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

from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import BlockState
from sawtooth_validator.journal.block_wrapper import BlockStatus

LOGGER = logging.getLogger(__name__)

NULLIDENTIFIER = "0000000000000000"


class BlockValidator(object):
    """
    Responsible for validating a block, handles both chain extensions and fork
    will determine if the new block should be the head of the chain and

    """
    def __init__(self, consensus,
                 block_store,
                 new_block,
                 chain_head,
                 request_block_cb,
                 done_cb,
                 executor,
                 squash_handler):
        self._consensus = consensus
        self._block_store = block_store
        self._new_block = new_block
        self._chain_head = chain_head
        self._request_block_cb = request_block_cb
        self._done_cb = done_cb
        self._executor = executor
        self._squash_handler = squash_handler
        self._commit_new_block = False

    def commit_new_block(self):
        return self._commit_new_block

    @property
    def new_block(self):
        return self._new_block

    @property
    def chain_head(self):
        return self._chain_head

    def _validate_block(self, block_state):
        if block_state.status == BlockStatus.Valid:
            return True
        elif block_state.status == BlockStatus.Invalid:
            return False
        else:
            valid = True
            # verify header_signature

            if valid:
                if len(block_state.block.batches) > 0:
                    scheduler = self._executor.create_scheduler(
                        self._squash_handler,
                        self.chain_head.block.state_root_hash)
                    self._executor.execute(scheduler)

                    for i in range(len(block_state.block.batches) - 1):
                        scheduler.add_batch(block_state.block.batches[i])
                    scheduler.add_batch(block_state.block.batches[-1],
                                        block_state.block.state_root_hash)
                    scheduler.finalize()
                    scheduler.complete(block=True)
                    state_hash = None
                    for i in range(len(block_state.block.batches)):
                        result = scheduler.get_batch_execution_result(
                            block_state.block.batches[i].header_signature)
                        # If the result is None, the executor did not
                        # receive the batch
                        if result is not None and result.is_valid:
                            state_hash = result.state_hash
                        else:
                            valid = False
                    if block_state.block.state_root_hash != state_hash:
                        valid = False
            if valid:
                valid = self._consensus.verify_block(block_state)

            # Update the block store
            block_state.weight = \
                self._consensus.compute_block_weight(block_state)
            block_state.status = BlockStatus.Valid if \
                valid else BlockStatus.Invalid

            LOGGER.debug('updating block store for %s',
                         block_state.block.header_signature)
            self._block_store[block_state.block.header_signature] = block_state
            return valid

    def run(self):
        LOGGER.info("Starting block validation of : %s",
                    self._new_block.block.header_signature)
        current_chain = []  # ordered list of the current chain
        new_chain = []

        new_block_state = self._new_block
        current_block_state = self._chain_head
        # 1) find the common ancestor of this block in the current chain
        # Walk back until we have both chains at the same length
        while new_block_state.block.block_num > \
                current_block_state.block.block_num\
                and new_block_state.block.previous_block_id != \
                NULLIDENTIFIER:
            new_chain.append(new_block_state)
            try:
                new_block_state = \
                    self._block_store[
                        new_block_state.block.previous_block_id]
            except KeyError:
                # required block is missing
                self._request_block_cb(
                    new_block_state.block.previous_block_id, self)
                return

        while current_block_state.block.block_num > \
                new_block_state.block.block_num \
                and new_block_state.block.previous_block_id != \
                NULLIDENTIFIER:
            current_chain.append(current_block_state)
            current_block_state = \
                self._block_store[
                    current_block_state.block.previous_block_id]

        # 2) now we have both chain at the same block number
        # continue walking back until we find a common block.
        while current_block_state.block.header_signature != \
                new_block_state.block.header_signature:
            if current_block_state.block.previous_block_id ==  \
                    NULLIDENTIFIER or \
                    new_block_state.block.previous_block_id == \
                    NULLIDENTIFIER:
                # We are at a genesis block and the blocks are not the
                # same
                LOGGER.info("Block rejected due to wrong genesis : %s %s",
                            current_block_state.block.header_signature,
                            new_block_state.block.header_signature)

                self._done_cb(self)
                return
            new_chain.append(new_block_state)
            new_block_state = \
                self._block_store[
                    new_block_state.block.previous_block_id]

            current_chain.append(current_block_state)
            current_block_state = \
                self._block_store[
                    current_block_state.block.previous_block_id]

        # 3) We now have the root of the fork.
        # determine the validity of the new fork
        for block in reversed(new_chain):
            if not self._validate_block(block):
                LOGGER.info("Block validation failed: %s",
                            block)
                self._done_cb(self)
                return

        # 4) new chain is valid... should we switch to it?
        LOGGER.info("Finished block validation of XXXX: %s, %s",
                    new_chain[0].weight, self._chain_head.weight)
        self._commit_new_block = new_chain[0].weight > self._chain_head.weight

        # Tell the journal we are done
        self._done_cb(self)
        LOGGER.info("Finished block validation of : %s",
                    self._new_block.block.header_signature)


