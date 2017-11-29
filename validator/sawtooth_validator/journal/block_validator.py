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
import queue

from sawtooth_validator.concurrent.thread import InstrumentedThread
from sawtooth_validator.concurrent.threadpool import \
    InstrumentedThreadPoolExecutor

from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.consensus.consensus_factory import \
    ConsensusFactory
from sawtooth_validator.journal.chain_commit_state import ChainCommitState
from sawtooth_validator.journal.chain_commit_state import DuplicateTransaction
from sawtooth_validator.journal.chain_commit_state import DuplicateBatch
from sawtooth_validator.journal.chain_commit_state import MissingDependency
from sawtooth_validator.journal.block_scheduler import BlockValidationScheduler
from sawtooth_validator.journal.validation_rule_enforcer import \
    ValidationRuleEnforcer
from sawtooth_validator.state.settings_view import SettingsViewFactory

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


class ForkResolutionResult:
    def __init__(self, block):
        self.block = block
        self.chain_head = None
        self.new_chain = []
        self.current_chain = []
        self.committed_batches = []
        self.uncommitted_batches = []
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

    def merge_block_result(self, block_validation_result):
        self.transaction_count =\
            block_validation_result.transaction_count
        self.execution_results.extend(
            block_validation_result.execution_results)


class BlockValidationResult:
    def __init__(self, block):
        self.block = block

    def __bool__(self):
        return self.block.status == BlockStatus.Valid

    @property
    def execution_results(self):
        return self.block.execution_results

    @property
    def transaction_count(self):
        return self.block.execution_results

    def set_valid(self, is_valid):
        if is_valid:
            self.block.status = BlockStatus.Valid
        else:
            self.block.status = BlockStatus.Invalid

    def merge_batch_results(self, batch_validation_results):
        self.block.transaction_count += \
            batch_validation_results.transaction_count
        self.block.execution_results.extend(
            batch_validation_results.execution_results)


class BatchValidationResults:
    def __init__(self):
        self.transaction_count = 0
        self.execution_results = []
        self.valid = False


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


class _BlockReceiveThread(InstrumentedThread):
    """This thread's job is to pull blocks off of the queue and to submit them
    for validation."""
    def __init__(
        self, block_queue, submit_function, callback_function,
        exit_poll_interval=1
    ):
        super().__init__(name='_BlockReceiveThread')
        self._block_queue = block_queue
        self._submit_function = submit_function
        self._callback_function = callback_function
        self._exit_poll_interval = exit_poll_interval
        self._exit = False

    def run(self):
        while True:
            try:
                # Set timeout so we can check if the thread has been stopped
                block = self._block_queue.get(timeout=self._exit_poll_interval)
                self._submit_function(block, self._callback_function)

            except queue.Empty:
                pass

            if self._exit:
                return

    def stop(self):
        self._exit = True


