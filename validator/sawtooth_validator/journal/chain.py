# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

from abc import ABCMeta
from abc import abstractmethod
import logging
import queue
from threading import RLock

import sawtooth_signing as signing

from sawtooth_validator.concurrent.thread import InstrumentedThread
from sawtooth_validator.concurrent.threadpool import \
    InstrumentedThreadPoolExecutor
from sawtooth_validator.journal.block_validator import BlockValidator
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.consensus.consensus_factory import \
    ConsensusFactory
from sawtooth_validator.protobuf.transaction_receipt_pb2 import \
    TransactionReceipt
from sawtooth_validator.metrics.wrappers import CounterWrapper
from sawtooth_validator.metrics.wrappers import GaugeWrapper


LOGGER = logging.getLogger(__name__)


class ChainObserver(object, metaclass=ABCMeta):
    @abstractmethod
    def chain_update(self, block, receipts):
        """This method is called by the ChainController on block boundaries.

        Args:
            block (:obj:`BlockWrapper`): The block that was just committed.
            receipts (dict of {str: receipt}): Map of transaction signatures to
                transaction receipts for all transactions in the block."""
        raise NotImplementedError()


class _ChainThread(InstrumentedThread):
    def __init__(self, chain_controller, block_queue, block_cache):
        super().__init__(name='_ChainThread')
        self._chain_controller = chain_controller
        self._block_queue = block_queue
        self._block_cache = block_cache
        self._exit = False

    def run(self):
        try:
            while True:
                try:
                    block = self._block_queue.get(timeout=1)
                    self._chain_controller.on_block_received(block)
                except queue.Empty:
                    # If getting a block times out, just try again.
                    pass

                if self._exit:
                    return
        # pylint: disable=broad-except
        except Exception:
            LOGGER.exception("ChainController thread exited with error.")

    def stop(self):
        self._exit = True


