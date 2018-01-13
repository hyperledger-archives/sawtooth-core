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
from sawtooth_validator.concurrent.threadpool import \
    InstrumentedThreadPoolExecutor
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.consensus.consensus_factory import \
    ConsensusFactory
from sawtooth_validator.journal.chain_commit_state import ChainCommitState
from sawtooth_validator.journal.validation_rule_enforcer import \
    ValidationRuleEnforcer
from sawtooth_validator.state.settings_view import SettingsViewFactory
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.transaction_receipt_pb2 import \
    TransactionReceipt
from sawtooth_validator.metrics.wrappers import CounterWrapper
from sawtooth_validator.metrics.wrappers import GaugeWrapper

from sawtooth_validator.state.merkle import INIT_ROOT_KEY


LOGGER = logging.getLogger(__name__)


class BlockValidationAborted(Exception):
    """
    Indication that the validation of this fork has terminated for an
    expected(handled) case and that the processing should exit.
    """
    pass


class ChainHeadUpdated(Exception):
    """ Raised when a chain head changed event is detected and we need to abort
    processing and restart processing with the new chain head.
    """


class InvalidBatch(Exception):
    """ Raised when a batch fails validation as a signal to reject the
    block.
    """
    pass


# pylint: disable=stop-iteration-return
def look_ahead(iterable):
    """Pass through all values from the given iterable, augmented by the
    information if there are more values to come after the current one
    (True), or if it is the last value (False).
    """
    # Get an iterator and pull the first value.
    it = iter(iterable)
    last = next(it)
    # Run the iterator to exhaustion (starting from the second value).
    for val in it:
        # Report the *previous* value (more to come).
        yield last, True
        last = val
    # Report the last value.
    yield last, False


