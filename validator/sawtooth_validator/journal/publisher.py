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

# pylint: disable=inconsistent-return-statements

import abc
from collections import deque
import logging
import queue
from threading import RLock
import time

from sawtooth_validator.concurrent.atomic import ConcurrentSet
from sawtooth_validator.concurrent.thread import InstrumentedThread
from sawtooth_validator.execution.scheduler_exceptions import SchedulerError

from sawtooth_validator.journal.block_builder import BlockBuilder
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.consensus.batch_publisher import \
    BatchPublisher
from sawtooth_validator.journal.consensus.consensus_factory import \
    ConsensusFactory
from sawtooth_validator.journal.validation_rule_enforcer import \
    enforce_validation_rules

from sawtooth_validator.journal.chain_commit_state import \
    TransactionCommitCache

from sawtooth_validator import metrics

from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_validator.state.settings_view import SettingsView

LOGGER = logging.getLogger(__name__)
COLLECTOR = metrics.get_collector(__name__)


NUM_PUBLISH_COUNT_SAMPLES = 5
INITIAL_PUBLISH_COUNT = 30


class ConsensusNotReady(Exception):
    """
    Consensus is not ready to build a block.
    """


class NoPendingBatchesRemaining(Exception):
    """There are no pending batches remaining."""


class FinalizeBlockResult:
    def __init__(self, block, remaining_batches, last_batch, injected_batches):
        self.block = block
        self.remaining_batches = remaining_batches
        self.last_batch = last_batch
        self.injected_batches = injected_batches


class PendingBatchObserver(metaclass=abc.ABCMeta):
    """An interface class for components wishing to be notified when a Batch
    has begun being processed.
    """

    @abc.abstractmethod
    def notify_batch_pending(self, batch):
        """This method will be called when a Batch has passed initial
        validation and is queued to be processed by the Publisher.

        Args:
            batch (Batch): The Batch that has been added to the Publisher
        """
        raise NotImplementedError('PendingBatchObservers must have a '
                                  '"notify_batch_pending" method')


