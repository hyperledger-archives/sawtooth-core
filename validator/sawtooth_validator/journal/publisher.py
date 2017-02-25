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
import copy
import logging
from threading import RLock

from sawtooth_signing import pbct as signing

from sawtooth_validator.execution.scheduler_exceptions import SchedulerError

from sawtooth_validator.journal.block_builder import BlockBuilder
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.consensus.consensus_factory import \
    ConsensusFactory

from sawtooth_validator.protobuf.block_pb2 import BlockHeader

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
        Creates a Journal instance.

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
        self._pending_batches = []  # batches we are waiting for validation
        self._validated_batches = []  # batches that are valid and can be added
        # to the next block.
        self._scheduler = None
        self._chain_head = chain_head  # block (BlockWrapper)
        self._squash_handler = squash_handler
        self._identity_signing_key = identity_signing_key
        self._identity_public_key = signing.encode_pubkey(
            signing.generate_pubkey(self._identity_signing_key), "hex")

    def _get_previous_block_root_state_hash(self, blkw):
        if blkw.previous_block_id == NULL_BLOCK_IDENTIFIER:
            return INIT_ROOT_KEY
        else:
            prev_blkw = self._block_cache[blkw.previous_block_id]
            return prev_blkw.state_root_hash

    def _build_block(self, chain_head):
        """ Build a candidate block and construct the consensus object to
        validate it.
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
            self._scheduler.add_batch(batch)
        self._pending_batches = []
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

    def on_batch_received(self, batch):
        """
        A new batch is received, send it for validation
        :param block:
        :return:
        """
        with self._lock:
            if self._chain_head is None:
                # We are not ready to process batches
                return

            self._pending_batches.append(batch)
            if self._scheduler:
                try:
                    self._scheduler.add_batch(batch)
                except SchedulerError:
                    pass

    def on_chain_updated(self, chain_head,
                         committed_batches=None,
                         uncommitted_batches=None):
        """
        The existing chain has been updated, the current head block has
        changed.

        chain_head: the new head of block_chain
        committed_batches:
        uncommitted_batches: the list of transactions if any that are now
            de-committed due to the switch in forks.

        :return:
        """
        try:
            with self._lock:
                LOGGER.info(
                    'Now building on top of block: %s',
                    chain_head)
                self._chain_head = chain_head
                if self._candidate_block is not None and \
                        chain_head is not None and \
                        chain_head.identifier == \
                        self._candidate_block.previous_block_id:
                    # nothing to do. We are building of the current head.
                    # This can happen after we publish a block and
                    # speculatively create a new block.
                    return
                else:
                    # TBD -- we need to rebuild the pending transaction queue
                    # which could be an unknown set depending if we switched
                    # forks new head of the chain.
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
        pending_batches = copy.copy(self._pending_batches)
        self._pending_batches = []

        state_hash = None
        for batch in pending_batches:
            result = self._scheduler.get_batch_execution_result(
                batch.header_signature)
            # if a result is None, this means that the executor never
            # received the batch and it should be added to
            # the pending_batches
            if result is None:
                self._pending_batches.append(batch)
            elif result.is_valid:
                self._validated_batches.append(batch)
                state_hash = result.state_hash

        block.add_batches(self._validated_batches)
        self._validated_batches = []

        # might need to take state_hash
        self._consensus.finalize_block(block)
        if state_hash is not None:
            block.set_state_hash(state_hash)
        self._sign_block(block)
        self._consensus = None

        return block

    def on_check_publish_block(self, force=False):
        """
            Ask the consensus module if it is time to claim the candidate block
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
