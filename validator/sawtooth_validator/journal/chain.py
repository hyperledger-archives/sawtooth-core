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
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.block_validator import BlockValidationFailure
from sawtooth_validator.journal.consensus.consensus_factory import \
    ConsensusFactory
from sawtooth_validator.protobuf.transaction_receipt_pb2 import \
    TransactionReceipt
from sawtooth_validator import metrics


LOGGER = logging.getLogger(__name__)
COLLECTOR = metrics.get_collector(__name__)


class ForkResolutionError(Exception):
    """
    Indication that an error occured during fork resolution.
    """


class ForkResolutionResult:
    def __init__(self, block):
        self.block = block
        self.chain_head = None
        self.new_chain = []
        self.current_chain = []
        self.committed_batches = []
        self.uncommitted_batches = []
        # NOTE: The following are for all blocks validated in order to validate
        # this block, i.e., all blocks on this block's fork
        self.execution_results = []
        self.transaction_count = 0

    def __bool__(self):
        return self.block.status == BlockStatus.Valid

    def __str__(self):
        keys = ("block", "valid", "chain_head", "new_chain", "current_chain",
                "committed_batches", "uncommitted_batches",
                "execution_results", "transaction_count")

        out = "{"
        for key in keys:
            out += "%s: %s," % (key, self.__getattribute(key))
        return out[:-1] + "}"


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
                 identity_signer,
                 data_dir,
                 config_dir,
                 chain_observers):
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
            identity_signer: A cryptographic signer for signing blocks.
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
        self._notify_on_chain_updated = on_chain_updated
        self._identity_signer = identity_signer
        self._data_dir = data_dir
        self._config_dir = config_dir

        self._chain_id_manager = chain_id_manager

        self._chain_head = None

        self._chain_observers = chain_observers

        self._chain_head_gauge = COLLECTOR.gauge('chain_head', instance=self)
        self._committed_transactions_gauge = COLLECTOR.gauge(
            'committed_transactions_gauge', instance=self)
        self._committed_transactions_gauge.set_value(0)
        self._committed_transactions_count = COLLECTOR.counter(
            'committed_transactions_count', instance=self)
        self._block_num_gauge = COLLECTOR.gauge('block_num', instance=self)
        self._blocks_considered_count = COLLECTOR.counter(
            'blocks_considered_count', instance=self)

        self._moved_to_fork_count = COLLECTOR.counter(
            'chain_head_moved_to_fork_count', instance=self)

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

    def on_block_validated(self, block):
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
            if block.status != BlockStatus.Valid:
                return

            with self._lock:
                commit_new_block, result = self._resolve_fork(block)
                self._blocks_considered_count.inc()
                new_block = result.block

                # If the head is to be updated to the new block.
                if commit_new_block:
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

                        self._committed_transactions_gauge.set_value(
                            self._block_store.get_transaction_count())

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

                    for blk in reversed(result.new_chain):
                        receipts = self._make_receipts(blk.execution_results)
                        # Update all chain observers
                        for observer in self._chain_observers:
                            observer.chain_update(blk, receipts)

                # The block is otherwise valid, but we have determined we
                # don't want it as the chain head.
                else:
                    LOGGER.info('Rejected new chain head: %s', new_block)

        # pylint: disable=broad-except
        except Exception:
            LOGGER.exception(
                "Unhandled exception in ChainController.on_block_validated()")

    def _resolve_fork(self, block):
        result = ForkResolutionResult(block)
        LOGGER.info("Starting fork resolution of : %s", block)

        # Get the current chain_head and store it in the result
        chain_head = self._block_cache.block_store.chain_head
        result.chain_head = chain_head

        # Create new local variables for current and new block, since
        # these variables get modified later
        current_block = chain_head
        new_block = block

        try:
            # Get all the blocks since the greatest common height from the
            # longer chain.
            if self._compare_chain_height(current_block, new_block):
                current_block, result.current_chain =\
                    self._build_fork_diff_to_common_height(
                        current_block, new_block)
            else:
                new_block, result.new_chain =\
                    self._build_fork_diff_to_common_height(
                        new_block, current_block)

            # Add blocks to the two chains until a common ancestor is found
            # or raise an exception if no common ancestor is found
            self._extend_fork_diff_to_common_ancestor(
                new_block, current_block,
                result.new_chain, result.current_chain)
        except ForkResolutionError as err:
            LOGGER.error(
                'Encountered an error while resolving a fork with head %s:'
                ' %s', block, err)
            return False, result

        for blk in reversed(result.new_chain):
            result.transaction_count += blk.num_transactions

        # Ask consensus if the new chain should be committed
        LOGGER.info(
            "Comparing current chain head '%s' against new block '%s'",
            chain_head, new_block)
        for i in range(max(
            len(result.new_chain), len(result.current_chain)
        )):
            cur = new = num = "-"
            if i < len(result.current_chain):
                cur = result.current_chain[i].header_signature[:8]
                num = result.current_chain[i].block_num
            if i < len(result.new_chain):
                new = result.new_chain[i].header_signature[:8]
                num = result.new_chain[i].block_num
            LOGGER.info(
                "Fork comparison at height %s is between %s and %s",
                num, cur, new)

        commit_new_chain = self._compare_forks_consensus(chain_head, block)

        # If committing the new chain, get the list of committed batches
        # from the current chain that need to be uncommitted and the list
        # of uncommitted batches from the new chain that need to be
        # committed.
        if commit_new_chain:
            commit, uncommit =\
                self._get_batch_commit_changes(
                    result.new_chain, result.current_chain)
            result.committed_batches = commit
            result.uncommitted_batches = uncommit

            if result.new_chain[0].previous_block_id \
                    != chain_head.identifier:
                self._moved_to_fork_count.inc()

        LOGGER.info("Finished fork resolution of: %s", block)
        return commit_new_chain, result

    @staticmethod
    def _compare_chain_height(head_a, head_b):
        """Returns True if head_a is taller, False if head_b is taller, and
        True if the heights are the same."""
        return head_a.block_num - head_b.block_num >= 0

    def _build_fork_diff_to_common_height(self, head_long, head_short):
        """Returns a list of blocks on the longer chain since the greatest
        common height between the two chains. Note that the chains may not
        have the same block id at the greatest common height.

        Args:
            head_long (BlockWrapper)
            head_short (BlockWrapper)

        Returns:
            (list of BlockWrapper) All blocks in the longer chain since the
            last block in the shorter chain. Ordered newest to oldest.

        Raises:
            BlockValidationError
                The block is missing a predecessor. Note that normally this
                shouldn't happen because of the completer."""
        fork_diff = []

        last = head_short.block_num
        blk = head_long

        while blk.block_num > last:
            if blk.previous_block_id == NULL_BLOCK_IDENTIFIER:
                break

            fork_diff.append(blk)
            try:
                blk = self._block_cache[blk.previous_block_id]
            except KeyError:
                raise ForkResolutionError(
                    'Failed to build fork diff: block {} missing predecessor'
                    .format(blk))

        return blk, fork_diff

    def _extend_fork_diff_to_common_ancestor(
        self, new_blkw, cur_blkw, new_chain, cur_chain
    ):
        """ Finds a common ancestor of the two chains. new_blkw and cur_blkw
        must be at the same height, or this will always fail.
        """
        while cur_blkw.identifier != new_blkw.identifier:
            if (cur_blkw.previous_block_id == NULL_BLOCK_IDENTIFIER
                    or new_blkw.previous_block_id == NULL_BLOCK_IDENTIFIER):
                # We are at a genesis block and the blocks are not the same
                for b in new_chain:
                    b.status = BlockStatus.Invalid
                raise ForkResolutionError(
                    'Block {} rejected due to wrong genesis {}'.format(
                        cur_blkw, new_blkw))

            new_chain.append(new_blkw)
            try:
                new_blkw = self._block_cache[new_blkw.previous_block_id]
            except KeyError:
                raise ForkResolutionError(
                    'Block {} rejected due to missing predecessor {}'.format(
                        new_blkw, new_blkw.previous_block_id))

            cur_chain.append(cur_blkw)
            cur_blkw = self._block_cache[cur_blkw.previous_block_id]

    def _compare_forks_consensus(self, chain_head, new_block):
        """Ask the consensus module which fork to choose.
        """
        public_key = self._identity_signer.get_public_key().as_hex()
        consensus = self._load_consensus(chain_head)
        fork_resolver = consensus.ForkResolver(
            block_cache=self._block_cache,
            state_view_factory=self._state_view_factory,
            data_dir=self._data_dir,
            config_dir=self._config_dir,
            validator_id=public_key)

        return fork_resolver.compare_forks(chain_head, new_block)

    def _load_consensus(self, block):
        """Load the consensus module using the state as of the given block."""
        if block is not None:
            return ConsensusFactory.get_configured_consensus_module(
                block.header_signature,
                BlockWrapper.state_view_for_block(
                    block,
                    self._state_view_factory))
        return ConsensusFactory.get_consensus_module('genesis')

    @staticmethod
    def _get_batch_commit_changes(new_chain, cur_chain):
        """
        Get all the batches that should be committed from the new chain and
        all the batches that should be uncommitted from the current chain.
        """
        committed_batches = []
        for blkw in new_chain:
            for batch in blkw.batches:
                committed_batches.append(batch)

        uncommitted_batches = []
        for blkw in cur_chain:
            for batch in blkw.batches:
                uncommitted_batches.append(batch)

        return (committed_batches, uncommitted_batches)

    def on_block_received(self, block):
        try:
            with self._lock:
                if self.has_block(block.header_signature):
                    # do we already have this block
                    return

                if self.chain_head is None:
                    self._set_genesis(block)
                    return

                self._block_cache[block.identifier] = block

                # schedule this block for validation.
                self._submit_blocks_for_verification([block])

        # pylint: disable=broad-except
        except Exception:
            LOGGER.exception(
                "Unhandled exception in ChainController.on_block_received()")

    def has_block(self, block_id):
        with self._lock:
            if block_id in self._block_cache:
                return True

            if self._block_validator.has_block(block_id):
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
