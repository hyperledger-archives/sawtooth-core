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
import logging
from threading import RLock

from sawtooth_signing import secp256k1_signer as signing

from sawtooth_validator.execution.scheduler_exceptions import SchedulerError

from sawtooth_validator.journal.block_builder import BlockBuilder
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.consensus.consensus_factory import \
    ConsensusFactory
from sawtooth_validator.journal.transaction_cache import TransactionCache

from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_validator.state.merkle import INIT_ROOT_KEY


LOGGER = logging.getLogger(__name__)


class BlockPublisher(object):
    """
    Responsible for generating new blocks and publishing them when the
    Consensus deems it appropriate.
    """
    def __init__(self,
                 transaction_executor,
                 block_cache,
                 state_view_factory,
                 block_sender,
                 squash_handler,
                 chain_head,
                 identity_signing_key):
        """
        Initialize the BlockPublisher object

        Args:
            consensus_module (module): The consensus module for block
                processing.
            transaction_executor (:obj:`TransactionExecutor`): A
                TransactionExecutor instance.
            block_cache (:obj:`BlockCache`): A BlockCache instance.
            state_view_factory (:obj:`StateViewFactory`): StateViewFactory for
                read-only state views.
            block_sender (:obj:`BlockSender`): The BlockSender instance.
            squash_handler (function): Squash handler function for merging
                contexts.
            chain_head (:obj:`BlockWrapper`): The inital chain head.
            identity_signing_key (str): Private key for signing blocks
        """
        self._lock = RLock()
        self._candidate_block = None  # the next block in potentia
        self._consensus = None
        self._block_cache = block_cache
        self._state_view_factory = state_view_factory
        self._transaction_executor = transaction_executor
        self._block_sender = block_sender
        self._pending_batches = []  # batches we are waiting for validation,
        # arranged in the order of batches received.
        self._committed_txn = None  # Look-up cache for transactions that are
        # committed in the current chain. Cache is used here so that we can
        # support opportunistically building on top of a block we published.

        self._scheduler = None
        self._chain_head = chain_head  # block (BlockWrapper)
        self._squash_handler = squash_handler
        self._identity_signing_key = identity_signing_key
        self._identity_public_key = signing.encode_pubkey(
            signing.generate_pubkey(self._identity_signing_key), "hex")

    def _get_previous_block_root_state_hash(self, blkw):
        """ Get the state root hash for the previous block. This
        function handles the origing block correctly.
        :param blkw: the reference block block.
        :return: The state root hash of the previous block.
        """
        if blkw.previous_block_id == NULL_BLOCK_IDENTIFIER:
            return INIT_ROOT_KEY
        else:
            prev_blkw = self._block_cache[blkw.previous_block_id]
            return prev_blkw.state_root_hash

    def _build_block(self, chain_head):
        """ Build a candidate block and construct the consensus object to
        validate it.
        :param chain_head: The block to build on top of.
        :return: (BlockBuilder) - The candidate block in a BlockBuilder
        wrapper.
        """
        prev_state = self._get_previous_block_root_state_hash(chain_head)
        state_view = self._state_view_factory. \
            create_view(prev_state)
        consensus_module = ConsensusFactory.get_configured_consensus_module(
            state_view)
        self._consensus = consensus_module.\
            BlockPublisher(block_cache=self._block_cache,
                           state_view=state_view)

        block_header = BlockHeader(
            block_num=chain_head.block_num + 1,
            previous_block_id=chain_head.header_signature)
        block_builder = BlockBuilder(block_header)
        self._consensus.initialize_block(block_builder)

        # create a new scheduler
        # TBD move factory in to executor for easier mocking --
        # Yes I want to make fun of it.
        self._scheduler = self._transaction_executor.create_scheduler(
            self._squash_handler, chain_head.state_root_hash)

        self._transaction_executor.execute(self._scheduler)
        for batch in self._pending_batches:
            self._validate_batch(batch)

        # build the TransactionCache
        self._committed_txn = TransactionCache(self._block_cache.block_store)
        if chain_head.header_signature not in self._block_cache.block_store:
            # if we opportunistically building a block
            # we need to check make sure we track that blocks transactions
            # as recorded.
            for batch in chain_head.block.batches:
                for txn in batch.transactions:
                    self._committed_txn.add_txn(txn.header_signature)

        return block_builder

    def _sign_block(self, block):
        """ The block should be complete and the final
        signature from the publishing validator(this validator) needs to
        be added.
        """
        block.block_header.signer_pubkey = self._identity_public_key
        block_header = block.block_header
        header_bytes = block_header.SerializeToString()
        signature = signing.sign(
            header_bytes,
            self._identity_signing_key)
        block.set_signature(signature)
        return block

    def _check_batch_dependencies(self, batch, committed_txn):
        """Check the dependencies for all transactions in this are present.
        If all are present the committed_txn is updated with all txn in this
        batch and True is returned. If they are not return failure and the
        committed_txn is not updated.
        :param batch: the batch to validate
        :param committed_txn(TransactionCache): Current set of commited
        transaction, updated during processing.
        :return: Boolean, True if dependencies checkout, False otherwise.
        """
        for txn in batch.transactions:
            if not self._check_transaction_dependencies(txn, committed_txn):
                # if any transaction in this batch fails the whole batch
                # fails.
                committed_txn.remove_batch(batch)
                return False
            # update so any subsequent txn in the same batch can be dependent
            # on this transaction.
            committed_txn.add_txn(txn.header_signature)
        return True

    def _check_transaction_dependencies(self, txn, committed_txn):
        """Check that all this transactions dependencies are present.
        :param tx: the transaction to check
        :param committed_txn(TransactionCache): Current set of committed
        :return: Boolean, True if dependencies checkout, False otherwise.
        """
        txn_hdr = TransactionHeader()
        txn_hdr.ParseFromString(txn.header)
        for dep in txn_hdr.dependencies:
            if dep not in committed_txn:
                LOGGER.debug("Transaction rejected due " +
                             "missing dependency, transaction " +
                             "{} depends on {}",
                             txn.header_signature, dep)
                return False
        return True

    def _validate_batch(self, batch):
        """Schedule validation of a batch for inclusion in the new block
        :param batch: the batch to validate
        :return: None
        """
        if self._scheduler:
            try:
                self._scheduler.add_batch(batch)
            except SchedulerError as err:
                LOGGER.debug("Scheduler error processing batch: %s", err)

    def on_batch_received(self, batch):
        """
        A new batch is received, send it for validation
        :param batch: the new pending batch
        :return: None
        """
        with self._lock:
            # first we check if the transaction dependencies are satisified
            # The completer should have taken care of making sure all
            # Batches containing dependent transactions were sent to the
            # BlockPublisher prior to this Batch. So if there is a missing
            # dependency this is an error condition and the batch will be
            # dropped.
            if self._block_cache.block_store.has_batch(batch.header_signature):
                # batch is already committed.
                LOGGER.debug("Dropping previously committed batch: %s",
                             batch.header_signature)
                return
            elif self._check_batch_dependencies(batch, self._committed_txn):
                self._pending_batches.append(batch)
                # if we are building a block then send schedule it for
                # execution.
                if self._chain_head is not None:
                    self._validate_batch(batch)
            else:
                LOGGER.debug("Dropping batch due to missing dependencies: %s",
                             batch.header_signature)

    def _rebuild_pending_batches(self, committed_batches, uncommitted_batches):
        """When the chain head is changed. This recomputes the list of pending
        transactions
        :param committed_batches: Batches committed in the current chain
        since the root of the fork switching from.
        :param uncommitted_batches: Batches that were committed in the old
        fork since the common root.
        """
        if committed_batches is None:
            committed_batches = []
        if uncommitted_batches is None:
            uncommitted_batches = []

        committed_set = set([x.header_signature for x in committed_batches])

        pending_batches = self._pending_batches
        self._pending_batches = []

        # Uncommitted and pending disjoint sets
        # since batches can only be committed to a chain once.
        for batch in uncommitted_batches:
            if batch.header_signature not in committed_set:
                if self._check_batch_dependencies(batch, self._committed_txn):
                    self._pending_batches.append(batch)

        for batch in pending_batches:
            if batch.header_signature not in committed_set:
                if self._check_batch_dependencies(batch, self._committed_txn):
                    self._pending_batches.append(batch)

    def on_chain_updated(self, chain_head,
                         committed_batches=None,
                         uncommitted_batches=None):
        """
        The existing chain has been updated, the current head block has
        changed.

        :param chain_head: the new head of block_chain
        :param committed_batches: the set of batches that were committed
         as part of the new chain.
        :param uncommitted_batches: the list of transactions if any that are
        now de-committed when the new chain was selected.
        :return: None
        """
        try:
            with self._lock:
                LOGGER.info('Now building on top of block: %s', chain_head)

                self._chain_head = chain_head

                if self._candidate_block is not None and \
                        chain_head is not None and \
                        chain_head.identifier == \
                        self._candidate_block.previous_block_id:
                    # nothing to do. We are building of the current head.
                    # This can happen after we publish a block and
                    # opportunistically create a new block.
                    return
                else:
                    self._rebuild_pending_batches(committed_batches,
                                                  uncommitted_batches)

                    self._candidate_block = self._build_block(chain_head)
        # pylint: disable=broad-except
        except Exception as exc:
            LOGGER.exception(exc)
            LOGGER.critical("BlockPublisher thread exited.")

    def _finalize_block(self, block):
        if self._scheduler:
            self._scheduler.finalize()
            self._scheduler.complete(block=True)

        # Read valid batches from self._scheduler
        pending_batches = self._pending_batches
        committed_txn = TransactionCache(self._block_cache.block_store)
        self._pending_batches = []
        self._committed_txn = TransactionCache(self._block_cache.block_store)

        state_hash = None
        for batch in pending_batches:
            result = self._scheduler.get_batch_execution_result(
                batch.header_signature)
            # if a result is None, this means that the executor never
            # received the batch and it should be added to
            # the pending_batches
            if result is None:
                committed_txn.uncommit_batch(batch)
                self._pending_batches.append(batch)
            elif result.is_valid:
                # check if a dependent batch failed. This could be belt and
                # suspenders action here but it is logically possible that
                # a transaction has a dependency that fails it could
                # still succeed validation. In that case we do not want
                # to add it to the batch.
                if not self._check_batch_dependencies(batch, committed_txn):
                    LOGGER.debug("Batch %s invalid, due to missing txn "
                                 "dependency.", batch.header_signature)
                else:
                    block.add_batch(batch)
                state_hash = result.state_hash
            else:
                committed_txn.uncommit_batch(batch)
                LOGGER.debug("Batch %s invalid, not added to block.",
                             batch.header_signature)

        if state_hash is None:
            LOGGER.debug("Abandoning block %s no batches added", block)
            return

        self._consensus.finalize_block(block)
        self._consensus = None

        block.set_state_hash(state_hash)
        self._sign_block(block)

        return block

    def on_check_publish_block(self, force=False):
        """Ask the consensus module if it is time to claim the candidate block
        if it is then, claim it and tell the world about it.
        :return:
        """
        try:
            with self._lock:
                if self._candidate_block is None and\
                        len(self._pending_batches) != 0:
                    self._candidate_block = self._build_block(self._chain_head)

                if self._candidate_block and \
                        (force or len(self._pending_batches) != 0) and \
                        self._consensus.check_publish_block(self.
                                                            _candidate_block):
                    candidate = self._candidate_block
                    self._candidate_block = None

                    self._finalize_block(candidate)
                    # if no batches are in the block, do not send it out
                    if len(candidate.batches) == 0:
                        LOGGER.info("No Valid batches added to block, " +
                                    " dropping %s",
                                    candidate.identifier[:8])
                        return

                    block = BlockWrapper(candidate.build_block())
                    self._block_cache[block.identifier] = block  # add the
                    # block to the cache, so we can build on top of it.
                    self._block_sender.send(block.block)

                    LOGGER.info("Claimed Block: %s", block)

                    # create a new block based on this one -- opportunistically
                    # assume the published block is the valid block.
                    self.on_chain_updated(block)
        # pylint: disable=broad-except
        except Exception as exc:
            LOGGER.exception(exc)
            LOGGER.critical("BlockPublisher thread exited.")
