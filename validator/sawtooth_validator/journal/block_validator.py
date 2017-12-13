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
    Indication that the validation of this block has terminated for an expected
    case and that the processing should exit.
    """
    pass


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
        New block has been received, queue it with the block validation
        scheduler for processing.
        """
        self._incoming_blocks.put(block)

    def on_block_validated(self, block):
        self._block_scheduler.on_block_validated(block.header_signature)
        self._on_block_validated(block)

    def _on_scheduled_block_received(self, block, callback):
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

    def _get_previous_block(self, blkw):
        if blkw.previous_block_id == NULL_BLOCK_IDENTIFIER:
            return None

        return self._block_cache[blkw.previous_block_id]

    def _get_state_root(self, blkw):
        if blkw is None:
            return INIT_ROOT_KEY
        return blkw.state_root_hash

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
        """Validate this block. Results are stored in the BlockWrapper."""
        if blkw.status != BlockStatus.Unknown:
            return blkw.status == BlockStatus.Valid

        # pylint: disable=broad-except
        try:
            try:
                # Returns None if this is a genesis block
                prev_block = self._get_previous_block(blkw)
            except KeyError:
                LOGGER.exception(
                    "Tried to validate block %s, but can't find predecessor.",
                    blkw)
                raise

            if prev_block is not None:
                if prev_block.status != BlockStatus.Valid:
                    LOGGER.info(
                        "Short-circuiting validation, predecessor has status "
                        "%s: %s", prev_block.status, blkw)
                    blkw.status = prev_block.status
                    return False

            prev_state_root = self._get_state_root(prev_block)

            if not self.validate_permissions(blkw, prev_state_root):
                blkw.status = BlockStatus.Invalid
                return False

            if not self.validate_on_chain_rules(blkw, prev_state_root):
                blkw.status = BlockStatus.Invalid
                return False

            consensus = self._load_consensus(prev_block)
            consensus_block_verifier = consensus.BlockVerifier(
                block_cache=self._block_cache,
                state_view_factory=self._state_view_factory,
                data_dir=self._data_dir,
                config_dir=self._config_dir,
                validator_id=self._identity_public_key)

            if not consensus_block_verifier.verify_block(blkw):
                blkw.status = BlockStatus.Invalid
                return False

            results = self.validate_batches_in_block(blkw, prev_state_root)
            if results.valid:
                blkw.status = BlockStatus.Valid
            else:
                blkw.status = BlockStatus.Invalid

            blkw.transaction_count += results.transaction_count
            blkw.execution_results.extend(results.execution_results)

        except Exception:
            LOGGER.exception(
                "Unhandled exception BlockValidator.validate_block()")
            blkw.status = BlockStatus.Invalid

        return blkw.status == BlockStatus.Valid

    def _load_consensus(self, block):
        """Load the consensus module using the state as of the given block."""
        if block is not None:
            return ConsensusFactory.get_configured_consensus_module(
                block.header_signature,
                BlockWrapper.state_view_for_block(
                    block,
                    self._state_view_factory))
        return ConsensusFactory.get_consensus_module('genesis')

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

            LOGGER.info("Starting block validation of : %s", block)

            # The completer and scheduler ensure that we have already validated
            # all previous blocks on this fork prior to receiving this block,
            # so we only need to validate this block.
            valid = self.validate_block(block)
            if not valid:
                LOGGER.info("Block validation failed: %s", block)
                # TODO: Should the chain controller even receive this?

            # Pass the results to the callback function
            callback(block)
            LOGGER.info("Finished block validation of: %s", block)

        except BlockValidationAborted:
            callback(block)
            return

        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(
                "Block validation failed with unexpected error: %s", block)
            # callback to clean up the block out of the processing list.
            callback(block)
