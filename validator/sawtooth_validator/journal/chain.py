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

from sawtooth_validator.concurrent.thread import InstrumentedThread
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.block_validator import BlockValidationFailure
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
                 block_validator,
                 state_view_factory,
                 chain_head_lock,
                 on_chain_updated,
                 chain_id_manager,
                 data_dir,
                 config_dir,
                 chain_observers,
                 metrics_registry=None):
        """Initialize the ChainController
        Args:
            block_cache: The cache of all recent blocks and the processing
                state associated with them.
            block_validator: The object to use for submitting block validation
                work.
            state_view_factory: A factory that can be used to create read-
                only views of state for a particular merkle root, in
                particular the state as it existed when a particular block
                was the chain head.
            chain_head_lock: Lock to hold while the chain head is being
                updated, this prevents other components that depend on the
                chain head and the BlockStore from having the BlockStore change
                under them. This lock is only for core Journal components
                (BlockPublisher and ChainController), other components should
                handle block not found errors from the BlockStore explicitly.
            on_chain_updated: The callback to call to notify the rest of the
                 system the head block in the chain has been changed.
            chain_id_manager: The ChainIdManager instance.
            data_dir: path to location where persistent data for the
                consensus module can be stored.
            config_dir: path to location where config data for the
                consensus module can be found.
            chain_observers (list of :obj:`ChainObserver`): A list of chain
                observers.
            metrics_registry: (Optional) Pyformance metrics registry handle for
                creating new metrics.
        Returns:
            None
        """
        self._lock = RLock()
        self._chain_head_lock = chain_head_lock
        self._block_cache = block_cache
        self._block_store = block_cache.block_store
        self._state_view_factory = state_view_factory
        self._notify_on_chain_updated = on_chain_updated
        self._data_dir = data_dir
        self._config_dir = config_dir

        self._chain_id_manager = chain_id_manager

        self._chain_head = None

        self._chain_observers = chain_observers
        self._metrics_registry = metrics_registry

        if metrics_registry:
            self._chain_head_gauge = GaugeWrapper(
                metrics_registry.gauge('chain_head', default='no chain head'))
            self._committed_transactions_count = CounterWrapper(
                metrics_registry.counter('committed_transactions_count'))
            self._block_num_gauge = GaugeWrapper(
                metrics_registry.gauge('block_num'))
            self._blocks_considered_count = CounterWrapper(
                metrics_registry.counter('blocks_considered_count'))
        else:
            self._chain_head_gauge = GaugeWrapper()
            self._committed_transactions_count = CounterWrapper()
            self._block_num_gauge = GaugeWrapper()
            self._blocks_considered_count = CounterWrapper()

        self._block_queue = queue.Queue()
        self._chain_thread = None

        self._block_validator = block_validator

        # Only run this after all member variables have been bound
        self._set_chain_head_from_block_store()

    def _set_chain_head_from_block_store(self):
        try:
            self._chain_head = self._block_store.chain_head
            if self._chain_head is not None:
                LOGGER.info("Chain controller initialized with chain head: %s",
                            self._chain_head)
                self._chain_head_gauge.set_value(
                    self._chain_head.identifier[:8])
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
        self._block_validator.submit_blocks_for_verification(
            blocks, self.on_block_validated)

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
                self._blocks_considered_count.inc()
                new_block = result.block

                # if the head has changed, since we started the work.
                if result.chain_head.identifier !=\
                        self._chain_head.identifier:
                    LOGGER.info(
                        'Chain head updated from %s to %s while processing '
                        'block: %s',
                        result.chain_head,
                        self._chain_head,
                        new_block)

                    LOGGER.debug('Verify block again: %s ', new_block)
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

                    for block in reversed(result.new_chain):
                        receipts = self._make_receipts(block.execution_results)
                        # Update all chain observers
                        for observer in self._chain_observers:
                            observer.chain_update(block, receipts)

                # The block is otherwise valid, but we have determined we
                # don't want it as the chain head.
                else:
                    LOGGER.info('Rejected new chain head: %s', new_block)

        # pylint: disable=broad-except
        except Exception:
            LOGGER.exception(
                "Unhandled exception in ChainController.on_block_validated()")

    def on_block_received(self, block):
        try:
            with self._lock:
                # are we already processing this block
                if self.has_block(block.header_signature):
                    return

                if self.chain_head is None:
                    self._set_genesis(block)
                    return

                # schedule this block for validation.
                self._submit_blocks_for_verification([block])

        # pylint: disable=broad-except
        except Exception:
            LOGGER.exception(
                "Unhandled exception in ChainController.on_block_received()")

    def has_block(self, block_id):
        with self._lock:
            if self._block_validator.in_process(block_id):
                return True

            if self._block_validator.in_pending(block_id):
                return True

            return False

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
                try:
                    self._block_validator.validate_block(block)
                except BlockValidationFailure as err:
                    LOGGER.warning(
                        'Cannot set chain head; '
                        'genesis block %s is not valid: %s',
                        block, err)
                    return

                if chain_id is None:
                    self._chain_id_manager.save_block_chain_id(
                        block.identifier)
                self._block_store.update_chain([block])
                self._chain_head = block
                self._notify_on_chain_updated(self._chain_head)

        else:
            LOGGER.warning("Cannot set initial chain head, this is not a "
                           "genesis block: %s", block)

    def _make_receipts(self, results):
        receipts = []
        for result in results:
            receipt = TransactionReceipt()
            receipt.data.extend([data for data in result.data])
            receipt.state_changes.extend(result.state_changes)
            receipt.events.extend(result.events)
            receipt.transaction_id = result.signature
            receipts.append(receipt)
        return receipts
