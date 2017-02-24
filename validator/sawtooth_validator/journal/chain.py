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

from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.consensus.consensus_factory import \
    ConsensusFactory
from sawtooth_validator.journal.transaction_cache import TransactionCache

from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_validator.state.merkle import INIT_ROOT_KEY


LOGGER = logging.getLogger(__name__)


class BlockValidationAborted(Exception):
    """
    Indication that the validation of this fork has terminated for an
    expected(handled) case and that the processing should exit.
    """
    pass


class BlockValidator(object):
    """
    Responsible for validating a block, handles both chain extensions and fork
    will determine if the new block should be the head of the chain and return
    the information necessary to do the switch if necessary.
    """

    def __init__(self, consensus_module,
                 block_cache,
                 new_block,
                 chain_head,
                 state_view_factory,
                 done_cb,
                 executor,
                 squash_handler):
        self._consensus_module = consensus_module
        self._block_cache = block_cache
        self._new_block = new_block
        self._chain_head = chain_head
        self._state_view_factory = state_view_factory
        self._done_cb = done_cb
        self._executor = executor
        self._squash_handler = squash_handler

        self._result = {
            'new_block': new_block,
            'chain_head': chain_head,
            'new_chain': [],
            'cur_chain': [],
            'committed_batches': [],
            'uncommitted_batches': [],
        }

    def _get_previous_block_root_state_hash(self, blkw):
        if blkw.previous_block_id == NULL_BLOCK_IDENTIFIER:
            return INIT_ROOT_KEY
        else:
            prev_blkw = self._block_cache[blkw.previous_block_id]
            return prev_blkw.state_root_hash

    def _is_block_complete(self, blkw):
        """
        Check that the block is formally complete.
        - all batches are present and in the correct order
        :param blkw: the block to verify
        :return: Boolean - True on success.
        """

        batch_ids = blkw.header.batch_ids
        batches = blkw.batches

        if len(batch_ids) != len(batches):
            return False

        for i in range(0, len(batch_ids)):
            if batch_ids[i] != batches[i].header_signature:
                return False

        return True

    def _verify_block_signature(self, blkw):
        """ Verify a block is properly signed.
        :param blkw: the block to verify
        :return: Boolean - True on success.
        """
        return signing.verify(blkw.block.header, blkw.block.header_signature,
                              blkw.header.signer_pubkey)

    def _verify_batches_dependencies(self, batch, committed_txn):
        """Verify that all transactions dependencies in this batch have been
        satisfied, ie already committed by this block or prior block in the
        chain.

        :param batch: the batch to verify
        :param committed_txn(TransactionCache): Current set of commited
        transaction, updated during processing.
        :return:
        Boolean: True if all dependencies are present.
        """
        for txn in batch.transactions:
            txn_hdr = TransactionHeader()
            txn_hdr.ParseFromString(txn.header)
            for dep in txn_hdr.dependencies:
                if dep not in committed_txn:
                    LOGGER.debug("Block rejected due missing" +
                                 " transaction dependency, transaction {}"
                                 " depends on {}",
                                 txn.header_signature, dep)
                    return False
            committed_txn.add_txn(txn.header_signature)
        return True

    def _verify_block_batches(self, blkw, committed_txn):
        if len(blkw.block.batches) > 0:

            prev_state = self._get_previous_block_root_state_hash(blkw)
            scheduler = self._executor.create_scheduler(
                self._squash_handler, prev_state)
            self._executor.execute(scheduler)

            for i in range(len(blkw.block.batches) - 1):
                batch = blkw.batches[i]
                if not self._verify_batches_dependencies(batch, committed_txn):
                    return False
                scheduler.add_batch(batch)

            batch = blkw.batches[-1]
            if not self._verify_batches_dependencies(batch, committed_txn):
                return False
            scheduler.add_batch(batch,
                                blkw.state_root_hash)

            scheduler.finalize()
            scheduler.complete(block=True)
            state_hash = None
            for i in range(len(blkw.batches)):
                result = scheduler.get_batch_execution_result(
                    blkw.batches[i].header_signature)
                # If the result is None, the executor did not
                # receive the batch
                if result is not None and result.is_valid:
                    state_hash = result.state_hash
                else:
                    return False
            if blkw.state_root_hash != state_hash:
                return False
        return True

    def _validate_block(self, blkw, committed_txn):
        try:
            if blkw.status == BlockStatus.Valid:
                return True
            elif blkw.status == BlockStatus.Invalid:
                return False
            else:
                valid = True

                prev_state = self._get_previous_block_root_state_hash(blkw)
                state_view = self._state_view_factory.\
                    create_view(prev_state)
                consensus = self._consensus_module.\
                    BlockVerifier(self._block_cache, state_view=state_view)

                if valid:
                    valid = self._is_block_complete(blkw)

                if valid:
                    valid = self._verify_block_signature(blkw)

                if valid:
                    valid = self._verify_block_batches(blkw, committed_txn)

                if valid:
                    valid = consensus.verify_block(blkw)

                # Update the block store
                blkw.weight = consensus.compute_block_weight(blkw)
                blkw.status = BlockStatus.Valid if \
                    valid else BlockStatus.Invalid
                return valid
        # pylint: disable=broad-except
        except Exception as exc:
            LOGGER.exception(exc)
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
                    new_blkw = \
                        self._block_cache[
                            new_blkw.previous_block_id]
                except KeyError:
                    LOGGER.debug("Block rejected due missing" +
                                 " predecessor: %s", new_blkw)
                    for b in new_chain:
                        b.status = BlockStatus.Invalid
                    self._done_cb(False, self._result)
                    raise BlockValidationAborted()
        elif new_blkw.block_num < cur_blkw.block_num:
            # current chain is longer
            # walk the current chain back until we find the block that is the
            # same height as the new chain.
            while cur_blkw.block_num > \
                    new_blkw.block_num \
                    and new_blkw.previous_block_id != \
                    NULL_BLOCK_IDENTIFIER:
                cur_chain.append(cur_blkw)
                cur_blkw = self._block_cache[cur_blkw.previous_block_id]
        return (new_blkw, cur_blkw)

    def _find_common_ancestor(self, new_blkw, cur_blkw, new_chain, cur_chain):
        """
        Finds a common ancestor of the two chains.
        """
        while cur_blkw.identifier != \
                new_blkw.identifier:
            if cur_blkw.previous_block_id ==  \
                    NULL_BLOCK_IDENTIFIER or \
                    new_blkw.previous_block_id == \
                    NULL_BLOCK_IDENTIFIER:
                # We are at a genesis block and the blocks are not the
                # same
                LOGGER.info("Block rejected due to wrong genesis: %s %s",
                            cur_blkw, new_blkw)
                for b in new_chain:
                    b.status = BlockStatus.Invalid
                self._done_cb(False, self._result)
                raise BlockValidationAborted()
            new_chain.append(new_blkw)
            new_blkw = \
                self._block_cache[
                    new_blkw.previous_block_id]

            cur_chain.append(cur_blkw)
            cur_blkw = \
                self._block_cache[cur_blkw.previous_block_id]

    def _compare_forks(self, new_chain, cur_chain):
        """
        Compare the two chains and determine which should be the head.
        """
        fork_resolver = self._consensus_module.\
            ForkResolver(block_cache=self._block_cache)

        return fork_resolver.compare_forks(self._chain_head, self._new_block)

    def _compute_batch_change(self, new_chain, cur_chain):
        """
        Compute the batch change sets.
        """
        committed_txn = []
        for blkw in new_chain:
            for batch in blkw.batches:
                committed_txn = committed_txn + list(batch.transactions)

        uncommitted_txn = []
        for blkw in cur_chain:
            for batch in blkw.batches:
                uncommitted_txn = uncommitted_txn + list(batch.transactions)

        return (committed_txn, uncommitted_txn)

    def run(self):
        """
        Main entry for Block Validation, Take a given candidate block
        and decide if it is valid then if it is valid determine if it should
        be the new head block. Returns the results to the ChainController
        so that the change over can be made if necessary.
        """
        try:
            LOGGER.info("Starting block validation of : %s",
                        self._new_block)
            cur_chain = self._result["cur_chain"]  # ordered list of the
            # current chain blocks
            new_chain = self._result["new_chain"]  # ordered list of the new
            # chain blocks

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
            committed_txn = TransactionCache(self._block_cache.block_store)
            for block in cur_chain:
                for batch in block.batches:
                    committed_txn.uncommit_batch(batch)

            valid = True
            for block in reversed(new_chain):
                if valid:
                    if not self._validate_block(block, committed_txn):
                        LOGGER.info("Block validation failed: %s", block)
                        valid = False
                else:
                    LOGGER.info("Block marked invalid(invalid predecessor): " +
                                "%s", block)
                    block.status = BlockStatus.Invalid

            if not valid:
                self._done_cb(False, self._result)
                return

            # 4) Evaluate the 2 chains to see which is the one true chain.
            commit_new_chain = self._compare_forks(new_chain, cur_chain)

            # 5) Consensus to compute batch sets (only if we are switching).
            if commit_new_chain:
                (self._result["committed_batches"],
                 self._result["uncommitted_batches"]) =\
                    self._compute_batch_change(new_chain, cur_chain)

            # 6) Tell the journal we are done.
            self._done_cb(commit_new_chain,
                          self._result)
            LOGGER.info("Finished block validation of: %s",
                        self._new_block)
        except BlockValidationAborted:
            return

        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error("Block validation failed with unexpected error: %s",
                         self._new_block)
            LOGGER.exception(exc)
            self._done_cb(False)  # callback to clean up the block out of the
            # processing list.


