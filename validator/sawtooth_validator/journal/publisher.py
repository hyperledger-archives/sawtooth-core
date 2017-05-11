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

import sawtooth_signing as signing

from sawtooth_validator.execution.scheduler_exceptions import SchedulerError

from sawtooth_validator.journal.block_builder import BlockBuilder
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.consensus.batch_publisher import \
    BatchPublisher
from sawtooth_validator.journal.consensus.consensus_factory import \
    ConsensusFactory

from sawtooth_validator.journal.transaction_cache import TransactionCache


from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_validator.state.config_view import ConfigView

LOGGER = logging.getLogger(__name__)


class _CandidateBlock(object):
    """This is a helper class for the BlockPublisher. The _CandidateBlock
    tracks all the state associated with the Block that is being built.
    This allows the BlockPublisher to focus on when to create and finalize
    a block and not worry about how the block is built.
    """
    def __init__(self,
                 block_store,
                 consensus,
                 scheduler,
                 committed_txn_cache,
                 block_builder,
                 max_batches
                 ):
        self._pending_batches = []
        self._pending_batch_ids = set()
        self._block_store = block_store
        self._consensus = consensus
        self._scheduler = scheduler
        self._committed_txn_cache = committed_txn_cache
        # Look-up cache for transactions that are committed in the current
        # chain and the state of the transactions already added to the
        # candidate block.
        self._block_builder = block_builder
        self._max_batches = max_batches

    def __del__(self):
        # Cancel the scheduler if it is not complete
        if not self._scheduler.complete(block=False):
            self._scheduler.cancel()

    @property
    def previous_block_id(self):
        return self._block_builder.previous_block_id

    @property
    def last_batch(self):
        if self._pending_batches:
            return self._pending_batches[-1]
        return None

    @property
    def can_add_batch(self):
        return self._max_batches == 0 or\
            len(self._pending_batches) < self._max_batches

    def _check_batch_dependencies(self, batch, committed_txn_cache):
        """Check the dependencies for all transactions in this are present.
        If all are present the committed_txn is updated with all txn in this
        batch and True is returned. If they are not return failure and the
        committed_txn is not updated.
        :param batch: the batch to validate
        :param committed_txn_cache: The cache holding the set of committed
        transactions to check against, updated during processing.
        :return: Boolean, True if dependencies checkout, False otherwise.
        """
        for txn in batch.transactions:
            if self._is_txn_already_committed(txn, committed_txn_cache):
                LOGGER.debug("Transaction rejected as it " +
                             "is already in the chain " +
                             "%s", txn.header_signature[:8])
                return False
            elif not self._check_transaction_dependencies(
                    txn,
                    committed_txn_cache):
                # if any transaction in this batch fails the whole batch
                # fails.
                committed_txn_cache.remove_batch(batch)
                return False
            # update so any subsequent txn in the same batch can be dependent
            # on this transaction.
            committed_txn_cache.add_txn(txn.header_signature)
        return True

    def _check_transaction_dependencies(self, txn, committed_txn_cache):
        """Check that all this transactions dependencies are present.
        :param txn: the transaction to check
        :param committed_txn_cache: The cache holding the set of committed
        transactions to check against.
        :return: Boolean, True if dependencies checkout, False otherwise.
        """
        txn_hdr = TransactionHeader()
        txn_hdr.ParseFromString(txn.header)
        for dep in txn_hdr.dependencies:
            if dep not in committed_txn_cache:
                LOGGER.debug("Transaction rejected due " +
                             "missing dependency, transaction " +
                             "%s depends on %s", txn.header_signature, dep)
                return False
        return True

    def _is_batch_already_committed(self, batch):
        """ Test if a batch is already committed to the chain or
        is already in the pending queue.
        :param batch: the batch to check
        """
        return (self._block_store.has_batch(batch.header_signature) or
                batch.header_signature in self._pending_batch_ids)

    def _is_txn_already_committed(self, txn, committed_txn_cache):
        """ Test if a transaction is already committed to the chain or
        is already in the pending queue.
        """
        return (self._block_store.has_batch(txn.header_signature) or
                txn.header_signature in committed_txn_cache)

    def add_batch(self, batch):
        """Add a batch to the _CandidateBlock
        :param batch: the batch to add to the block
        """
        # first we check if the transaction dependencies are satisfied
        # The completer should have taken care of making sure all
        # Batches containing dependent transactions were sent to the
        # BlockPublisher prior to this Batch. So if there is a missing
        # dependency this is an error condition and the batch will be
        # dropped.
        if self._is_batch_already_committed(batch):
            # batch is already committed.
            LOGGER.debug("Dropping previously committed batch: %s",
                         batch.header_signature)
            return
        elif self._check_batch_dependencies(batch, self._committed_txn_cache):
            self._pending_batches.append(batch)
            self._pending_batch_ids.add(batch.header_signature)
            try:
                self._scheduler.add_batch(batch)
            except SchedulerError as err:
                LOGGER.debug("Scheduler error processing batch: %s", err)
        else:
            LOGGER.debug("Dropping batch due to missing dependencies: %s",
                         batch.header_signature)

    def check_publish_block(self):
        """Check if it is okay to publish this candidate.
        """
        return self._consensus.check_publish_block(
            self._block_builder.block_header)

    def _sign_block(self, block, identity_signing_key):
        """ The block should be complete and the final
        signature from the publishing validator(this validator) needs to
        be added.
        :param block: the Block to sign.
        :param identity_signing_key: the key to sign the block with.
        """
        header_bytes = block.block_header.SerializeToString()
        signature = signing.sign(header_bytes, identity_signing_key)
        block.set_signature(signature)

    def finalize_block(self, identity_signing_key, pending_batches):
        """Compose the final Block to publish. This involves flushing
        the scheduler, having consensus bless the block, and signing
        the block.
        :param identity_signing_key: the key to sign the block with.
        :param pending_batches: list to receive any batches that were
        submitted to add to the block but were not validated before this
        call.
        """
        self._scheduler.finalize()
        self._scheduler.complete(block=True)

        # this is a transaction cache to track the transactions committed
        # up to this batch. Only valid transactions that were processed
        # by the scheduler are added.
        committed_txn_cache = TransactionCache(self._block_store)

        builder = self._block_builder
        state_hash = None
        for batch in self._pending_batches:
            result = self._scheduler.get_batch_execution_result(
                batch.header_signature)
            # if a result is None, this means that the executor never
            # received the batch and it should be added to
            # the pending_batches, to be added to the next
            # block
            if result is None:
                pending_batches.append(batch)
            elif result.is_valid:
                # check if a dependent batch failed. This could be belt and
                # suspenders action here but it is logically possible that
                # a transaction has a dependency that fails it could
                # still succeed validation. In which case we do not want
                # to add it to the batch.
                if not self._check_batch_dependencies(batch,
                                                      committed_txn_cache):
                    LOGGER.debug("Batch %s invalid, due to missing txn "
                                 "dependency.", batch.header_signature)
                    LOGGER.debug("Abandoning block %s:" +
                                 "root state hash has invalid txn applied",
                                 builder)
                    return None
                else:
                    builder.add_batch(batch)
                    committed_txn_cache.add_batch(batch)
                if result.state_hash is not None:
                    state_hash = result.state_hash
            else:
                LOGGER.debug("Batch %s invalid, not added to block.",
                             batch.header_signature)

        if state_hash is None:
            LOGGER.debug("Abandoning block %s no batches added", builder)
            return None

        if not self._consensus.finalize_block(builder.block_header):
            LOGGER.debug("Abandoning block %s, consensus failed to finalize "
                         "it", builder)
            return False

        builder.set_state_hash(state_hash)
        self._sign_block(builder, identity_signing_key)
        return builder.build_block()


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
                 batch_sender,
                 squash_handler,
                 chain_head,
                 identity_signing_key,
                 data_dir):
        """
        Initialize the BlockPublisher object

        Args:
            transaction_executor (:obj:`TransactionExecutor`): A
                TransactionExecutor instance.
            block_cache (:obj:`BlockCache`): A BlockCache instance.
            state_view_factory (:obj:`StateViewFactory`): StateViewFactory for
                read-only state views.
            block_sender (:obj:`BlockSender`): The BlockSender instance.
            batch_sender (:obj:`BatchSender`): The BatchSender instance.
            squash_handler (function): Squash handler function for merging
                contexts.
            chain_head (:obj:`BlockWrapper`): The initial chain head.
            identity_signing_key (str): Private key for signing blocks
            data_dir (str): path to location where persistent data for the
             consensus module can be stored.
        """
        self._lock = RLock()
        self._candidate_block = None  # _CandidateBlock helper,
        # the next block in potential chain
        self._block_cache = block_cache
        self._state_view_factory = state_view_factory
        self._transaction_executor = transaction_executor
        self._block_sender = block_sender
        self._batch_publisher = BatchPublisher(identity_signing_key,
                                               batch_sender)
        self._pending_batches = []  # batches we are waiting for validation,
        # arranged in the order of batches received.

        self._chain_head = chain_head  # block (BlockWrapper)
        self._squash_handler = squash_handler
        self._identity_signing_key = identity_signing_key
        self._identity_public_key = \
            signing.generate_pubkey(self._identity_signing_key)
        self._data_dir = data_dir

    @property
    def chain_head_lock(self):
        return self._lock

    def _build_candidate_block(self, chain_head):
        """ Build a candidate block and construct the consensus object to
        validate it.
        :param chain_head: The block to build on top of.
        :return: (BlockBuilder) - The candidate block in a BlockBuilder
        wrapper.
        """
        state_view = BlockWrapper.state_view_for_block(
            chain_head,
            self._state_view_factory)
        consensus_module = ConsensusFactory.get_configured_consensus_module(
            chain_head.header_signature,
            state_view)

        config_view = ConfigView(state_view)
        max_batches = config_view.get_setting(
            'sawtooth.publisher.max_batches_per_block',
            default_value=0, value_type=int)

        consensus = consensus_module.\
            BlockPublisher(block_cache=self._block_cache,
                           state_view_factory=self._state_view_factory,
                           batch_publisher=self._batch_publisher,
                           data_dir=self._data_dir,
                           validator_id=self._identity_public_key)

        block_header = BlockHeader(
            block_num=chain_head.block_num + 1,
            previous_block_id=chain_head.header_signature,
            signer_pubkey=self._identity_public_key)
        block_builder = BlockBuilder(block_header)
        if not consensus.initialize_block(block_builder.block_header):
            LOGGER.debug("Consensus not ready to build candidate block.")
            return None

        # create a new scheduler
        scheduler = self._transaction_executor.create_scheduler(
            self._squash_handler, chain_head.state_root_hash)

        # build the TransactionCache
        committed_txn_cache = TransactionCache(self._block_cache.block_store)

        self._transaction_executor.execute(scheduler)
        self._candidate_block = _CandidateBlock(self._block_cache.block_store,
                                                consensus, scheduler,
                                                committed_txn_cache,
                                                block_builder,
                                                max_batches)
        for batch in self._pending_batches:
            if self._candidate_block.can_add_batch:
                self._candidate_block.add_batch(batch)
            else:
                break

    def on_batch_received(self, batch):
        """
        A new batch is received, send it for validation
        :param batch: the new pending batch
        :return: None
        """
        self._pending_batches.append(batch)
        # if we are building a block then send schedule it for
        # execution.
        if self._candidate_block and self._candidate_block.can_add_batch:
            self._candidate_block.add_batch(batch)

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
                self._pending_batches.append(batch)

        for batch in pending_batches:
            if batch.header_signature not in committed_set:
                self._pending_batches.append(batch)

    def on_chain_updated(self, chain_head,
                         committed_batches=None,
                         uncommitted_batches=None):
        """
        The existing chain has been updated, the current head block has
        changed.

        :param chain_head: the new head of block_chain, can be None if
        no block publishing is desired.
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

                self._candidate_block = None  # we need to make a new
                # _CandidateBlock (if we can) since the block chain has updated
                # under us.
                if chain_head is not None:
                    self._rebuild_pending_batches(committed_batches,
                                                  uncommitted_batches)
                    self._build_candidate_block(chain_head)

        # pylint: disable=broad-except
        except Exception as exc:
            LOGGER.critical("on_chain_updated exception.")
            LOGGER.exception(exc)

    def on_check_publish_block(self, force=False):
        """Ask the consensus module if it is time to claim the candidate block
        if it is then, claim it and tell the world about it.
        :return:
            None
        """
        try:
            with self._lock:
                if self._chain_head is not None and\
                        self._candidate_block is None and\
                        self._pending_batches:
                    self._build_candidate_block(self._chain_head)

                if self._candidate_block and \
                        (force or self._pending_batches) and \
                        self._candidate_block.check_publish_block():

                    pending_batches = []  # will receive the list of batches
                    # that were not added to the block
                    last_batch = self._candidate_block.last_batch
                    block = self._candidate_block.finalize_block(
                        self._identity_signing_key,
                        pending_batches)
                    self._candidate_block = None
                    if block:
                        blkw = BlockWrapper(block)
                        LOGGER.info("Claimed Block: %s", blkw)
                        self._block_sender.send(blkw.block)

                        # check if we have batches that were not
                        # sent to the CandidateBlock.
                        last_batch_index =\
                            self._pending_batches.index(last_batch)
                        additional_batches =\
                            self._pending_batches[last_batch_index + 1:]

                        self._pending_batches =\
                            pending_batches + additional_batches

                        # We built our candidate, disable processing until
                        # the chain head is updated. Only set this if
                        # we succeeded. Otherwise try again, this
                        # can happen in cases where txn dependencies
                        # did not validate when building the block.
                        self.on_chain_updated(None)

        # pylint: disable=broad-except
        except Exception as exc:
            LOGGER.critical("on_check_publish_block exception.")
            LOGGER.exception(exc)
