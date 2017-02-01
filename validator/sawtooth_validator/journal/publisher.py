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
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.execution.scheduler_exceptions import SchedulerError

LOGGER = logging.getLogger(__name__)

NULLIDENTIFIER = "0000000000000000"


class BlockPublisher(object):
    """
    Responsible for generating new blocks and publishing them when the
    Consensus deems it appropriate.
    """
    def __init__(self,
                 consensus,
                 transaction_executor,
                 block_sender,
                 squash_handler,
                 chain_head):
        self._lock = RLock()
        self._candidate_block = None  # the next block in potentia
        self._consensus = consensus  # the consensus object.
        self._transaction_executor = transaction_executor
        self._pending_batches = []  # batches we are waiting for
        self._validated_batches = []
        self._block_sender = block_sender
        self._scheduler = None
        self._chain_head = chain_head
        self._squash_handler = squash_handler

    def _build_block(self, chain_head):
        """ Build a candidate block
        """
        block_header = BlockHeader(
            block_num=chain_head.block_num + 1,
            previous_block_id=chain_head.header_signature)
        self._consensus.initialize_block(block_header)

        # create a new scheduler
        # TBD move factory in to executor for easier mocking --
        # Yes I want to make fun of it.
        self._scheduler = self._transaction_executor.create_scheduler(
            self._squash_handler, chain_head.state_root_hash)

        self._transaction_executor.execute(self._scheduler)
        for batch in self._pending_batches:
            self._scheduler.add_batch(batch)
        self._pending_batches = []
        block = BlockWrapper(block_header)
        return block

    def _sign_block(self, block):
        """ The block should be complete and the final
        signature from the publishing validator(this validator) needs to
        be added.
        """
        # Temp signature creation to use as identifier
        temp_key = signing.generate_privkey()
        public_key = signing.encode_pubkey(
            signing.generate_pubkey(temp_key), "hex")

        block.block_header.signer_pubkey = public_key
        block_header = block.block_header
        header_bytes = block_header.SerializeToString()
        signature = signing.sign(
            header_bytes,
            temp_key)
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
        with self._lock:
            LOGGER.info(
                'Chain updated, new head: num=%s id=%s state=%s prev=%s',
                chain_head.block_num,
                chain_head.header_signature,
                chain_head.state_root_hash,
                chain_head.previous_block_id)
            self._chain_head = chain_head
            if self._candidate_block is not None and \
                    chain_head is not None and \
                    chain_head.header_signature == \
                    self._candidate_block.previous_block_id:
                # nothing to do. We are building of the current head.
                # This can happen after we publish a block and speculatively
                # create a new block.
                return
            else:
                # TBD -- we need to rebuild the pending transaction queue --
                # which could be an unknown set depending if we switched forks

                # new head of the chain.
                self._candidate_block = self._build_block(chain_head)

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
        self._consensus.finalize_block(block.block_header)
        if state_hash is not None:
            block.set_state_hash(state_hash)
        self._sign_block(block)
        return block

    def on_check_publish_block(self, force=False):
        """
            Ask the consensus module if it is time to claim the candidate block
            if it is then, claim it and tell the world about it.
        :return:
        """
        with self._lock:
            if self._candidate_block is None and len(self._pending_batches) \
                    != 0:
                self._candidate_block = self._build_block(self._chain_head)

            if self._candidate_block and \
                    (force or len(self._pending_batches) != 0) and \
                    self._consensus.check_publish_block(self._candidate_block):
                candidate = self._candidate_block
                self._candidate_block = None
                candidate = self._finalize_block(candidate)
                # if no batches are in the block, do not send it out
                if len(candidate.batches) == 0:
                    LOGGER.info("No Valid batches added to block, dropping %s",
                                candidate.header_signature)
                    return

                self._block_sender.send(candidate.get_block())

                LOGGER.info("Claimed Block: %s", candidate.header_signature)

                # create a new block based on this one -- opportunistically
                # assume the published block is the valid block.
                self.on_chain_updated(candidate)
