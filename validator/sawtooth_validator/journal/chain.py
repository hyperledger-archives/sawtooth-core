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
from threading import RLock

from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.block_pipeline import SimpleReceiverThread
from sawtooth_validator.journal.consensus.consensus_factory import \
    ConsensusFactory
from sawtooth_validator.protobuf.transaction_receipt_pb2 import \
    TransactionReceipt
from sawtooth_validator.metrics.wrappers import CounterWrapper
from sawtooth_validator.metrics.wrappers import GaugeWrapper


LOGGER = logging.getLogger(__name__)


class ForkResolutionResult:
    def __init__(self, chain_head, block):
        self.block = block
        self.chain_head = chain_head
        self.new_chain = []
        self.current_chain = []
        self.committed_batches = []
        self.uncommitted_batches = []
        self.commit_new_chain = False

    def __bool__(self):
        return self.commit_new_chain


class ForkResolutionAborted(Exception):
    """
    Indication that the resolution of this fork has terminated for an expected
    reason and that resolution should be terminated.
    """
    pass


class ChainHeadUpdated(Exception):
    """Raised when a chain head changed event is detected and we need to abort
    processing and restart processing with the new chain head.
    """
    pass


class ChainObserver(object, metaclass=ABCMeta):
    @abstractmethod
    def chain_update(self, block, receipts):
        """This method is called by the ChainController on block boundaries.

        Args:
            block (:obj:`BlockWrapper`): The block that was just committed.
            receipts (dict of {str: receipt}): Map of transaction signatures to
                transaction receipts for all transactions in the block."""
        raise NotImplementedError()


