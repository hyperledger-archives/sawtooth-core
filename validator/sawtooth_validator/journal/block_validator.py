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

import sawtooth_signing as signing

from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.chain_commit_state import ChainCommitState
from sawtooth_validator.journal.validation_rule_enforcer import \
    ValidationRuleEnforcer
from sawtooth_validator.state.settings_view import SettingsViewFactory
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.metrics.wrappers import CounterWrapper

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


class BlockValidationResult:
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
        self._result = BlockValidationResult(new_block)
        self._permission_verifier = permission_verifier

        self._validation_rule_enforcer = \
            ValidationRuleEnforcer(SettingsViewFactory(state_view_factory))

        if metrics_registry:
            self._moved_to_fork_count = CounterWrapper(
                metrics_registry.counter('chain_head_moved_to_fork_count'))
        else:
            self._moved_to_fork_count = CounterWrapper()

    def _get_previous_block_state_root(self, blkw):
        if blkw.previous_block_id == NULL_BLOCK_IDENTIFIER:
            return INIT_ROOT_KEY

        return self._block_cache[blkw.previous_block_id].state_root_hash

    @staticmethod
    def verify_batch_transactions(batch, chain_commit_state):
        """Verify that all transactions in this batch are unique and that all
        transaction dependencies in this batch have been satisfied.

        :param batch: the batch to verify
        :param chain_commit_state: the current chain commit state to verify the
            batch against
        :return:
        Boolean: True if all dependencies are present and all transactions
        are unique.
        """
        for txn in batch.transactions:
            txn_hdr = TransactionHeader()
            txn_hdr.ParseFromString(txn.header)
            if chain_commit_state.has_transaction(txn.header_signature):
                LOGGER.debug(
                    "Batch invalid due to duplicate transaction: %s",
                    txn.header_signature[:8])
                return False
            for dep in txn_hdr.dependencies:
                if not chain_commit_state.has_transaction(dep):
                    LOGGER.debug(
                        "Batch invalid due to missing transaction dependency;"
                        " transaction %s depends on %s",
                        txn.header_signature[:8], dep[:8])
                    return False
        return True

    def _verify_block_batches(self, blkw, prev_state_root):
        if blkw.block.batches:
            scheduler = self._executor.create_scheduler(
                self._squash_handler, prev_state_root)
            self._executor.execute(scheduler)
            try:
                for batch, has_more in look_ahead(blkw.block.batches):
                    if self._chain_commit_state.has_batch(
                            batch.header_signature):
                        LOGGER.debug("Block(%s) rejected due to duplicate "
                                     "batch, batch: %s", blkw,
                                     batch.header_signature[:8])
                        raise InvalidBatch()

                    # Verify dependencies and uniqueness
                    if self.verify_batch_transactions(
                        batch, self._chain_commit_state
                    ):
                        # Only add transactions to commit state if all
                        # transactions in the batch are good.
                        self._chain_commit_state.add_batch(
                            batch, add_transactions=True)
                    else:
                        raise InvalidBatch()

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
                        batch, prev_state_root, from_state=True):
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
        # pylint: disable=broad-except
        try:
            if blkw.status == BlockStatus.Valid:
                return True
            elif blkw.status == BlockStatus.Invalid:
                return False
            else:
                valid = True

                try:
                    prev_state_root = self._get_previous_block_state_root(blkw)
                except KeyError:
                    LOGGER.debug(
                        "Block rejected due to missing predecessor: %s", blkw)
                    return False

                valid = self.validate_permissions(blkw, prev_state_root)

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
                    valid = self.validate_on_chain_rules(blkw, prev_state_root)

                if valid:
                    valid = self._verify_block_batches(blkw, prev_state_root)

                # since changes to the chain-head can change the state of the
                # blocks in BlockStore we have to revalidate this block.
                block_store = self._block_cache.block_store
                if self._chain_head is not None and\
                        self._chain_head.identifier !=\
                        block_store.chain_head.identifier:
                    raise ChainHeadUpdated()

                blkw.status = BlockStatus.Valid if\
                    valid else BlockStatus.Invalid
                return valid
        except ChainHeadUpdated:
            raise
        except Exception:
            LOGGER.exception(
                "Unhandled exception BlockPublisher.validate_block()")
            return False

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

    def _compare_forks_consensus(self, chain_head, new_block):
        """Ask the consensus module which fork to choose.
        """
        public_key = self._identity_signer.get_public_key().as_hex()
        fork_resolver = self._consensus_module.\
            ForkResolver(block_cache=self._block_cache,
                         state_view_factory=self._state_view_factory,
                         data_dir=self._data_dir,
                         config_dir=self._config_dir,
                         validator_id=public_key)

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

    def run(self):
        """
        Main entry for Block Validation, Take a given candidate block
        and decide if it is valid then if it is valid determine if it should
        be the new head block. Returns the results to the ChainController
        so that the change over can be made if necessary.
        """
        try:
            LOGGER.info("Starting block validation of : %s", self._new_block)

            # Get the current chain_head and store it in the result
            self._chain_head = self._block_cache.block_store.chain_head
            self._result.chain_head = self._chain_head

            # Get the heads of the current chain and the new chain
            cur_blkw = self._chain_head
            new_blkw = self._new_block

            # Get all the blocks since the greatest common height from the
            # longer chain.
            if self.compare_chain_height(cur_blkw, new_blkw):
                cur_blkw, self._result.current_chain =\
                    self.build_fork_diff_to_common_height(cur_blkw, new_blkw)
            else:
                new_blkw, self._result.new_chain =\
                    self.build_fork_diff_to_common_height(new_blkw, cur_blkw)

            # Create local bindings
            cur_chain = self._result.current_chain
            new_chain = self._result.new_chain

            # Add blocks to the two chains until a common ancestor is found
            # or raise an exception if no common ancestor is found
            self.extend_fork_diff_to_common_ancestor(
                new_blkw, cur_blkw,
                self._result.new_chain, self._result.current_chain)

            # Determine the validity of the new fork and build the transaction
            # cache to simulate the state of the chain at the common root.
            self._chain_commit_state = ChainCommitState(
                self._block_cache.block_store, cur_chain)

            valid = True
            for block in reversed(new_chain):
                if valid:
                    if not self.validate_block(block):
                        LOGGER.info("Block validation failed: %s", block)
                        valid = False
                    self._result.transaction_count += block.num_transactions
                else:
                    LOGGER.info(
                        "Block marked invalid (invalid predecessor): %s",
                        block)
                    block.status = BlockStatus.Invalid

            if not valid:
                self._done_cb(False, self._result)
                return

            # Ask consensus if the new chain should be committed
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

            commit_new_chain = self._compare_forks_consensus(
                self._chain_head, self._new_block)

            # If committing the new chain, get the list of committed batches
            # from the current chain that need to be uncommitted and the list
            # of uncommitted batches from the new chain that need to be
            # committed.
            if commit_new_chain:
                commit, uncommit =\
                    self.get_batch_commit_changes(new_chain, cur_chain)
                self._result.committed_batches = commit
                self._result.uncommitted_batches = uncommit

                if new_chain[0].previous_block_id != \
                        self._chain_head.identifier:
                    self._moved_to_fork_count.inc()

            # Pass the results to the callback function
            self._done_cb(commit_new_chain, self._result)
            LOGGER.info("Finished block validation of: %s", self._new_block)
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