class _PublisherThread(InstrumentedThread):
    def __init__(self, block_publisher, batch_queue,
                 check_publish_block_frequency):
        super().__init__(name='_PublisherThread')
        self._block_publisher = block_publisher
        self._batch_queue = batch_queue
        self._check_publish_block_frequency = \
            check_publish_block_frequency
        self._exit = False

    def run(self):
        try:
            # make sure we don't check to publish the block
            # to frequently.
            next_check_publish_block_time = time.time() + \
                self._check_publish_block_frequency
            while True:
                try:
                    batch = self._batch_queue.get(
                        timeout=self._check_publish_block_frequency)
                    self._block_publisher.on_batch_received(batch)
                except queue.Empty:
                    # If getting a batch times out, just try again.
                    pass

                if next_check_publish_block_time < time.time():
                    self._block_publisher.on_check_publish_block()
                    next_check_publish_block_time = time.time() + \
                        self._check_publish_block_frequency
                if self._exit:
                    return
        # pylint: disable=broad-except
        except Exception as exc:
            LOGGER.exception(exc)
            LOGGER.critical("BlockPublisher thread exited with error.")

    def stop(self):
        self._exit = True


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
                 max_batches,
                 batch_injectors,
                 settings_view,
                 identity_signer,
                 ):
        self._pending_batches = []
        self._pending_batch_ids = set()
        self._injected_batch_ids = set()
        self._block_store = block_store
        self._consensus = consensus
        self._scheduler = scheduler
        self._committed_txn_cache = committed_txn_cache
        # Look-up cache for transactions that are committed in the current
        # chain and the state of the transactions already added to the
        # candidate block.
        self._block_builder = block_builder
        self._max_batches = max_batches
        self._batch_injectors = batch_injectors

        self._settings_view = settings_view
        self._identity_signer = identity_signer

    def __del__(self):
        self.cancel()

    def cancel(self):
        self._scheduler.cancel()

    @property
    def previous_block_id(self):
        return self._block_builder.previous_block_id

    def _last_batch(self):
        if self._pending_batches:
            return self._pending_batches[-1]
        raise ValueError(
            'last_batch called on an empty block.'
            'Empty block publishing is not supported.'
        )

    @property
    def batches(self):
        return self._pending_batches.copy()

    def can_add_batch(self):
        return (
            self._max_batches == 0
            or len(self._pending_batches) < self._max_batches
        )

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
                LOGGER.debug(
                    "Transaction rejected as it is already in the chain %s",
                    txn.header_signature[:8])
                return False
            elif not self._check_transaction_dependencies(
                    txn, committed_txn_cache):
                # if any transaction in this batch fails the whole batch
                # fails.
                committed_txn_cache.remove_batch(batch)
                return False
            # update so any subsequent txn in the same batch can be dependent
            # on this transaction.
            committed_txn_cache.add(txn.header_signature)
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
                LOGGER.debug(
                    "Transaction rejected due missing dependency, "
                    "transaction %s depends on %s",
                    txn.header_signature, dep)
                return False
        return True

    def _is_batch_already_committed(self, batch):
        """ Test if a batch is already committed to the chain or
        is already in the pending queue.
        :param batch: the batch to check
        """
        return (self._block_store.has_batch(batch.header_signature)
                or batch.header_signature in self._pending_batch_ids)

    def _is_txn_already_committed(self, txn, committed_txn_cache):
        """ Test if a transaction is already committed to the chain or
        is already in the pending queue.
        """
        return (self._block_store.has_batch(txn.header_signature)
                or txn.header_signature in committed_txn_cache)

    def _poll_injectors(self, poller, batch_list):
        for injector in self._batch_injectors:
            inject = poller(injector)
            if inject:
                for b in inject:
                    self._injected_batch_ids.add(b.header_signature)
                    batch_list.append(b)

    def add_batch(self, batch):
        """Add a batch to the _CandidateBlock
        :param batch: the batch to add to the block
        """
        if batch.trace:
            LOGGER.debug("TRACE %s: %s", batch.header_signature,
                         self.__class__.__name__)

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
            batches_to_add = []

            # Inject batches at the beginning of the block
            if not self._pending_batches:
                self._poll_injectors(lambda injector: injector.block_start(
                    self._block_builder.previous_block_id), batches_to_add)

            batches_to_add.append(batch)

            if not enforce_validation_rules(
                    self._settings_view,
                    self._identity_signer.get_public_key().as_hex(),
                    self._pending_batches + batches_to_add):
                return

            for b in batches_to_add:
                self._pending_batches.append(b)
                self._pending_batch_ids.add(b.header_signature)
                try:
                    injected = b.header_signature in self._injected_batch_ids
                    self._scheduler.add_batch(b, required=injected)
                except SchedulerError as err:
                    LOGGER.debug("Scheduler error processing batch: %s", err)
        else:
            LOGGER.debug("Dropping batch due to missing dependencies: %s",
                         batch.header_signature)

    def _sign_block(self, block):
        """ The block should be complete and the final
        signature from the publishing validator(this validator) needs to
        be added.
        :param block: the Block to sign.
        :param identity_signer: the singer to sign the block with.
        """
        header_bytes = block.block_header.SerializeToString()
        signature = self._identity_signer.sign(header_bytes)
        block.set_signature(signature)

    def finalize(self, force=False):
        """Compose the final Block to publish. This involves flushing
        the scheduler, having consensus bless the block, and signing
        the block.
        :return: The generated Block, or None if Block failed to finalize.
        In both cases the pending_batches will contain the list of batches
        that need to be added to the next Block that is built.
        """
        if not (force or self._pending_batches):
            raise NoPendingBatchesRemaining()

        if not self._consensus.check_publish_block(
                self._block_builder.block_header):
            raise ConsensusNotReady()

        pending_batches = []

        self._scheduler.unschedule_incomplete_batches()
        self._scheduler.finalize()
        self._scheduler.complete(block=True)

        # this is a transaction cache to track the transactions committed
        # up to this batch. Only valid transactions that were processed
        # by the scheduler are added.
        committed_txn_cache = TransactionCommitCache(self._block_store)

        builder = self._block_builder
        bad_batches = []  # the list of batches that failed processing
        state_hash = None

        # Walk the pending batch list:
        # - find the state hash for the block, the block state_hash is
        # is randomly placed on one of the transactions, so must interogate
        # every batch to find it. If it is on a batch that failed processing
        # then this block will be abandoned.
        # - build three lists of batches:
        # 1) a lists of all valid transactions that will be included in the
        #   block, these are added to the BlockBuilder to include in the Block
        # 2) all batches that were not executed, these are to be returned
        #   in the pending_batches list
        # 3) all batches that failed processing. These will be discarded.
        #   This list is needed in some case when the block is abandoned to
        #   make sure they do not remain in the pending_batches list.
        for batch in self._pending_batches:
            if batch.trace:
                LOGGER.debug("TRACE %s: %s", batch.header_signature,
                             self.__class__.__name__)

            result = self._scheduler.get_batch_execution_result(
                batch.header_signature)
            # if a result is None, this means that the executor never
            # received the batch and it should be added to
            # the pending_batches, to be added to the next
            # block
            if result is None:
                # If this was an injected batch, don't keep it in pending
                # batches since it had to be in this block
                if batch.header_signature not in self._injected_batch_ids:
                    pending_batches.append(batch)
                else:
                    LOGGER.warning(
                        "Failed to inject batch '%s'", batch.header_signature)
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
                    LOGGER.debug("Abandoning block %s:"
                                 "root state hash has invalid txn applied",
                                 builder)
                    # Update the pending batch list to be all the
                    # batches that passed validation to this point and
                    # none of the ones that failed. It is possible that
                    # this batch caused a future batch to fail so
                    # we leave all of the batches that failed after this
                    # one in the list.
                    bad_batches.append(batch)
                    pending_batches.clear()
                    pending_batches.extend([
                        x for x in self._pending_batches
                        if x not in bad_batches
                    ])
                    return self._build_result(None, pending_batches)

                else:
                    builder.add_batch(batch)
                    committed_txn_cache.add_batch(batch)
                if result.state_hash is not None:
                    state_hash = result.state_hash
            else:
                bad_batches.append(batch)
                LOGGER.debug("Batch %s invalid, not added to block.",
                             batch.header_signature)

        if state_hash is None or not builder.batches:
            LOGGER.debug("Abandoning block %s: no batches added", builder)
            return self._build_result(None, pending_batches)

        if not self._consensus.finalize_block(builder.block_header):
            LOGGER.debug("Abandoning block %s, consensus failed to finalize "
                         "it", builder)
            # return all valid batches to the pending_batches list
            pending_batches.clear()
            pending_batches.extend([x for x in self._pending_batches
                                    if x not in bad_batches])
            return self._build_result(None, pending_batches)

        builder.set_state_hash(state_hash)
        self._sign_block(builder)
        return self._build_result(builder.build_block(), pending_batches)

    def _build_result(self, block, remaining):
        return FinalizeBlockResult(
            block=block,
            remaining_batches=remaining,
            last_batch=self._last_batch(),
            injected_batches=self._injected_batch_ids)


