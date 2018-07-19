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

from sawtooth_validator.concurrent.threadpool import \
    InstrumentedThreadPoolExecutor

from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.chain_commit_state import ChainCommitState
from sawtooth_validator.journal.chain_commit_state import DuplicateTransaction
from sawtooth_validator.journal.chain_commit_state import DuplicateBatch
from sawtooth_validator.journal.chain_commit_state import MissingDependency
from sawtooth_validator.journal.validation_rule_enforcer import \
    enforce_validation_rules
from sawtooth_validator.state.settings_view import SettingsViewFactory
from sawtooth_validator import metrics

from sawtooth_validator.state.merkle import INIT_ROOT_KEY


LOGGER = logging.getLogger(__name__)
COLLECTOR = metrics.get_collector(__name__)


class BlockValidationFailure(Exception):
    """
    Indication that a failure has occurred during block validation.
    """


class BlockValidationError(Exception):
    """
    Indication that an error occured during block validation and the validity
    of the block could not be determined.
    """


# Need to disable this new pylint check until the function can be refactored
# to return instead of raise StopIteration, which it does by calling next()
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


class BlockValidator:
    """
    Responsible for validating a block.
    """

    def __init__(self,
                 block_cache,
                 state_view_factory,
                 transaction_executor,
                 identity_signer,
                 data_dir,
                 config_dir,
                 permission_verifier,
                 thread_pool=None):
        """Initialize the BlockValidator
        Args:
            block_cache: The cache of all recent blocks and the processing
                state associated with them.
            state_view_factory: A factory that can be used to create read-
                only views of state for a particular merkle root, in
                particular the state as it existed when a particular block
                was the chain head.
            transaction_executor: The transaction executor used to
                process transactions.
            identity_signer: A cryptographic signer for signing blocks.
            data_dir: Path to location where persistent data for the
                consensus module can be stored.
            config_dir: Path to location where config data for the
                consensus module can be found.
            permission_verifier: The delegate for handling permission
                validation on blocks.
            thread_pool: (Optional) Executor pool used to submit block
                validation jobs. If not specified, a default will be created.
        Returns:
            None
        """
        self._block_cache = block_cache
        self._state_view_factory = state_view_factory
        self._transaction_executor = transaction_executor
        self._identity_signer = identity_signer
        self._data_dir = data_dir
        self._config_dir = config_dir
        self._permission_verifier = permission_verifier

        self._settings_view_factory = SettingsViewFactory(state_view_factory)

        self._thread_pool = InstrumentedThreadPoolExecutor(1) \
            if thread_pool is None else thread_pool

        self._block_scheduler = BlockScheduler(block_cache)

    def stop(self):
        self._thread_pool.shutdown(wait=True)

    def _get_previous_block_state_root(self, blkw):
        if blkw.previous_block_id == NULL_BLOCK_IDENTIFIER:
            return INIT_ROOT_KEY

        return self._block_cache[blkw.previous_block_id].state_root_hash

    def _validate_batches_in_block(self, blkw, prev_state_root):
        """
        Validate all batches in the block. This includes:
            - Validating all transaction dependencies are met
            - Validating there are no duplicate batches or transactions
            - Validating execution of all batches in the block produces the
              correct state root hash

        Args:
            blkw: the block of batches to validate
            prev_state_root: the state root to execute transactions on top of

        Raises:
            BlockValidationFailure:
                If validation fails, raises this error with the reason.
            MissingDependency:
                Validation failed because of a missing dependency.
            DuplicateTransaction:
                Validation failed because of a duplicate transaction.
            DuplicateBatch:
                Validation failed because of a duplicate batch.
        """
        if not blkw.block.batches:
            return

        scheduler = None
        try:
            while True:
                try:
                    chain_head = self._block_cache.block_store.chain_head

                    chain_commit_state = ChainCommitState(
                        blkw.previous_block_id,
                        self._block_cache,
                        self._block_cache.block_store)

                    chain_commit_state.check_for_duplicate_batches(
                        blkw.block.batches)

                    transactions = []
                    for batch in blkw.block.batches:
                        transactions.extend(batch.transactions)

                    chain_commit_state.check_for_duplicate_transactions(
                        transactions)

                    chain_commit_state.check_for_transaction_dependencies(
                        transactions)

                    if not self._check_chain_head_updated(chain_head, blkw):
                        break

                except (DuplicateBatch,
                        DuplicateTransaction,
                        MissingDependency) as err:
                    if not self._check_chain_head_updated(chain_head, blkw):
                        raise BlockValidationFailure(
                            "Block {} failed validation: {}".format(blkw, err))

            scheduler = self._transaction_executor.create_scheduler(
                prev_state_root)

            for batch, has_more in look_ahead(blkw.block.batches):
                if has_more:
                    scheduler.add_batch(batch)
                else:
                    scheduler.add_batch(batch, blkw.state_root_hash)

        except Exception:
            if scheduler is not None:
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
                raise BlockValidationFailure(
                    "Block {} failed validation: Invalid batch "
                    "{}".format(blkw, batch))

        if blkw.state_root_hash != state_hash:
            raise BlockValidationFailure(
                "Block {} failed state root hash validation. Expected {}"
                " but got {}".format(
                    blkw, blkw.state_root_hash, state_hash))

    def _check_chain_head_updated(self, chain_head, block):
        # The validity of blocks depends partially on whether or not
        # there are any duplicate transactions or batches in the block.
        # This can only be checked accurately if the block store does
        # not update during validation. The current practice is the
        # assume this will not happen and, if it does, to reprocess the
        # validation. This has been experimentally proven to be more
        # performant than locking the chain head and block store around
        # duplicate checking.
        if chain_head is None:
            return False

        current_chain_head = self._block_cache.block_store.chain_head
        if chain_head.identifier != current_chain_head.identifier:
            LOGGER.warning(
                "Chain head updated from %s to %s while checking "
                "duplicates and dependencies in block %s. "
                "Reprocessing validation.",
                chain_head, current_chain_head, block)
            return True

        return False

    def _validate_permissions(self, blkw, prev_state_root):
        """
        Validate that all of the batch signers and transaction signer for the
        batches in the block are permitted by the transactor permissioning
        roles stored in state as of the previous block. If a transactor is
        found to not be permitted, the block is invalid.
        """
        if blkw.block_num != 0:
            for batch in blkw.batches:
                if not self._permission_verifier.is_batch_signer_authorized(
                        batch, prev_state_root, from_state=True):
                    return False
        return True

    def _validate_on_chain_rules(self, blkw, prev_state_root):
        """
        Validate that the block conforms to all validation rules stored in
        state. If the block breaks any of the stored rules, the block is
        invalid.
        """
        if blkw.block_num != 0:
            return enforce_validation_rules(
                self._settings_view_factory.create_settings_view(
                    prev_state_root),
                blkw.header.signer_public_key,
                blkw.batches)
        return True

    def validate_block(self, blkw):
        if blkw.status == BlockStatus.Valid:
            return
        if blkw.status == BlockStatus.Invalid:
            raise BlockValidationFailure(
                'Block {} is already invalid'.format(blkw))

        # pylint: disable=broad-except
        try:
            try:
                prev_block = self._block_cache[blkw.previous_block_id]
            except KeyError:
                prev_block = None
            else:
                if prev_block.status == BlockStatus.Invalid:
                    raise BlockValidationFailure(
                        "Block {} rejected due to invalid predecessor"
                        " {}".format(blkw, prev_block))
                elif prev_block.status == BlockStatus.Unknown:
                    raise BlockValidationError(
                        "Attempted to validate block {} before its predecessor"
                        " {}".format(blkw, prev_block))

            try:
                prev_state_root = self._get_previous_block_state_root(blkw)
            except KeyError:
                raise BlockValidationError(
                    'Block {} rejected due to missing predecessor'.format(
                        blkw))

            if not self._validate_permissions(blkw, prev_state_root):
                raise BlockValidationFailure(
                    'Block {} failed permission validation'.format(blkw))

            if not self._validate_on_chain_rules(blkw, prev_state_root):
                raise BlockValidationFailure(
                    'Block {} failed on-chain validation rules'.format(
                        blkw))

            self._validate_batches_in_block(blkw, prev_state_root)

            blkw.status = BlockStatus.Valid

        except BlockValidationFailure as err:
            blkw.status = BlockStatus.Invalid
            raise err

        except BlockValidationError as err:
            blkw.status = BlockStatus.Unknown
            raise err

        except Exception as e:
            LOGGER.exception(
                "Unhandled exception BlockValidator.validate_block()")
            raise e

    def submit_blocks_for_verification(self, blocks, callback):
        # This is a work-around for the fact that the blocks passed to this
        # function are both from the ChainController (in Rust) or itself.
        # This ensures that the blocks being operated on come from the cache
        blocks = [self._block_cache[b.identifier] for b in blocks]
        ready = self._block_scheduler.schedule(blocks)
        for block in ready:
            # Schedule the block for processing
            self._thread_pool.submit(
                self.process_block_verification, block, callback)

    def _release_pending(self, block):
        """Removes the block from processing and returns any blocks that should
        now be scheduled for processing, cleaning up the pending block trackers
        in the process.
        """
        ready = []
        if block.status == BlockStatus.Valid:
            ready.extend(self._block_scheduler.done(block))

        elif block.status == BlockStatus.Invalid:
            # Mark all pending blocks as invalid
            invalid = self._block_scheduler.done(block, and_descendants=True)
            for blk in invalid:
                blk.status = BlockStatus.Invalid
                LOGGER.debug('Marking descendant block invalid: %s', blk)

        else:
            # An error occured during validation, something is wrong internally
            # and we need to abort validation of this block and all its
            # children without marking them as invalid.
            unknown = self._block_scheduler.done(block, and_descendants=True)
            for blk in unknown:
                LOGGER.debug(
                    'Removing block from cache and pending due to error '
                    'during validation: %s', block)
                try:
                    del self._block_cache[block.identifier]
                except KeyError:
                    LOGGER.exception(
                        "Tried to delete a descendant pending block from the"
                        " block cache because of an error, but the descendant"
                        " was not in the cache.")

        return ready

    def has_block(self, block_id):
        return block_id in self._block_scheduler

    def process_block_verification(self, block, callback):
        """
        Main entry for Block Validation, Take a given candidate block
        and decide if it is valid then if it is valid determine if it should
        be the new head block. Returns the results to the ChainController
        so that the change over can be made if necessary.
        """
        try:
            self.validate_block(block)
            LOGGER.info(
                'Block %s passed validation', block)
        except BlockValidationFailure as err:
            LOGGER.warning(
                'Block %s failed validation: %s', block, err)
        except BlockValidationError as err:
            LOGGER.error(
                'Encountered an error while validating %s: %s', block, err)
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(
                "Block validation failed with unexpected error: %s", block)
        else:
            callback(block)

        try:
            blocks_now_ready = self._release_pending(block)
            self.submit_blocks_for_verification(blocks_now_ready, callback)
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(
                "Submitting pending blocks failed with unexpected error: %s",
                block)


