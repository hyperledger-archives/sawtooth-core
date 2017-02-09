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

from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER


LOGGER = logging.getLogger(__name__)


class BlockValidator(object):
    """
    Responsible for validating a block, handles both chain extensions and fork
    will determine if the new block should be the head of the chain and return
    the information necessary to do the switch if necessary.
    """
    def __init__(self, consensus,
                 block_cache,
                 new_block,
                 chain_head,
                 request_block_cb,
                 done_cb,
                 executor,
                 squash_handler):
        self._consensus = consensus
        self._block_cache = block_cache
        self._new_block = new_block
        self._chain_head = chain_head
        self._request_block_cb = request_block_cb
        self._done_cb = done_cb
        self._executor = executor
        self._squash_handler = squash_handler

    @property
    def new_block(self):
        return self._new_block

    @property
    def chain_head(self):
        return self._chain_head

    def _validate_block(self, block_state):
        try:
            if block_state.status == BlockStatus.Valid:
                return True
            elif block_state.status == BlockStatus.Invalid:
                return False
            else:
                valid = True

                # FXM verify header_signature

                if valid:
                    if len(block_state.block.batches) > 0:
                        scheduler = self._executor.create_scheduler(
                            self._squash_handler,

                            # FXM: This does not look Right!!!!!
                            # it should be the previous block state hash
                            # not the current chain head state root.
                            self.chain_head.state_root_hash)
                        self._executor.execute(scheduler)

                        for i in range(len(block_state.block.batches) - 1):
                            scheduler.add_batch(block_state.batches[i])
                        scheduler.add_batch(block_state.batches[-1],
                                            block_state.state_root_hash)
                        scheduler.finalize()
                        scheduler.complete(block=True)
                        state_hash = None
                        for i in range(len(block_state.batches)):
                            result = scheduler.get_batch_execution_result(
                                block_state.batches[i].header_signature)
                            # If the result is None, the executor did not
                            # receive the batch
                            if result is not None and result.is_valid:
                                state_hash = result.state_hash
                            else:
                                valid = False
                        if block_state.state_root_hash != state_hash:
                            valid = False
                if valid:
                    valid = self._consensus.verify_block(block_state)

                # Update the block store
                block_state.weight = \
                    self._consensus.compute_block_weight(block_state)
                block_state.status = BlockStatus.Valid if \
                    valid else BlockStatus.Invalid
                return valid
        # pylint: disable=broad-except
        except Exception as exc:
            LOGGER.error(exc)
            return False

    def run(self):
        try:
            LOGGER.info("Starting block validation of : %s",
                        self._new_block)
            current_chain = []  # ordered list of the current chain
            new_chain = []

            new_block_state = self._new_block
            current_block_state = self._chain_head

            # 1) find the common ancestor of this block in the current chain
            # Walk back until we have both chains at the same length
            while new_block_state.block_num > \
                    current_block_state.block_num\
                    and new_block_state.previous_block_id != \
                    NULL_BLOCK_IDENTIFIER:
                new_chain.append(new_block_state)
                try:
                    new_block_state = \
                        self._block_cache[
                            new_block_state.previous_block_id]
                except KeyError:
                    # required block is missing
                    self._request_block_cb(
                        new_block_state.block.previous_block_id, self)
                    return

            while current_block_state.block_num > \
                    new_block_state.block_num \
                    and new_block_state.previous_block_id != \
                    NULL_BLOCK_IDENTIFIER:
                current_chain.append(current_block_state)
                current_block_state = \
                    self._block_cache[
                        current_block_state.previous_block_id]

            # 2) now we have both chain at the same block number
            # continue walking back until we find a common block.

            while current_block_state.identifier != \
                    new_block_state.identifier:
                if current_block_state.previous_block_id ==  \
                        NULL_BLOCK_IDENTIFIER or \
                        new_block_state.previous_block_id == \
                        NULL_BLOCK_IDENTIFIER:
                    # We are at a genesis block and the blocks are not the
                    # same
                    LOGGER.info("Block rejected due to wrong genesis: %s %s",
                                current_block_state,
                                new_block_state)

                    self._done_cb(False,
                                  new_chain,
                                  current_chain,
                                  self._chain_head)
                    return
                new_chain.append(new_block_state)
                new_block_state = \
                    self._block_cache[
                        new_block_state.previous_block_id]

                current_chain.append(current_block_state)
                current_block_state = \
                    self._block_cache[
                        current_block_state.previous_block_id]

            # 3) We now have the root of the fork.
            # determine the validity of the new fork
            for block in reversed(new_chain):
                if not self._validate_block(block):
                    LOGGER.info("Block validation failed: %s",
                                block)
                    self._done_cb(False,
                                  new_chain,
                                  current_chain,
                                  self._chain_head)
                    return

            # 4) new chain is valid... should we switch to it?
            commit_new_chain = new_chain[0].weight > self._chain_head.weight

            # Tell the journal we are done
            self._done_cb(commit_new_chain,
                          new_chain,
                          current_chain,
                          self._chain_head)
            LOGGER.info("Finished block validation of: %s",
                        self._new_block)
        # pylint: disable=broad-except
        except Exception as exc:
            LOGGER.error("Block validation failed with unexpected error: %s",
                         self._new_block)
            LOGGER.exception(exc)