class _PublisherLoggingStates:
    """Collects and tracks the changes in various states of the Publisher.  For
    example it tracks 'consensus_ready', which denotes entering or exiting of
    that state."""
    def __init__(self, consensus_ready=True):
        self.consensus_ready = True


class BlockPublisher(object):
    """
    Responsible for generating new blocks and publishing them when the
    Consensus deems it appropriate.
    """

    def __init__(self,
                 transaction_executor,
                 block_cache,
                 state_view_factory,
                 settings_cache,
                 block_sender,
                 batch_sender,
                 squash_handler,
                 chain_head,
                 identity_signer,
                 data_dir,
                 config_dir,
                 permission_verifier,
                 check_publish_block_frequency,
                 batch_observers,
                 batch_injector_factory=None):
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
            identity_signer (:obj:`Signer`): Cryptographic signer for signing
                blocks
            data_dir (str): path to location where persistent data for the
                consensus module can be stored.
            config_dir (str): path to location where configuration can be
                found.
            batch_injector_factory (:obj:`BatchInjectorFatctory`): A factory
                for creating BatchInjectors.
        """
        self._lock = RLock()
        self._candidate_block = None  # _CandidateBlock helper,
        # the next block in potential chain
        self._block_cache = block_cache
        self._state_view_factory = state_view_factory
        self._settings_cache = settings_cache
        self._transaction_executor = transaction_executor
        self._block_sender = block_sender
        self._batch_publisher = BatchPublisher(identity_signer, batch_sender)
        self._pending_batches = PendingBatchesPool(
            NUM_PUBLISH_COUNT_SAMPLES, INITIAL_PUBLISH_COUNT)

        self._chain_head = chain_head  # block (BlockWrapper)
        self._squash_handler = squash_handler
        self._identity_signer = identity_signer
        self._data_dir = data_dir
        self._config_dir = config_dir
        self._permission_verifier = permission_verifier
        self._batch_injector_factory = batch_injector_factory

        # For metric gathering
        self._blocks_published_count = COLLECTOR.counter(
            'blocks_published_count', instance=self)

        self._batch_queue = IncomingBatchQueue()
        self._batch_observers = batch_observers
        self._check_publish_block_frequency = check_publish_block_frequency
        self._publisher_thread = None

        # A series of states that allow us to check for condition changes.
        # These can be used to log only at the boundary of condition changes.
        self._logging_states = _PublisherLoggingStates()

    def start(self):
        self._publisher_thread = _PublisherThread(
            block_publisher=self,
            batch_queue=self._batch_queue,
            check_publish_block_frequency=self._check_publish_block_frequency)
        self._publisher_thread.start()

    def stop(self):
        if self._publisher_thread is not None:
            self._publisher_thread.stop()
            self._publisher_thread = None

    def queue_batch(self, batch):
        """
        New batch has been received, queue it with the BlockPublisher for
        inclusion in the next block.
        """
        self._batch_queue.put(batch)
        for observer in self._batch_observers:
            observer.notify_batch_pending(batch)

    def pending_batch_info(self):
        """Returns a tuple of the current size of the pending batch queue
        and the current queue limit.
        """
        return (len(self._pending_batches), self._pending_batches.limit())

    @property
    def chain_head_lock(self):
        return self._lock

    def _load_consensus(self, block, state_view, public_key):
        """Load the configured consensus module's BlockPublisher to use for
        blocks built on this block."""
        consensus_module = ConsensusFactory.get_configured_consensus_module(
            block.header_signature,
            state_view)

        consensus = consensus_module.\
            BlockPublisher(block_cache=self._block_cache,
                           state_view_factory=self._state_view_factory,
                           batch_publisher=self._batch_publisher,
                           data_dir=self._data_dir,
                           config_dir=self._config_dir,
                           validator_id=public_key)

        return consensus

    def _load_injectors(self, block):
        if self._batch_injector_factory is not None:
            batch_injectors = self._batch_injector_factory.create_injectors(
                block.identifier)
            if batch_injectors:
                LOGGER.debug("Loaded batch injectors: %s", batch_injectors)
            return batch_injectors
        else:
            return []

    def initialize_block(self, previous_block):
        """Begin building a new candidate block.

        Args:
            previous_block (BlockWrapper): The block to base the new block on.

        Raises:
            ConsensusNotReady
                Consensus is not ready to build a block
        """

        # using previous_block so so we can use the setting_cache
        max_batches = int(self._settings_cache.get_setting(
            'sawtooth.publisher.max_batches_per_block',
            previous_block.state_root_hash,
            default_value=0))

        state_view = BlockWrapper.state_view_for_block(
            previous_block,
            self._state_view_factory)

        public_key = self._identity_signer.get_public_key().as_hex()
        consensus = self._load_consensus(
            previous_block, state_view, public_key)
        batch_injectors = self._load_injectors(previous_block)

        block_header = BlockHeader(
            block_num=previous_block.block_num + 1,
            previous_block_id=previous_block.header_signature,
            signer_public_key=public_key)
        block_builder = BlockBuilder(block_header)

        if not consensus.initialize_block(block_builder.block_header):
            raise ConsensusNotReady()

        # create a new scheduler
        scheduler = self._transaction_executor.create_scheduler(
            self._squash_handler, previous_block.state_root_hash)

        # build the TransactionCommitCache
        committed_txn_cache = TransactionCommitCache(
            self._block_cache.block_store)

        self._transaction_executor.execute(scheduler)
        self._candidate_block = _CandidateBlock(
            self._block_cache.block_store,
            consensus, scheduler,
            committed_txn_cache,
            block_builder,
            max_batches,
            batch_injectors,
            SettingsView(state_view),
            self._identity_signer)

        for batch in self._pending_batches:
            if self._candidate_block.can_add_batch():
                self._candidate_block.add_batch(batch)
            else:
                break

    def on_batch_received(self, batch):
        """
        A new batch is received, send it for validation
        :param batch: the new pending batch
        :return: None
        """
        with self._lock:
            if self._permission_verifier.is_batch_signer_authorized(batch):
                self._pending_batches.append(batch)
                # if we are building a block then send schedule it for
                # execution.
                if self._candidate_block and \
                        self._candidate_block.can_add_batch():
                    self._candidate_block.add_batch(batch)
            else:
                LOGGER.debug("Batch has an unauthorized signer. Batch: %s",
                             batch.header_signature)

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
                if chain_head is not None:
                    LOGGER.info('Now building on top of block: %s', chain_head)
                else:
                    LOGGER.info('Block publishing is suspended until new '
                                'chain head arrives.')

                self._chain_head = chain_head

                self.cancel_block()

                # we need to make a new _CandidateBlock (if we can) since the
                # block chain has updated under us.
                if chain_head is not None:
                    self._pending_batches.update_limit(len(chain_head.batches))
                    self._pending_batches.rebuild(
                        committed_batches, uncommitted_batches)

        # pylint: disable=broad-except
        except Exception:
            LOGGER.exception(
                "Unhandled exception in BlockPublisher.on_chain_updated")

    def cancel_block(self):
        if self._candidate_block:
            self._candidate_block.cancel()

        self._candidate_block = None

    def _building(self):
        """Returns whether the block publisher is in the process of building
        a block or not.
        """
        return self._candidate_block is not None

    def _can_build(self):
        """Returns whether the block publisher is ready to build a block.
        """
        return self._chain_head is not None and self._pending_batches

    def _log_consensus_state(self):
        if self._logging_states.consensus_ready:
            LOGGER.debug("Consensus is ready to build candidate block.")
            self._logging_states.consensus_ready = True
        else:
            self._logging_states.consensus_ready = False
            LOGGER.debug("Consensus not ready to build candidate block.")

    def on_check_publish_block(self, force=False):
        """Ask the consensus module if it is time to claim the candidate block
        if it is then, claim it and tell the world about it.
        :return:
            None
        """
        try:
            with self._lock:
                if not self._building() and self._can_build():
                    try:
                        self.initialize_block(self._chain_head)
                    except ConsensusNotReady:
                        self._log_consensus_state()

                if self._building():
                    try:
                        result = self.finalize_block(force)
                    except (ConsensusNotReady, NoPendingBatchesRemaining):
                        return

                    if result.block:
                        self.publish_block(
                            result.block, result.injected_batches)

        # pylint: disable=broad-except
        except Exception:
            LOGGER.exception(
                "Unhandled exception in BlockPublisher.on_check_publish_block")

    def finalize_block(self, force=False):
        result = self._candidate_block.finalize(force)

        self._candidate_block = None

        # Update the _pending_batches to reflect what we learned.
        self._pending_batches.update(
            result.remaining_batches,
            result.last_batch)

        return result

    def publish_block(self, block, injected_batches):
        blkw = BlockWrapper(block)
        LOGGER.info("Claimed Block: %s", blkw)
        self._block_sender.send(blkw.block, keep_batches=injected_batches)
        self._blocks_published_count.inc()

        # We built our candidate, disable processing until the chain head is
        # updated. Only set this if we succeeded. Otherwise try again, this can
        # happen in cases where txn dependencies did not validate when building
        # the block.
        self.on_chain_updated(None)

    def has_batch(self, batch_id):
        with self._lock:
            if batch_id in self._pending_batches:
                return True
            if batch_id in self._batch_queue:
                return True

        return False


class IncomingBatchQueue:
    """This queue keeps track of the batch ids so that components on the edge
    can filter out duplicates early. However, there is still an opportunity for
    duplicates to make it into this queue, which is intentional to avoid
    blocking threads trying to put/get from the queue. Any duplicates
    introduced by this must be filtered out later.
    """
    def __init__(self):
        self._queue = queue.Queue()
        self._ids = ConcurrentSet()

    def put(self, batch):
        if batch.header_signature not in self._ids:
            self._queue.put(batch)

    def get(self, timeout=None):
        batch = self._queue.get(timeout=timeout)
        try:
            self._ids.remove(batch.header_signature)
        except KeyError:
            pass
        return batch

    def __contains__(self, batch_id):
        return batch_id in self._ids


class PendingBatchesPool:

    def __init__(self, sample_size, initial_value):
        # Ordered batches waiting to be processed
        self._batches = list()
        self._ids = set()
        self._gauge = COLLECTOR.gauge('pending_batch_gauge', instance=self)
        self._limit = QueueLimit(sample_size, initial_value)

    def __len__(self):
        return len(self._batches)

    def __iter__(self):
        return iter(self._batches)

    def __contains__(self, batch_id):
        return batch_id in self._ids

    def _reset(self):
        self._batches = list()
        self._ids = set()

    def append(self, batch):
        self._append(batch)
        self._update_gauge()

    def _append(self, batch):
        if batch.header_signature not in self._ids:
            self._batches.append(batch)
            self._ids.add(batch.header_signature)

    def rebuild(self, committed=None, uncommitted=None):
        """Recomputes the list of pending batches

        Args:
            committed (List<Batches>): Batches committed in the current chain
                since the root of the fork switching from.
            uncommitted (List<Batches): Batches that were committed in the old
                fork since the common root.
        """
        if committed is None:
            committed = []
        if uncommitted is None:
            uncommitted = []

        committed_set = set(b.header_signature for b in committed)

        previous_batches = self._batches

        self._reset()

        # Uncommitted and pending are disjoint sets since batches can only be
        # committed to a chain once.
        for batch in uncommitted:
            if batch.header_signature not in committed_set:
                self._append(batch)

        for batch in previous_batches:
            if batch.header_signature not in committed_set:
                self._append(batch)

        self._update_gauge()

    def update(self, still_pending, last_sent):
        last_index = self._batches.index(last_sent)
        unsent = self._batches[last_index + 1:]
        self._reset()
        for batch in still_pending + unsent:
            self._append(batch)

        self._update_gauge()

    def update_limit(self, consumed):
        self._limit.update(len(self._batches), consumed)

    def limit(self):
        return self._limit.get()

    def _update_gauge(self):
        self._gauge.set_value(len(self._batches))


class QueueLimit:
    def __init__(self, sample_size, initial_value):
        self._avg = _RollingAverage(sample_size, initial_value)

    def update(self, queue_length, consumed):
        """Use the current queue size and the number of items consumed to
        update the queue limit, if there was a significant enough change.

        Args:
            queue_length (int): the current size of the queue
            consumed (int): the number items consumed
        """
        if consumed > 0:
            # Only update the average if either:
            # a. Not drained below the current average
            # b. Drained the queue, but the queue was not bigger than the
            #    current running average
            remainder = queue_length - consumed
            if remainder > self._avg.value or consumed > self._avg.value:
                self._avg.update(consumed)

    def get(self):
        # Limit the number of items to 2 times the publishing average.  This
        # allows the queue to grow geometrically, if the queue is drained.
        return 2 * self._avg.value


class _RollingAverage(object):

    def __init__(self, sample_size, initial_value):
        self._samples = deque(maxlen=sample_size)

        self._samples.append(initial_value)
        self._current_average = initial_value

    @property
    def value(self):
        return self._current_average

    def update(self, sample):
        """Add the sample and return the updated average.
        """
        self._samples.append(sample)

        self._current_average = sum(self._samples) / len(self._samples)

        return self._current_average