class BlockScheduler:

    def __init__(self, block_cache):
        # Blocks that are currently being processed
        self._processing = set()

        self._processing_gauge = COLLECTOR.gauge(
            'blocks_processing', instance=self)
        self._processing_gauge.set_value(0)

        # Descendant blocks that are waiting for an in process block
        # to complete
        self._pending = set()
        self._descendants = dict()

        self._pending_gauge = COLLECTOR.gauge(
            'blocks_pending', instance=self)
        self._pending_gauge.set_value(0)

        self._block_cache = block_cache

        self._lock = RLock()

    def schedule(self, blocks):
        """Add the blocks to the scheduler and return any blocks that are
        ready to be processed immediately.
        """
        ready = []
        with self._lock:
            for block in blocks:
                block_id = block.header_signature
                prev_id = block.previous_block_id

                if block_id in self._processing:
                    LOGGER.debug("Block already in process: %s", block)
                    continue

                if block_id in self._pending:
                    LOGGER.debug("Block already pending: %s", block)
                    continue

                if prev_id in self._processing:
                    LOGGER.debug(
                        "Previous block '%s' in process, adding '%s' to "
                        " pending",
                        block.previous_block_id, block)
                    self._add_block_to_pending(block)
                    continue

                if prev_id in self._pending:
                    LOGGER.debug(
                        "Previous block '%s' is pending, adding '%s' to "
                        " pending",
                        block.previous_block_id, block)
                    self._add_block_to_pending(block)
                    continue

                try:
                    prev_block = self._block_cache[block.previous_block_id]
                except KeyError:
                    LOGGER.error(
                        "Block %s submitted for processing but predecessor %s"
                        " is missing. Adding to pending.",
                        block,
                        block.previous_block_id)
                    self._add_block_to_pending(block)
                    continue
                else:
                    if prev_block.status == BlockStatus.Unknown:
                        LOGGER.warning(
                            "Block %s submitted for processing but predecessor"
                            " %s has not been validated and is not pending."
                            " Adding to pending.", block, prev_block)
                        self._add_block_to_pending(block)
                    else:
                        LOGGER.debug(
                            "Adding block %s for processing",
                            block.identifier)

                        # Add the block to the set of blocks being processed
                        self._processing.add(block.identifier)
                        ready.append(block)

        self._update_gauges()

        return ready

    def done(self, block, and_descendants=False):
        """Mark the given in process block as done and return any blocks that
        are now ready to be processed.

        Args:
            block: The block to mark as done
            and_descendants: If true, also mark all descendants as done and
                return them.

        Returns:
            A list of blocks ready to be processed
        """
        block_id = block.header_signature
        ready = []
        with self._lock:
            LOGGER.debug("Removing block from processing %s", block_id)
            try:
                self._processing.remove(block_id)
            except KeyError:
                LOGGER.warning(
                    "Tried to remove block from in process but it wasn't in"
                    " processes: %s",
                    block_id)

            if and_descendants:
                descendants = self._descendants.pop(block_id, [])
                while descendants:
                    blk = descendants.pop()
                    self._pending.remove(blk.header_signature)
                    descendants.extend(self._descendants.pop(
                        blk.header_signature, []))
                    ready.append(blk)

            else:
                ready.extend(self._descendants.pop(block_id, []))
                for blk in ready:
                    self._pending.remove(blk.header_signature)

        return ready

    def __contains__(self, block_id):
        with self._lock:
            return block_id in self._processing or block_id in self._pending

    def _add_block_to_pending(self, block):
        with self._lock:
            self._pending.add(block.identifier)
            previous = block.previous_block_id
            if previous not in self._descendants:
                self._descendants[previous] = [block]
            else:
                if block not in self._descendants[previous]:
                    self._descendants[previous].append(block)

    def _update_gauges(self):
        self._pending_gauge.set_value(len(self._pending))
        self._processing_gauge.set_value(len(self._processing))