class ChainController(object):
    """
    To evaluating new blocks to determine if they should extend or replace
    the current chain. If they are valid extend the chain.
    """

    def __init__(self,
                 block_cache,
                 state_view_factory,
                 chain_head_lock,
                 on_chain_updated,
                 chain_id_manager,
                 identity_public_key,
                 data_dir,
                 config_dir,
                 chain_observers,
                 metrics_registry=None):
        """Initialize the ChainController
        Args:
            block_cache: The cache of all recent blocks and the processing
                state associated with them.
            state_view_factory: The factory object to create
            chain_head_lock: Lock to hold while the chain head is being
                updated, this prevents other components that depend on the
                chain head and the BlockStore from having the BlockStore change
                under them. This lock is only for core Journal components
                (BlockPublisher and ChainController), other components should
                handle block not found errors from the BlockStore explicitly.
            on_chain_updated: The callback to call to notify the rest of the
                 system the head block in the chain has been changed.
            chain_id_manager: The ChainIdManager instance.
            identity_public_key: The public key of this validator.
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
        self._identity_public_key = identity_public_key
        self._data_dir = data_dir
        self._config_dir = config_dir

        self._chain_id_manager = chain_id_manager

        self._chain_head = None

        self._chain_observers = chain_observers

        self._block_receive_thread = None

        if metrics_registry:
            self._chain_head_gauge = GaugeWrapper(
                metrics_registry.gauge('chain_head', default='no chain head'))
            self._committed_transactions_count = CounterWrapper(
                metrics_registry.counter('committed_transactions_count'))
            self._block_num_gauge = GaugeWrapper(
                metrics_registry.gauge('block_num'))
        else:
            self._chain_head_gauge = GaugeWrapper()
            self._committed_transactions_count = CounterWrapper()
            self._block_num_gauge = GaugeWrapper()

        # Only run this after all member variables have been bound
        self._set_chain_head_from_block_store()

        self._chain_controller_thread = None

    def _set_chain_head_from_block_store(self):
        try:
            chain_head = self._block_store.chain_head
            if chain_head is not None:
                if chain_head.status == BlockStatus.Valid:
                    self._chain_head = chain_head
                    LOGGER.info(
                        "Chain controller initialized with chain head: %s",
                        self._chain_head)
                    self._chain_head_gauge.set_value(
                        self._chain_head.identifier[:8])
                else:
                    LOGGER.warning(
                        "Tried to set chain head from block store, but chain"
                        " head isn't valid: %s", chain_head)
        except Exception:
            LOGGER.exception(
                "Invalid block store. Head of the block chain cannot be"
                " determined")
            raise

    def start(self, receiver):
        self._set_chain_head_from_block_store()
        self._notify_on_chain_updated(self._chain_head)
        self._chain_controller_thread = SimpleReceiverThread(
            receiver=receiver,
            task=self.on_block_validated,
            name='ChainControllerThread')
        self._chain_controller_thread.start()

    def stop(self):
        if self._chain_controller_thread is not None:
            self._chain_controller_thread.stop()

    @property
    def chain_head(self):
        return self._chain_head

    def on_block_validated(self, block):
        """Try to update the chain with this block. If the chain head updates
        for some other reason, try again."""
        try:
            while True:
                chain_head_updated = False
                try:
                    self.update_chain(block)
                except ChainHeadUpdated:
                    chain_head_updated = True
                if not chain_head_updated:
                    return

        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(
                "Unhandled exception in ChainController.on_block_validated()")

    def update_chain(self, block):
        """Try to update the chain.
        Args:
            block (BlockWrapper): The validated block.
        """
        if self._chain_head is None:
            # Try to set genesis
            self._set_genesis(block)
            return

        result = self.resolve_fork(self._chain_head, block)

        # Make sure the chain head didn't update while resolving the fork
        if result.chain_head.identifier != self._chain_head.identifier:
            LOGGER.info(
                'Chain head updated from %s to %s while resolving fork with '
                'head: %s', result.chain_head, self._chain_head, block)
            raise ChainHeadUpdated()

        if result.commit_new_chain:
            with self._chain_head_lock:
                self._chain_head = block

                # update the the block store to have the new chain
                self._block_store.update_chain(
                    result.new_chain, result.current_chain)

                LOGGER.info("Chain head updated to: %s", self._chain_head)

                self._chain_head_gauge.set_value(
                    self._chain_head.identifier[:8])

                self._committed_transactions_count.inc(
                    block.transaction_count)

                self._block_num_gauge.set_value(self._chain_head.block_num)

                # tell the BlockPublisher else the chain is updated
                self._notify_on_chain_updated(
                    self._chain_head,
                    result.committed_batches,
                    result.uncommitted_batches)

                for batch in block.batches:
                    if batch.trace:
                        LOGGER.debug(
                            "TRACE %s: %s", batch.header_signature,
                            self.__class__.__name__)

            for blk in result.new_chain:
                receipts = self._make_receipts(blk.execution_results)
                # Update all chain observers
                for observer in self._chain_observers:
                    observer.chain_update(blk, receipts)

        # The block is otherwise valid, but we have determined we
        # don't want it as the chain head.
        else:
            LOGGER.info('Rejected new chain head: %s', block)

    def resolve_fork(self, chain_head, block):
        """Build a ForkResolutionResult for the chain this block is on."""
        result = ForkResolutionResult(chain_head, block)

        if block.status != BlockStatus.Valid:
            result.commit_new_chain = False
            return result

        # Create new local variables for current and new block, since these
        # variables get modified later
        current_block = chain_head
        new_block = block

        # Get all the blocks since the greatest common height from the longer
        # chain.
        if self.compare_chain_height(current_block, new_block):
            current_block, result.current_chain = \
                self.build_fork_diff_to_common_height(current_block, new_block)
        else:
            new_block, result.new_chain = \
                self.build_fork_diff_to_common_height(new_block, current_block)

        # Add blocks to the two chains until a common ancestor is found or
        # raise an exception if no common ancestor is found
        self.extend_fork_diff_to_common_ancestor(
            new_block, current_block, result.new_chain, result.current_chain)

        # First, double check if any predecessors are invalid or unknown.
        # Because the BlockValidator only passes the ChainController blocks
        # if they are valid, this should always be the case..
        for blk in result.new_chain[1:]:
            # This should never happen, because the completer and scheduler
            # should ensure we only receive blocks in order
            if blk.status == BlockStatus.Unknown:
                LOGGER.error(
                    "Chain controller received valid block '%s' but "
                    "predecessor '%s' status is unknown",
                    block, blk)
                raise ForkResolutionAborted()

            if blk.status == BlockStatus.Invalid:
                result.commit_new_chain = False
                return result

        # Ask consensus if the new chain should be committed
        result.commit_new_chain = \
            self._compare_forks_consensus(chain_head, block)

        # If committing the new chain, get the list of committed batches
        # from the current chain that need to be uncommitted and the list
        # of uncommitted batches from the new chain that need to be
        # committed.
        if result.commit_new_chain:
            commit, uncommit = self.get_batch_commit_changes(
                result.new_chain, result.current_chain)
            result.committed_batches = commit
            result.uncommitted_batches = uncommit

        return result

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

                if block.status == BlockStatus.Valid:
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
            receipt.data.extend([data for data in result.data])
            receipt.state_changes.extend(result.state_changes)
            receipt.events.extend(result.events)
            receipt.transaction_id = result.signature
            receipts.append(receipt)
        return receipts

    @staticmethod
    def compare_chain_height(head_a, head_b):
        """Returns True if head_a is taller, False if head_b is taller, and True
        if the heights are the same."""
        return head_a.block_num - head_b.block_num >= 0

    def build_fork_diff_to_common_height(self, head_long, head_short):
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
            ForkResolutionAborted
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
                LOGGER.debug(
                    "Failed to build fork diff due to missing predecessor: %s",
                    blk)

                # Mark all blocks in the longer chain since the invalid block
                # as invalid.
                for blk in fork_diff:
                    blk.status = BlockStatus.Invalid
                raise ForkResolutionAborted()

        return blk, fork_diff

    def extend_fork_diff_to_common_ancestor(
        self, new_blkw, cur_blkw, new_chain, cur_chain
    ):
        """ Finds a common ancestor of the two chains. new_blkw and cur_blkw
        must be at the same height, or this will always fail.
        """
        # Add blocks to the corresponding chains until a common ancestor is
        # found.
        while cur_blkw.identifier != new_blkw.identifier:
            if cur_blkw.previous_block_id == NULL_BLOCK_IDENTIFIER or \
               new_blkw.previous_block_id == NULL_BLOCK_IDENTIFIER:
                # If the genesis block is reached and the identifiers are
                # different, the forks are not for the same chain.
                LOGGER.info(
                    "Block rejected due to wrong genesis: %s %s",
                    cur_blkw, new_blkw)

                for b in new_chain:
                    b.status = BlockStatus.Invalid
                raise ForkResolutionAborted()

            new_chain.append(new_blkw)
            try:
                new_blkw = self._block_cache[new_blkw.previous_block_id]
            except KeyError:
                LOGGER.debug(
                    "Block rejected due to missing predecessor: %s",
                    new_blkw)
                for b in new_chain:
                    b.status = BlockStatus.Invalid
                raise ForkResolutionAborted()

            cur_chain.append(cur_blkw)
            cur_blkw = self._block_cache[cur_blkw.previous_block_id]

    def _compare_forks_consensus(self, chain_head, new_block):
        """Ask the consensus module which fork to choose.
        """
        consensus = self._load_consensus(chain_head)
        fork_resolver = consensus.ForkResolver(
            block_cache=self._block_cache,
            state_view_factory=self._state_view_factory,
            data_dir=self._data_dir,
            config_dir=self._config_dir,
            validator_id=self._identity_public_key)
        return fork_resolver.compare_forks(chain_head, new_block)

    @staticmethod
    def get_batch_commit_changes(new_chain, cur_chain):
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

    def _load_consensus(self, block):
        """Load the consensus module using the state as of the given block."""
        if block is not None:
            return ConsensusFactory.get_configured_consensus_module(
                block.header_signature,
                BlockWrapper.state_view_for_block(
                    block,
                    self._state_view_factory))
        return ConsensusFactory.get_consensus_module('genesis')