class ChainController(object):
    """
    To evaluating new blocks to determine if they should extend or replace
    the current chain. If they are valid extend the chain.
    """
    def __init__(self,
                 consensus,
                 block_store,
                 block_sender,
                 executor,
                 transaction_executor,
                 on_chain_updated,
                 squash_handler):
        self._lock = RLock()
        self._consensus = consensus
        self._block_store = block_store
        self._block_sender = block_sender
        self._executor = executor
        self._transaction_executor = transaction_executor
        self._notify_on_chain_updated = on_chain_updated
        self._sqaush_handler = squash_handler

        self._blocks_requested = {}  # a set of blocks that were requested.
        self._blocks_processing = {}  # a set of blocks that are
        # currently being processed.
        self._blocks_pending = {}  # set of blocks that the previous block
        # is being processed. Once that completes this block will be
        # scheduled for validation.

        try:
            self._chain_head = \
                self._block_store[self._block_store["chain_head_id"]]

            LOGGER.info("Chain controller initialized with chain head: %s",
                        self._chain_head.block.header_signature)
        except Exception as e:
            LOGGER.error("Invalid block store. Head of the block chain cannot "
                         "be determined: %s", e)
            raise

        self._notify_on_chain_updated(self._chain_head.block)

    @property
    def chain_head(self):
        return self._chain_head

    def _verify_block(self, block_state):
        validator = BlockValidator(
            consensus=self._consensus,
            new_block=block_state,
            chain_head=self._chain_head,
            block_store=self._block_store,
            request_block_cb=self._request_block,
            done_cb=self.on_block_validated,
            executor=self._transaction_executor,
            squash_handler=self._sqaush_handler)
        self._blocks_processing[block_state.block.header_signature] = validator
        self._executor.submit(validator.run)

    def _request_block(self, block_id, validator):
        # TBD add request time and time out
        self._blocks_requested[block_id] = validator

    def on_block_validated(self, validator):
        """
        Message back from the block validator
        :param block:
        :return:
        """
        with self._lock:
            LOGGER.info("on_block_validated : %s",
                        validator.new_block.block.header_signature)
            # remove from the processing list
            del self._blocks_processing[
                validator.new_block.block.header_signature]

            # if the head has changed, since we started the work.
            if validator.chain_head != self._chain_head:
                # chain has advanced since work started.
                # the block validation work we have done is saved.
                self._verify_block(validator.new_block)
            elif validator.commit_new_block():
                print('****** commit the chain! ****')
                self._chain_head = validator.new_block
                self._block_store["chain_head_id"] = \
                    self._chain_head.block.header_signature
                LOGGER.info("Chain head updated to: %s",
                            self._chain_head.block.header_signature)
                # tell everyone else the chain is updated
                self._notify_on_chain_updated(self._chain_head.block)

                pending_blocks = \
                    self._blocks_pending.pop(
                        self._chain_head.block.header_signature, [])
                for pending_block in pending_blocks:
                    self._verify_block(pending_block)

    def on_block_received(self, block):
        with self._lock:
            if block.header_signature in self._block_store:
                LOGGER.debug('already have block %s', block.header_signature)
                # do we already have this block
                return
            header = BlockHeader()
            header.ParseFromString(block.header)
            block = BlockWrapper(header, block)

            LOGGER.debug('inserting block %s', block.header_signature)
            block_state = BlockState(block_wrapper=block, weight=0,
                                     status=BlockStatus.Unknown)
            self._block_store[block.header_signature] = block_state
            self._blocks_pending[block.header_signature] = []
            if block.header_signature in self._blocks_requested:
                # is it a requested block
                # route block to the validator that requested
                validator = self._blocks_requested.pop(block.header_signature)
                if validator.chain_head.block.header_signature != \
                        self._chain_head.block.header_signature:
                    # the head of the chain has changed start over
                    self._verify_block(validator.new_block)
                else:
                    self._executor.submit(validator.run)
            elif block.previous_block_id in self._blocks_processing or \
                    block.previous_block_id in self._blocks_pending:
                LOGGER.debug('in blocks pending: %s', block.header_signature)
                # if the previous block is being processed...put it in a wait
                # queue, Also need to check if previous block is in a wait
                # queue.
                pending_blocks = \
                    self._blocks_pending.get(block.previous_block_id,
                                             [])
                pending_blocks.append(block_state)
                self._blocks_pending[block.previous_block_id] = \
                    pending_blocks
            else:
                # schedule this block for validation.
                self._verify_block(block_state)