class ChainController(object):
    """
    To evaluating new blocks to determine if they should extend or replace
    the current chain. If they are valid extend the chain.
    """
    def __init__(self,
                 consensus,
                 block_cache,
                 block_sender,
                 executor,
                 transaction_executor,
                 on_chain_updated,
                 squash_handler):
        self._lock = RLock()
        self._consensus = consensus
        self._block_cache = block_cache
        self._block_store = block_cache.block_store
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

    def _verify_block(self, block_state):
        validator = BlockValidator(
            consensus=self._consensus,
            new_block=block_state,
            chain_head=self._chain_head,
            block_cache=self._block_cache,
            request_block_cb=self._request_block,
            done_cb=self.on_block_validated,
            executor=self._transaction_executor,
            squash_handler=self._sqaush_handler)
        self._blocks_processing[block_state.block.header_signature] = validator
        self._executor.submit(validator.run)

    def _request_block(self, block_id, validator):
        # TBD add request time and time out
        self._blocks_requested[block_id] = validator

    def on_block_validated(self,
                           commit_new_block,
                           new_chain,
                           current_chain,
                           chain_head):
        """
        Message back from the block validator,
        :param block:
        :return:
        """
        try:
            with self._lock:
                new_block = new_chain[0]
                LOGGER.info("on_block_validated : %s", new_block)

                # remove from the processing list
                del self._blocks_processing[new_block.identifier]

                # if the head has changed, since we started the work.
                if chain_head != self._chain_head:
                    # chain has advanced since work started.
                    # the block validation work we have done is saved.
                    self._verify_block(new_block)
                elif commit_new_block:
                    self._chain_head = new_block

                    for b in new_chain:
                        self._block_store[b.identifier] = b

                    self._block_store.set_chain_head(new_block.identifier)

                    for b in current_chain:
                        del self._block_store[b.identifier]

                    LOGGER.info("Chain head updated to: %s",
                                self._chain_head)
                    # tell everyone else the chain is updated
                    self._notify_on_chain_updated(self._chain_head)

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
                if block.identifier in self._blocks_requested:
                    # is it a requested block
                    # route block to the validator that requested
                    validator = self._blocks_requested.pop(block.identifier)
                    if validator.chain_head.block.identifier != \
                            self._chain_head.block.identifier:
                        # the head of the chain has changed start over
                        self._verify_block(validator.new_block)
                    else:
                        self._executor.submit(validator.run)
                elif block.previous_block_id in self._blocks_processing or \
                        block.previous_block_id in self._blocks_pending:
                    LOGGER.debug('in blocks pending: %s', block)
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