class BlockValidator(object):
    """
    Responsible for validating a block, handles both chain extensions and fork
    will determine if the new block should be the head of the chain and return
    the information necessary to do the switch if necessary.
    """

    def __init__(self,
                 consensus_module,
                 block_cache,
                 new_block,
                 state_view_factory,
                 done_cb,
                 executor,
                 squash_handler,
                 identity_signer,
                 data_dir,
                 config_dir,
                 permission_verifier,
                 metrics_registry=None):
        """Initialize the BlockValidator
        Args:
             consensus_module: The consensus module that contains
             implementation of the consensus algorithm to use for block
             validation.
             block_cache: The cache of all recent blocks and the processing
             state associated with them.
             new_block: The block to validate.
             state_view_factory: The factory object to create.
             done_cb: The method to call when block validation completed
             executor: The thread pool to process block validations.
             squash_handler: A parameter passed when creating transaction
             schedulers.
             identity_signer: A cryptographic signer for signing blocks.
             data_dir: Path to location where persistent data for the
             consensus module can be stored.
             config_dir: Path to location where config data for the
             consensus module can be found.
        Returns:
            None
        """
        self._consensus_module = consensus_module
        self._block_cache = block_cache
        self._chain_commit_state = ChainCommitState(
            self._block_cache.block_store, [])
        self._new_block = new_block

        # Set during execution of the of the  BlockValidation to the current
        # chain_head at that time.
        self._chain_head = None

        self._state_view_factory = state_view_factory
        self._done_cb = done_cb
        self._executor = executor
        self._squash_handler = squash_handler
        self._identity_signer = identity_signer
        self._data_dir = data_dir
        self._config_dir = config_dir
        self._result = {
            'new_block': new_block,
            'chain_head': None,
            'new_chain': [],
            'cur_chain': [],
            'committed_batches': [],
            'uncommitted_batches': [],
            'num_transactions': 0
        }
        self._permission_verifier = permission_verifier

        self._validation_rule_enforcer = \
            ValidationRuleEnforcer(SettingsViewFactory(state_view_factory))

        if metrics_registry:
            self._moved_to_fork_count = CounterWrapper(
                metrics_registry.counter('chain_head_moved_to_fork_count'))
        else:
            self._moved_to_fork_count = CounterWrapper()

    def _get_previous_block_root_state_hash(self, blkw):
        if blkw.previous_block_id == NULL_BLOCK_IDENTIFIER:
            return INIT_ROOT_KEY

        return self._block_cache[blkw.previous_block_id].state_root_hash

    def _txn_header(self, txn):
        txn_hdr = TransactionHeader()
        txn_hdr.ParseFromString(txn.header)
        return txn_hdr

    def _verify_batch_transactions(self, batch):
        """Verify that all transactions in are unique and that all
        transactions dependencies in this batch have been satisfied, ie
        already committed by this block or prior block in the chain.

        :param batch: the batch to verify
        :return:
        Boolean: True if all dependencies are present and all transactions
        are unique.
        """
        for txn in batch.transactions:
            txn_hdr = self._txn_header(txn)
            if self._chain_commit_state.has_transaction(txn.header_signature):
                LOGGER.debug(
                    "Block rejected due to duplicate"
                    " transaction, transaction: %s",
                    txn.header_signature[:8])
                raise InvalidBatch()
            for dep in txn_hdr.dependencies:
                if not self._chain_commit_state.has_transaction(dep):
                    LOGGER.debug(
                        "Block rejected due to missing "
                        "transaction dependency, transaction %s "
                        "depends on %s",
                        txn.header_signature[:8],
                        dep[:8])
                    raise InvalidBatch()
            self._chain_commit_state.add_txn(txn.header_signature)

    def _verify_block_batches(self, blkw):
        if blkw.block.batches:
            prev_state = self._get_previous_block_root_state_hash(blkw)
            scheduler = self._executor.create_scheduler(
                self._squash_handler, prev_state)
            self._executor.execute(scheduler)
            try:
                for batch, has_more in look_ahead(blkw.block.batches):
                    if self._chain_commit_state.has_batch(
                            batch.header_signature):
                        LOGGER.debug("Block(%s) rejected due to duplicate "
                                     "batch, batch: %s", blkw,
                                     batch.header_signature[:8])
                        raise InvalidBatch()

                    self._verify_batch_transactions(batch)
                    self._chain_commit_state.add_batch(
                        batch, add_transactions=False)
                    if has_more:
                        scheduler.add_batch(batch)
                    else:
                        scheduler.add_batch(batch, blkw.state_root_hash)
            except InvalidBatch:
                LOGGER.debug("Invalid batch %s encountered during "
                             "verification of block %s",
                             batch.header_signature[:8],
                             blkw)
                scheduler.cancel()
                return False
            except Exception:
                scheduler.cancel()
                raise

            scheduler.finalize()
            scheduler.complete(block=True)
            state_hash = None

            for batch in blkw.batches:
                batch_result = scheduler.get_batch_execution_result(
                    batch.header_signature)
                if batch_result is not None and batch_result.is_valid:
                    txn_results = \
                        scheduler.get_transaction_execution_results(
                            batch.header_signature)
                    blkw.execution_results.extend(txn_results)
                    state_hash = batch_result.state_hash
                    blkw.num_transactions += len(batch.transactions)
                else:
                    return False
            if blkw.state_root_hash != state_hash:
                LOGGER.debug("Block(%s) rejected due to state root hash "
                             "mismatch: %s != %s", blkw, blkw.state_root_hash,
                             state_hash)
                return False
        return True

    def _validate_permissions(self, blkw):
        """
        Validate that all of the batch signers and transaction signer for the
        batches in the block are permitted by the transactor permissioning
        roles stored in state as of the previous block. If a transactor is
        found to not be permitted, the block is invalid.
        """
        if blkw.block_num != 0:
            try:
                state_root = self._get_previous_block_root_state_hash(blkw)
            except KeyError:
                LOGGER.info(
                    "Block rejected due to missing predecessor: %s", blkw)
                return False

            for batch in blkw.batches:
                if not self._permission_verifier.is_batch_signer_authorized(
                        batch, state_root):
                    return False
        return True

    def _validate_on_chain_rules(self, blkw):
        """
        Validate that the block conforms to all validation rules stored in
        state. If the block breaks any of the stored rules, the block is
        invalid.
        """
        if blkw.block_num != 0:
            try:
                state_root = self._get_previous_block_root_state_hash(blkw)
            except KeyError:
                LOGGER.debug(
                    "Block rejected due to missing" + " predecessor: %s", blkw)
                return False
            return self._validation_rule_enforcer.validate(blkw, state_root)
        return True

    def validate_block(self, blkw):
        # pylint: disable=broad-except
        try:
            if blkw.status == BlockStatus.Valid:
                return True
            elif blkw.status == BlockStatus.Invalid:
                return False
            else:
                valid = True

                valid = self._validate_permissions(blkw)

                if valid:
                    public_key = \
                        self._identity_signer.get_public_key().as_hex()
                    consensus = self._consensus_module.BlockVerifier(
                        block_cache=self._block_cache,
                        state_view_factory=self._state_view_factory,
                        data_dir=self._data_dir,
                        config_dir=self._config_dir,
                        validator_id=public_key)
                    valid = consensus.verify_block(blkw)

                if valid:
                    valid = self._validate_on_chain_rules(blkw)

                if valid:
                    valid = self._verify_block_batches(blkw)

                # since changes to the chain-head can change the state of the
                # blocks in BlockStore we have to revalidate this block.
                block_store = self._block_cache.block_store
                if (self._chain_head is not None
                        and self._chain_head.identifier !=
                        block_store.chain_head.identifier):
                    raise ChainHeadUpdated()

                blkw.status = \
                    BlockStatus.Valid if valid else BlockStatus.Invalid

                return valid
        except ChainHeadUpdated as chu:
            raise chu
        except Exception:
            LOGGER.exception(
                "Unhandled exception BlockPublisher.validate_block()")
            return False

    def _find_common_height(self, new_chain, cur_chain):
        """
        Walk back on the longest chain until we find a predecessor that is the
        same height as the other chain.
        The blocks are recorded in the corresponding lists
        and the blocks at the same height are returned
        """
        new_blkw = self._new_block
        cur_blkw = self._chain_head
        # 1) find the common ancestor of this block in the current chain
        # Walk back until we have both chains at the same length

        # Walk back the new chain to find the block that is the
        # same height as the current head.
        if new_blkw.block_num > cur_blkw.block_num:
            # new chain is longer
            # walk the current chain back until we find the block that is the
            # same height as the current chain.
            while new_blkw.block_num > cur_blkw.block_num and \
                    new_blkw.previous_block_id != NULL_BLOCK_IDENTIFIER:
                new_chain.append(new_blkw)
                try:
                    new_blkw = self._block_cache[new_blkw.previous_block_id]
                except KeyError:
                    LOGGER.info(
                        "Block %s rejected due to missing predecessor %s",
                        new_blkw,
                        new_blkw.previous_block_id)
                    for b in new_chain:
                        b.status = BlockStatus.Invalid
                    raise BlockValidationAborted()
        elif new_blkw.block_num < cur_blkw.block_num:
            # current chain is longer
            # walk the current chain back until we find the block that is the
            # same height as the new chain.
            while (cur_blkw.block_num > new_blkw.block_num
                   and new_blkw.previous_block_id != NULL_BLOCK_IDENTIFIER):
                cur_chain.append(cur_blkw)
                cur_blkw = self._block_cache[cur_blkw.previous_block_id]
        return (new_blkw, cur_blkw)

    def _find_common_ancestor(self, new_blkw, cur_blkw, new_chain, cur_chain):
        """ Finds a common ancestor of the two chains.
        """
        while cur_blkw.identifier != new_blkw.identifier:
            if (cur_blkw.previous_block_id == NULL_BLOCK_IDENTIFIER
                    or new_blkw.previous_block_id == NULL_BLOCK_IDENTIFIER):
                # We are at a genesis block and the blocks are not the same
                LOGGER.info(
                    "Block rejected due to wrong genesis: %s %s",
                    cur_blkw, new_blkw)
                for b in new_chain:
                    b.status = BlockStatus.Invalid
                raise BlockValidationAborted()
            new_chain.append(new_blkw)
            try:
                new_blkw = self._block_cache[new_blkw.previous_block_id]
            except KeyError:
                LOGGER.info(
                    "Block %s rejected due to missing predecessor %s",
                    new_blkw,
                    new_blkw.previous_block_id)
                for b in new_chain:
                    b.status = BlockStatus.Invalid
                raise BlockValidationAborted()

            cur_chain.append(cur_blkw)
            cur_blkw = self._block_cache[cur_blkw.previous_block_id]

    def _test_commit_new_chain(self):
        """ Compare the two chains and determine which should be the head.
        """
        public_key = self._identity_signer.get_public_key().as_hex()
        fork_resolver = \
            self._consensus_module.ForkResolver(
                block_cache=self._block_cache,
                state_view_factory=self._state_view_factory,
                data_dir=self._data_dir,
                config_dir=self._config_dir,
                validator_id=public_key)

        return fork_resolver.compare_forks(self._chain_head, self._new_block)

    def _compute_batch_change(self, new_chain, cur_chain):
        """
        Compute the batch change sets.
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

    def run(self):
        """
        Main entry for Block Validation, Take a given candidate block
        and decide if it is valid then if it is valid determine if it should
        be the new head block. Returns the results to the ChainController
        so that the change over can be made if necessary.
        """
        try:
            LOGGER.info("Starting block validation of : %s", self._new_block)
            cur_chain = self._result["cur_chain"]  # ordered list of the
            # current chain blocks
            new_chain = self._result["new_chain"]  # ordered list of the new
            # chain blocks

            # get the current chain_head.
            self._chain_head = self._block_cache.block_store.chain_head
            self._result['chain_head'] = self._chain_head

            # 1) Find the common ancestor block, the root of the fork.
            # walk back till both chains are the same height
            (new_blkw, cur_blkw) = self._find_common_height(new_chain,
                                                            cur_chain)

            # 2) Walk back until we find the common ancestor
            self._find_common_ancestor(new_blkw, cur_blkw,
                                       new_chain, cur_chain)

            # 3) Determine the validity of the new fork
            # build the transaction cache to simulate the state of the
            # chain at the common root.
            self._chain_commit_state = ChainCommitState(
                self._block_cache.block_store, cur_chain)

            valid = True
            for block in reversed(new_chain):
                if valid:
                    if not self.validate_block(block):
                        LOGGER.info("Block validation failed: %s", block)
                        valid = False
                    self._result["num_transactions"] += block.num_transactions
                else:
                    LOGGER.info(
                        "Block marked invalid (invalid predecessor): %s",
                        block)
                    block.status = BlockStatus.Invalid

            if not valid:
                self._done_cb(False, self._result)
                return

            # 4) Evaluate the 2 chains to see if the new chain should be
            # committed
            LOGGER.info(
                "Comparing current chain head '%s' against new block '%s'",
                self._chain_head, self._new_block)
            for i in range(max(len(new_chain), len(cur_chain))):
                cur = new = num = "-"
                if i < len(cur_chain):
                    cur = cur_chain[i].header_signature[:8]
                    num = cur_chain[i].block_num
                if i < len(new_chain):
                    new = new_chain[i].header_signature[:8]
                    num = new_chain[i].block_num
                LOGGER.info(
                    "Fork comparison at height %s is between %s and %s",
                    num, cur, new)

            commit_new_chain = self._test_commit_new_chain()

            # 5) Consensus to compute batch sets (only if we are switching).
            if commit_new_chain:
                (self._result["committed_batches"],
                 self._result["uncommitted_batches"]) = \
                    self._compute_batch_change(new_chain, cur_chain)

                if new_chain[0].previous_block_id != \
                        self._chain_head.identifier:
                    self._moved_to_fork_count.inc()

            # 6) Tell the journal we are done.
            self._done_cb(commit_new_chain, self._result)

            LOGGER.info(
                "Finished block validation of: %s",
                self._new_block)
        except BlockValidationAborted:
            self._done_cb(False, self._result)
            return
        except ChainHeadUpdated:
            self._done_cb(False, self._result)
            return
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(
                "Block validation failed with unexpected error: %s",
                self._new_block)
            # callback to clean up the block out of the processing list.
            self._done_cb(False, self._result)


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
                 identity_signer,
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
            identity_signer: Private key for signing blocks.
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
        self._identity_signer = identity_signer
        self._data_dir = data_dir
        self._config_dir = config_dir

        self._blocks_processing = {}  # a set of blocks that are
        # currently being processed.
        self._blocks_pending = {}  # set of blocks that the previous block
        # is being processed. Once that completes this block will be
        # scheduled for validation.
        self._chain_id_manager = chain_id_manager

        self._chain_head = None

        self._permission_verifier = permission_verifier
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
        self._thread_pool = (
            InstrumentedThreadPoolExecutor(1)
            if thread_pool is None else thread_pool
        )
        self._chain_thread = None

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
                done_cb=self.on_block_validated,
                executor=self._transaction_executor,
                squash_handler=self._squash_handler,
                identity_signer=self._identity_signer,
                data_dir=self._data_dir,
                config_dir=self._config_dir,
                permission_verifier=self._permission_verifier,
                metrics_registry=self._metrics_registry)
            self._blocks_processing[blkw.block.header_signature] = validator
            self._thread_pool.submit(validator.run)

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
                new_block = result["new_block"]

                # remove from the processing list
                del self._blocks_processing[new_block.identifier]

                # Remove this block from the pending queue, obtaining any
                # immediate descendants of this block in the process.
                descendant_blocks = \
                    self._blocks_pending.pop(new_block.identifier, [])

                # if the head has changed, since we started the work.
                if result["chain_head"].identifier != \
                        self._chain_head.identifier:
                    LOGGER.info(
                        'Chain head updated from %s to %s while processing '
                        'block: %s',
                        result["chain_head"],
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
                        self._block_store.update_chain(result["new_chain"],
                                                       result["cur_chain"])

                        # make sure old chain is in the block_caches
                        self._block_cache.add_chain(result["cur_chain"])

                        LOGGER.info(
                            "Chain head updated to: %s",
                            self._chain_head)

                        self._chain_head_gauge.set_value(
                            self._chain_head.identifier[:8])

                        self._committed_transactions_count.inc(
                            result["num_transactions"])

                        self._block_num_gauge.set_value(
                            self._chain_head.block_num)

                        # tell the BlockPublisher else the chain is updated
                        self._notify_on_chain_updated(
                            self._chain_head,
                            result["committed_batches"],
                            result["uncommitted_batches"])

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

                    for block in reversed(result["new_chain"]):
                        receipts = self._make_receipts(block.execution_results)
                        # Update all chain observers
                        for observer in self._chain_observers:
                            observer.chain_update(block, receipts)

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
                if self.has_block(block.header_signature):
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
                if (block.previous_block_id in self._blocks_processing
                        or block.previous_block_id in self._blocks_pending):
                    LOGGER.debug('Block pending: %s', block)
                    # if the previous block is being processed, put it in a
                    # wait queue, Also need to check if previous block is
                    # in the wait queue.
                    pending_blocks = self._blocks_pending.get(
                        block.previous_block_id,
                        [])
                    # Though rare, the block may already be in the
                    # pending_block list and should not be re-added.
                    if block not in pending_blocks:
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

    def has_block(self, block_id):
        with self._lock:
            if block_id in self._block_cache:
                return True

            if block_id in self._blocks_processing:
                return True

            if block_id in self._blocks_pending:
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
                    done_cb=self.on_block_validated,
                    executor=self._transaction_executor,
                    squash_handler=self._squash_handler,
                    identity_signer=self._identity_signer,
                    data_dir=self._data_dir,
                    config_dir=self._config_dir,
                    permission_verifier=self._permission_verifier,
                    metrics_registry=self._metrics_registry)

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
            receipt.data.extend([data for data in result.data])
            receipt.state_changes.extend(result.state_changes)
            receipt.events.extend(result.events)
            receipt.transaction_id = result.signature
            receipts.append(receipt)
        return receipts