class ChainController(object):
    """
    To evaluating new blocks to determine if they should extend or replace
    the current chain. If they are valid extend the chain.
    """
    def __init__(self,
                 block_cache,
                 block_sender,
                 state_view_factory,
                 executor,
                 transaction_executor,
                 on_chain_updated,
                 squash_handler):
        """Initialize the ChainController
        Args:
            algorithm to use.
             block_cache: The cache of all recent blocks and the processing
             state associated with them.
             block_sender: an interface object used to send blocks to the
             network.
             state_view_factory: The factory object to create
             executor: The thread pool to process block validations.
             transaction_executor: The TransactionExecutor used to produce
             schedulers for batch validation.
             on_chain_updated: The callback to call to notify the rest of the
             system the head block in the chain has been changed.
             squash_handler: a parameter passed when creating transaction
             schedulers.
        Returns:
            None
        """
        self._lock = RLock()
        self._block_cache = block_cache
        self._block_store = block_cache.block_store
        self._state_view_factory = state_view_factory
        self._block_sender = block_sender
        self._executor = executor
        self._transaction_executor = transaction_executor
        self._notify_on_chain_updated = on_chain_updated
        self._sqaush_handler = squash_handler

        self._blocks_processing = {}  # a set of blocks that are
        # currently being processed.
        self._blocks_pending = {}  # set of blocks that the previous block
        # is being processed. Once that completes this block will be
        # scheduled for validation.

        try:
            self._chain_head = self._block_store.chain_head
            LOGGER.info("Chain controller initialized with chain head: %s",
                        self._chain_head)
        except Exception as exc:
            LOGGER.error("Invalid block store. Head of the block chain cannot "
                         "be determined")
            LOGGER.exception(exc)
            raise

        self._notify_on_chain_updated(self._chain_head)

    @property
    def chain_head(self):
        return self._chain_head

    def _verify_block(self, blkw):

        state_view = self._state_view_factory.create_view(
            self.chain_head.header.state_root_hash)
        consensus_module = ConsensusFactory.get_configured_consensus_module(
            state_view)

        validator = BlockValidator(
            consensus_module=consensus_module,
            new_block=blkw,
            chain_head=self._chain_head,
            block_cache=self._block_cache,
            state_view_factory=self._state_view_factory,
            done_cb=self.on_block_validated,
            executor=self._transaction_executor,
            squash_handler=self._sqaush_handler)
        self._blocks_processing[blkw.block.header_signature] = validator
        self._executor.submit(validator.run)

    def on_block_validated(self, commit_new_block, result):
        """Message back from the block validator, that the validation is
        complete
        Args:
        commit_new_block (Boolean): wether the new block should become the
        chain head or not.
        result (Dict): Map of the results of the fork resolution.
        Returns:
            None
        """
        try:
            with self._lock:
                new_block = result["new_block"]
                LOGGER.info("on_block_validated: %s", new_block)

                # remove from the processing list
                del self._blocks_processing[new_block.identifier]

                # if the head has changed, since we started the work.
                if result["chain_head"] != self._chain_head:
                    # chain has advanced since work started.
                    # the block validation work we have done is saved.
                    self._verify_block(new_block)
                elif commit_new_block:
                    self._chain_head = new_block

                    # update the the block store to have the new chain
                    self._block_store.update_chain(result["new_chain"],
                                                   result["cur_chain"])

                    LOGGER.info("Chain head updated to: %s", self._chain_head)

                    # tell the BlockPublisher else the chain is updated
                    self._notify_on_chain_updated(self._chain_head,
                                                  result["committed_batches"],
                                                  result["uncommitted_batches"]
                                                  )

                    pending_blocks = \
                        self._blocks_pending.pop(
                            self._chain_head.block.header_signature, [])
                    for pending_block in pending_blocks:
                        self._verify_block(pending_block)
        # pylint: disable=broad-except
        except Exception as exc:
            LOGGER.exception(exc)

    def on_block_received(self, block):
        try:
            with self._lock:
                if block.header_signature in self._block_store:
                    # do we already have this block
                    return

                self._block_cache[block.identifier] = block
                self._blocks_pending[block.identifier] = []
                LOGGER.debug("Block received: %s", block)
                if block.previous_block_id in self._blocks_processing or \
                        block.previous_block_id in self._blocks_pending:
                    LOGGER.debug('Block pending: %s', block)
                    # if the previous block is being processed, put it in a
                    # wait queue, Also need to check if previous block is
                    # in the wait queue.
                    pending_blocks = \
                        self._blocks_pending.get(block.previous_block_id,
                                                 [])
                    pending_blocks.append(block)
                    self._blocks_pending[block.previous_block_id] = \
                        pending_blocks
                else:
                    # schedule this block for validation.
                    self._verify_block(block)
        # pylint: disable=broad-except
        except Exception as exc:
            LOGGER.exception(exc)