class BlockValidator(object):
    """
    Responsible for validating a block, handles both chain extensions and fork
    will determine if the new block should be the head of the chain and return
    the information necessary to do the switch if necessary.
    """

    def __init__(self,
                 block_cache,
                 state_view_factory,
                 transaction_executor,
                 on_block_validated,
                 squash_handler,
                 identity_public_key,
                 data_dir,
                 config_dir,
                 permission_verifier):
        """Initialize the BlockValidator
        Args:
             implementation of the consensus algorithm to use for block
             validation.
             block_cache: The cache of all recent blocks and the processing
             state associated with them.
             state_view_factory: The factory object to create.
             transaction_executor: The transaction executor used to
             process transactions.
             on_block_validated: The function to call when block validation is
             complete.
             squash_handler: A parameter passed when creating transaction
             schedulers.
             identity_public_key: Public key used for this validator's
             identity.
             data_dir: Path to location where persistent data for the
             consensus module can be stored.
             config_dir: Path to location where config data for the
             consensus module can be found.
        Returns:
            None
        """
        self._block_cache = block_cache
        self._state_view_factory = state_view_factory
        self._transaction_executor = transaction_executor
        self._on_block_validated = on_block_validated
        self._squash_handler = squash_handler
        self._identity_public_key = identity_public_key
        self._data_dir = data_dir
        self._config_dir = config_dir
        self._permission_verifier = permission_verifier

        self._validation_rule_enforcer = ValidationRuleEnforcer(
            SettingsViewFactory(state_view_factory))

        self._thread_pool = InstrumentedThreadPoolExecutor(1)
        self._block_receive_thread = None

        # Blocks waiting to be scheduled
        self._incoming_blocks = queue.Queue()
        # Blocks waiting to be processed
        self._ready_blocks = queue.Queue()

        # The scheduler reads blocks off of the incoming queue and puts blocks
        # on the ready queue when they are ready to be validated. This
        # allows us to make some guarantees about blocks before they are
        # validated and enable validating a single block at a time.
        self._block_scheduler = BlockValidationScheduler(
            self._incoming_blocks, self._ready_blocks, block_cache)

    def start(self):
        self._block_receive_thread = _BlockReceiveThread(
            block_queue=self._ready_blocks,
            submit_function=self._on_scheduled_block_received,
            callback_function=self.on_block_validated)
        self._block_receive_thread.start()
        self._block_scheduler.start()

    def stop(self):
        self._thread_pool.shutdown(wait=True)
        if self._block_receive_thread is not None:
            self._block_receive_thread.stop()
            self._block_receive_thread = None
        self._block_scheduler.stop()

    def queue_block(self, block):
        """
        New block has been received, queue it with the block validator for
        processing.
        """
        self._incoming_blocks.put(block)

    def on_block_validated(self, commit_new_block, result):
        self._block_scheduler.on_block_validated(result.block.header_signature)
        self._on_block_validated(commit_new_block, result)

    def _on_scheduled_block_received(self, block, callback):
        """Checks to see if the block should be dropped, then adds the block to
        the block cache and submits the block for validation."""
        self.submit_blocks_for_validation([block], callback)

    def has_block(self, block_id):
        # I am not convinced that any of these checks are necessary, since the
        # block cache is checked in the completer and in_process and in_pending
        # are checked in submit_blocks_for_validation.
        if block_id in self._block_cache:
            return True

        if self._block_scheduler.is_processing(block_id):
            return True

        if self._block_scheduler.is_pending(block_id):
            return True

        return False

    def _get_previous_block_state_root(self, blkw):
        if blkw.previous_block_id == NULL_BLOCK_IDENTIFIER:
            return INIT_ROOT_KEY

        return self._block_cache[blkw.previous_block_id].state_root_hash

    def validate_batches_in_block(self, blkw, prev_state_root):
        result = BatchValidationResults()
        if blkw.block.batches:
            chain_commit_state = ChainCommitState(
                blkw.previous_block_id,
                self._block_cache,
                self._block_cache.block_store)

            scheduler = self._transaction_executor.create_scheduler(
                self._squash_handler, prev_state_root)
            self._transaction_executor.execute(scheduler)

            try:
                chain_commit_state.check_for_duplicate_batches(
                    blkw.block.batches)
            except DuplicateBatch as err:
                LOGGER.debug("Block(%s) rejected due to duplicate "
                             "batch, batch: %s", blkw,
                             err.batch_id[:8])
                return result

            transactions = []
            for batch in blkw.block.batches:
                transactions.extend(batch.transactions)

            try:
                chain_commit_state.check_for_duplicate_transactions(
                    transactions)
            except DuplicateTransaction as err:
                LOGGER.debug(
                    "Block(%s) rejected due to duplicate transaction: %s",
                    blkw, err.transaction_id[:8])
                return result

            try:
                chain_commit_state.check_for_transaction_dependencies(
                    transactions)
            except MissingDependency as err:
                LOGGER.debug(
                    "Block(%s) rejected due to missing dependency: %s",
                    blkw, err.transaction_id[:8])
                return result

            try:
                for batch, has_more in look_ahead(blkw.block.batches):
                    if has_more:
                        scheduler.add_batch(batch)
                    else:
                        scheduler.add_batch(batch, blkw.state_root_hash)
            except:
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
                    state_hash = batch_result.state_hash

                    result.execution_results.extend(txn_results)
                    result.transaction_count += len(batch.transactions)
                else:
                    return result
            if blkw.state_root_hash != state_hash:
                LOGGER.debug("Block(%s) rejected due to state root hash "
                             "mismatch: %s != %s", blkw, blkw.state_root_hash,
                             state_hash)
                return result
        result.valid = True
        return result

    def validate_permissions(self, blkw, prev_state_root):
        """
        Validate that all of the batch signers and transaction signer for the
        batches in the block are permitted by the transactor permissioning
        roles stored in state as of the previous block. If a transactor is
        found to not be permitted, the block is invalid.
        """
        if blkw.block_num != 0:
            for batch in blkw.batches:
                if not self._permission_verifier.is_batch_signer_authorized(
                        batch, prev_state_root):
                    return False
        return True

    def validate_on_chain_rules(self, blkw, prev_state_root):
        """
        Validate that the block conforms to all validation rules stored in
        state. If the block breaks any of the stored rules, the block is
        invalid.
        """
        if blkw.block_num != 0:
            return self._validation_rule_enforcer.validate(
                blkw, prev_state_root)
        return True

    def validate_block(self, blkw):
        result = BlockValidationResult(blkw)

        if blkw.status != BlockStatus.Unknown:
            return result

        # pylint: disable=broad-except
        try:
            prev_state_root = self._get_previous_block_state_root(blkw)

            if not self.validate_permissions(blkw, prev_state_root):
                result.set_valid(False)
                return result

            if not self.validate_on_chain_rules(blkw, prev_state_root):
                result.set_valid(False)
                return result

            try:
                prev_block = self._block_cache[blkw.previous_block_id]
            except KeyError:
                prev_block = None

            consensus = self._load_consensus(prev_block)
            consensus_block_verifier = consensus.BlockVerifier(
                block_cache=self._block_cache,
                state_view_factory=self._state_view_factory,
                data_dir=self._data_dir,
                config_dir=self._config_dir,
                validator_id=self._identity_public_key)

            if not consensus_block_verifier.verify_block(blkw):
                result.set_valid(False)
                return result

            batch_validation_results = self.validate_batches_in_block(
                blkw, prev_state_root)
            result.set_valid(batch_validation_results.valid)
            result.merge_batch_results(batch_validation_results)

            return result

        except Exception:
            LOGGER.exception(
                "Unhandled exception BlockValidator.validate_block()")
            return result

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
            BlockValidationAborted
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
                raise BlockValidationAborted()

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
                raise BlockValidationAborted()

            new_chain.append(new_blkw)
            try:
                new_blkw = self._block_cache[new_blkw.previous_block_id]
            except KeyError:
                LOGGER.debug(
                    "Block rejected due to missing predecessor: %s",
                    new_blkw)
                for b in new_chain:
                    b.status = BlockStatus.Invalid
                raise BlockValidationAborted()

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

    def submit_blocks_for_validation(self, blocks, callback):
        for block in blocks:
            LOGGER.debug(
                "Adding block %s for processing", block.identifier[:6])

            # Schedule the block for processing
            self._thread_pool.submit(
                self.process_block_validation, block, callback)

    def process_block_validation(self, block, callback):
        """
        Main entry for Block Validation, Take a given candidate block
        and decide if it is valid then if it is valid determine if it should
        be the new head block. Returns the results to the ChainController
        so that the change over can be made if necessary.
        """
        try:
            result = ForkResolutionResult(block)
            LOGGER.info("Starting block validation of : %s", block)

            # If this is a genesis block, we can skip the rest
            if block.previous_block_id == NULL_BLOCK_IDENTIFIER:
                valid = bool(self.validate_block(block))
                callback(valid, result)
                return

            # Get the current chain_head and store it in the result
            chain_head = self._block_cache.block_store.chain_head
            result.chain_head = chain_head

            # Create new local variables for current and new block, since
            # these variables get modified later
            current_block = chain_head
            new_block = block

            # Get all the blocks since the greatest common height from the
            # longer chain.
            if self.compare_chain_height(current_block, new_block):
                current_block, result.current_chain =\
                    self.build_fork_diff_to_common_height(
                        current_block, new_block)
            else:
                new_block, result.new_chain =\
                    self.build_fork_diff_to_common_height(
                        new_block, current_block)

            # Add blocks to the two chains until a common ancestor is found
            # or raise an exception if no common ancestor is found
            self.extend_fork_diff_to_common_ancestor(
                new_block, current_block,
                result.new_chain, result.current_chain)

            # First check if any predecessors are invalid or unknown
            for blk in result.new_chain[1:]:
                # This should never happen, because the completer and scheduler
                # should ensure we only receive blocks in order
                if blk.status == BlockStatus.Unknown:
                    LOGGER.error(
                        "Tried to validate block '%s' before predecessor '%s'",
                        block, blk)
                    raise BlockValidationAborted()

                if blk.status == BlockStatus.Invalid:
                    block.status = BlockStatus.Invalid
                    callback(False, result)
                    return

            # The completer and scheduler ensure that we have already validated
            # all previous blocks on this fork prior to receiving this block,
            # so we only need to validate this block.
            block_validation_result = self.validate_block(block)
            result.merge_block_result(block_validation_result)
            if not bool(block_validation_result):
                LOGGER.info("Block validation failed: %s", block)
                callback(False, result)
                return

            # The chain_head is None when this is the genesis block or if the
            # block store has no chain_head.
            if chain_head is not None:
                current_chain_head = self._block_cache.block_store.chain_head
                if chain_head.identifier != current_chain_head.identifier:
                    raise ChainHeadUpdated()

            # Ask consensus if the new chain should be committed
            commit_new_chain = self._compare_forks_consensus(chain_head, block)

            # If committing the new chain, get the list of committed batches
            # from the current chain that need to be uncommitted and the list
            # of uncommitted batches from the new chain that need to be
            # committed.
            if commit_new_chain:
                commit, uncommit =\
                    self.get_batch_commit_changes(
                        result.new_chain, result.current_chain)
                result.committed_batches = commit
                result.uncommitted_batches = uncommit

            # Pass the results to the callback function
            callback(commit_new_chain, result)
            LOGGER.info("Finished block validation of: %s", block)

        except BlockValidationAborted:
            callback(False, result)
            return
        except ChainHeadUpdated:
            callback(False, result)
            return
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(
                "Block validation failed with unexpected error: %s", new_block)
            # callback to clean up the block out of the processing list.
            callback(False, result)