class ChainController(object):
    """
    To evaluating new blocks to determine if they should extend or replace
    the current chain. If they are valid extend the chain.
    """
    def __init__(self,
                 block_cache,
                 block_sender,
                 state_view_factory,
                 transaction_executor,
                 chain_head_lock,
                 on_chain_updated,
                 squash_handler,
                 chain_id_manager,
                 identity_signing_key,
                 data_dir,
                 config_dir,
                 permission_verifier,
                 chain_observers,
                 thread_pool=None,
                 metrics_registry=None):
        """Initialize the ChainController
        Args:
            block_cache: The cache of all recent blocks and the processing
                state associated with them.
            block_sender: an interface object used to send blocks to the
                network.
            state_view_factory: The factory object to create
            transaction_executor: The TransactionExecutor used to produce
                schedulers for batch validation.
            chain_head_lock: Lock to hold while the chain head is being
                updated, this prevents other components that depend on the
                chain head and the BlockStore from having the BlockStore change
                under them. This lock is only for core Journal components
                (BlockPublisher and ChainController), other components should
                handle block not found errors from the BlockStore explicitly.
            on_chain_updated: The callback to call to notify the rest of the
                 system the head block in the chain has been changed.
                 squash_handler: a parameter passed when creating transaction
                 schedulers.
            chain_id_manager: The ChainIdManager instance.
            identity_signing_key: Private key for signing blocks.
            data_dir: path to location where persistent data for the
                consensus module can be stored.
            config_dir: path to location where config data for the
                consensus module can be found.
            chain_observers (list of :obj:`ChainObserver`): A list of chain
                observers.
        Returns:
            None
        """
        self._lock = RLock()
        self._chain_head_lock = chain_head_lock
        self._block_cache = block_cache
        self._block_store = block_cache.block_store
        self._state_view_factory = state_view_factory
        self._block_sender = block_sender
        self._transaction_executor = transaction_executor
        self._notify_on_chain_updated = on_chain_updated
        self._squash_handler = squash_handler
        self._identity_signing_key = identity_signing_key
        self._identity_public_key = \
            signing.generate_public_key(self._identity_signing_key)
        self._data_dir = data_dir
        self._config_dir = config_dir

        self._blocks_processing = {}  # a set of blocks that are
        # currently being processed.
        self._blocks_pending = {}  # set of blocks that the previous block
        # is being processed. Once that completes this block will be
        # scheduled for validation.
        self._chain_id_manager = chain_id_manager

        self._chain_head = None
        self._set_chain_head_from_block_store()

        self._permission_verifier = permission_verifier
        self._chain_observers = chain_observers
        self._chain_head_gauge = \
            metrics_registry.gauge('chain_head', default='no chain head') \
            if metrics_registry else None

        if metrics_registry:
            self._committed_transactions_count = CounterWrapper(
                metrics_registry.counter('committed_transactions_count'))
            self._block_num_gauge = GaugeWrapper(
                metrics_registry.gauge('block_num'))
        else:
            self._committed_transactions_count = CounterWrapper()
            self._block_num_gauge = GaugeWrapper()

        self._block_queue = queue.Queue()
        self._thread_pool = \
            InstrumentedThreadPoolExecutor(1) \
            if thread_pool is None else thread_pool
        self._chain_thread = None

    def _set_chain_head_from_block_store(self):
        try:
            self._chain_head = self._block_store.chain_head
            if self._chain_head is not None:
                LOGGER.info("Chain controller initialized with chain head: %s",
                            self._chain_head)
        except Exception:
            LOGGER.exception(
                "Invalid block store. Head of the block chain cannot be"
                " determined")
            raise

    def start(self):
        self._set_chain_head_from_block_store()
        self._notify_on_chain_updated(self._chain_head)

        self._chain_thread = _ChainThread(
            chain_controller=self,
            block_queue=self._block_queue,
            block_cache=self._block_cache)
        self._chain_thread.start()

    def stop(self):
        if self._chain_thread is not None:
            self._chain_thread.stop()
            self._chain_thread = None

        if self._thread_pool is not None:
            self._thread_pool.shutdown(wait=True)

    def queue_block(self, block):
        """
        New block has been received, queue it with the chain controller
        for processing.
        """
        self._block_queue.put(block)

    @property
    def chain_head(self):
        return self._chain_head

    def _submit_blocks_for_verification(self, blocks):
        for blkw in blocks:
            state_view = BlockWrapper.state_view_for_block(
                self.chain_head,
                self._state_view_factory)
            consensus_module = \
                ConsensusFactory.get_configured_consensus_module(
                    self.chain_head.header_signature,
                    state_view)

            validator = BlockValidator(
                consensus_module=consensus_module,
                new_block=blkw,
                block_cache=self._block_cache,
                state_view_factory=self._state_view_factory,
                executor=self._transaction_executor,
                squash_handler=self._squash_handler,
                identity_signing_key=self._identity_signing_key,
                data_dir=self._data_dir,
                config_dir=self._config_dir,
                permission_verifier=self._permission_verifier)
            self._blocks_processing[blkw.block.header_signature] = validator
            self._thread_pool.submit(validator.run, self.on_block_validated)

    def on_block_validated(self, commit_new_block, result):
        """Message back from the block validator, that the validation is
        complete
        Args:
        commit_new_block (Boolean): whether the new block should become the
        chain head or not.
        result (Dict): Map of the results of the fork resolution.
        Returns:
            None
        """
        try:
            with self._lock:
                new_block = result.block
                LOGGER.info("on_block_validated: %s", new_block)

                # remove from the processing list
                del self._blocks_processing[new_block.identifier]

                # Remove this block from the pending queue, obtaining any
                # immediate descendants of this block in the process.
                descendant_blocks = \
                    self._blocks_pending.pop(new_block.identifier, [])

                # if the head has changed, since we started the work.
                if result.chain_head.identifier !=\
                        self._chain_head.identifier:
                    LOGGER.info(
                        'Chain head updated from %s to %s while processing '
                        'block: %s',
                        result.chain_head,
                        self._chain_head,
                        new_block)

                    # If any immediate descendant blocks arrived while this
                    # block was being processed, then submit them for
                    # verification.  Otherwise, add this block back to the
                    # pending queue and resubmit it for verification.
                    if descendant_blocks:
                        LOGGER.debug(
                            'Verify descendant blocks: %s (%s)',
                            new_block,
                            [block.identifier[:8] for block in
                             descendant_blocks])
                        self._submit_blocks_for_verification(
                            descendant_blocks)
                    else:
                        LOGGER.debug('Verify block again: %s ', new_block)
                        self._blocks_pending[new_block.identifier] = []
                        self._submit_blocks_for_verification([new_block])

                # If the head is to be updated to the new block.
                elif commit_new_block:
                    with self._chain_head_lock:
                        self._chain_head = new_block

                        # update the the block store to have the new chain
                        self._block_store.update_chain(result.new_chain,
                                                       result.current_chain)

                        LOGGER.info(
                            "Chain head updated to: %s",
                            self._chain_head)

                        if self._chain_head_gauge:
                            self._chain_head_gauge.set_value(
                                self._chain_head.identifier[:8])

                        self._committed_transactions_count.inc(
                            result.transaction_count)

                        self._block_num_gauge.set_value(
                            self._chain_head.block_num)

                        # tell the BlockPublisher else the chain is updated
                        self._notify_on_chain_updated(
                            self._chain_head,
                            result.committed_batches,
                            result.uncommitted_batches)

                        for batch in new_block.batches:
                            if batch.trace:
                                LOGGER.debug("TRACE %s: %s",
                                             batch.header_signature,
                                             self.__class__.__name__)

                    # Submit any immediate descendant blocks for verification
                    LOGGER.debug(
                        'Verify descendant blocks: %s (%s)',
                        new_block,
                        [block.identifier[:8] for block in descendant_blocks])
                    self._submit_blocks_for_verification(descendant_blocks)

                    receipts = self._make_receipts(result.execution_results)
                    # Update all chain observers
                    for observer in self._chain_observers:
                        observer.chain_update(new_block, receipts)

                # If the block was determine to be invalid.
                elif new_block.status == BlockStatus.Invalid:
                    # Since the block is invalid, we will never accept any
                    # blocks that are descendants of this block.  We are going
                    # to go through the pending blocks and remove all
                    # descendants we find and mark the corresponding block
                    # as invalid.
                    while descendant_blocks:
                        pending_block = descendant_blocks.pop()
                        pending_block.status = BlockStatus.Invalid

                        LOGGER.debug(
                            'Marking descendant block invalid: %s',
                            pending_block)

                        descendant_blocks.extend(
                            self._blocks_pending.pop(
                                pending_block.identifier,
                                []))

                # The block is otherwise valid, but we have determined we
                # don't want it as the chain head.
                else:
                    LOGGER.info('Rejected new chain head: %s', new_block)

                    # Submit for verification any immediate descendant blocks
                    # that arrived while we were processing this block.
                    LOGGER.debug(
                        'Verify descendant blocks: %s (%s)',
                        new_block,
                        [block.identifier[:8] for block in descendant_blocks])
                    self._submit_blocks_for_verification(descendant_blocks)

        # pylint: disable=broad-except
        except Exception:
            LOGGER.exception(
                "Unhandled exception in ChainController.on_block_validated()")

    def on_block_received(self, block):
        try:
            with self._lock:
                if block.header_signature in self._block_store:
                    # do we already have this block
                    return

                if self.chain_head is None:
                    self._set_genesis(block)
                    return

                # If we are already currently processing this block, then
                # don't bother trying to schedule it again.
                if block.identifier in self._blocks_processing:
                    return

                self._block_cache[block.identifier] = block
                self._blocks_pending[block.identifier] = []
                LOGGER.debug("Block received: %s", block)
                if block.previous_block_id in self._blocks_processing or \
                        block.previous_block_id in self._blocks_pending:
                    LOGGER.debug('Block pending: %s', block)
                    # if the previous block is being processed, put it in a
                    # wait queue, Also need to check if previous block is
                    # in the wait queue.
                    pending_blocks = \
                        self._blocks_pending.get(block.previous_block_id,
                                                 [])
                    pending_blocks.append(block)
                    self._blocks_pending[block.previous_block_id] = \
                        pending_blocks
                else:
                    # schedule this block for validation.
                    self._submit_blocks_for_verification([block])
        # pylint: disable=broad-except
        except Exception:
            LOGGER.exception(
                "Unhandled exception in ChainController.on_block_received()")

    def _set_genesis(self, block):
        # This is used by a non-genesis journal when it has received the
        # genesis block from the genesis validator
        if block.previous_block_id == NULL_BLOCK_IDENTIFIER:
            chain_id = self._chain_id_manager.get_block_chain_id()
            if chain_id is not None and chain_id != block.identifier:
                LOGGER.warning("Block id does not match block chain id %s. "
                               "Cannot set initial chain head.: %s",
                               chain_id[:8], block.identifier[:8])
            else:
                state_view = self._state_view_factory.create_view()
                consensus_module = \
                    ConsensusFactory.get_configured_consensus_module(
                        NULL_BLOCK_IDENTIFIER,
                        state_view)

                validator = BlockValidator(
                    consensus_module=consensus_module,
                    new_block=block,
                    block_cache=self._block_cache,
                    state_view_factory=self._state_view_factory,
                    executor=self._transaction_executor,
                    squash_handler=self._squash_handler,
                    identity_signing_key=self._identity_signing_key,
                    data_dir=self._data_dir,
                    config_dir=self._config_dir,
                    permission_verifier=self._permission_verifier)

                valid = validator.validate_block(block)
                if valid:
                    if chain_id is None:
                        self._chain_id_manager.save_block_chain_id(
                            block.identifier)
                    self._block_store.update_chain([block])
                    self._chain_head = block
                    self._notify_on_chain_updated(self._chain_head)
                else:
                    LOGGER.warning("The genesis block is not valid. Cannot "
                                   "set chain head: %s", block)

        else:
            LOGGER.warning("Cannot set initial chain head, this is not a "
                           "genesis block: %s", block)

    def _make_receipts(self, results):
        receipts = []
        for result in results:
            receipt = TransactionReceipt()
            receipt.data.extend([
                TransactionReceipt.Data(
                    data_type=data_type, data=data)
                for data_type, data in result.data
            ])
            receipt.state_changes.extend(result.state_changes)
            receipt.events.extend(result.events)
            receipt.transaction_id = result.signature
            receipts.append(receipt)
        return receipts
