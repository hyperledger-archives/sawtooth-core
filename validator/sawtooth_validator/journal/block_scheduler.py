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
from sawtooth_validator.concurrent.atomic import ConcurrentSet
from sawtooth_validator.concurrent.atomic import ConcurrentMultiMap

from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER


LOGGER = logging.getLogger(__name__)


class _BlockValidationSchedulerThread(InstrumentedThread):
    """This thread's job is to pull blocks off of the queue and to submit them
    for scheduling."""
    def __init__(self, block_queue, submit_function, exit_poll_interval=1):
        super().__init__(name='_BlockValidationSchedulerThread')
        self._block_queue = block_queue
        self._submit_function = submit_function
        self._exit_poll_interval = exit_poll_interval
        self._exit = False

    def run(self):
        while True:
            try:
                # Set timeout so we can check if the thread has been stopped
                block = self._block_queue.get(timeout=self._exit_poll_interval)
                self._submit_function(block)

            except queue.Empty:
                pass

            if self._exit:
                return

    def stop(self):
        self._exit = True


class BlockValidationScheduler:
    """BlockValidationScheduler is responsible for receiving blocks from an
    incoming queue and determining when they are ready to be validated. A block
    is ready to be validated when:

        1. All predecessor blocks are known (if this is not true, it is
           considered an error as it should be guaranteed by the completer)
        2. All predecesor blocks have been validated

    The BlockValidationScheduler does not do any validation itself.
    """

    def __init__(self, incoming, outgoing, block_cache):
        self._incoming = incoming
        self._outgoing = outgoing
        self._block_cache = block_cache

        # In process
        self._blocks_processing = ConcurrentSet()

        # Pending
        self._blocks_pending = ConcurrentSet()
        self._block_dependencies = ConcurrentMultiMap()

        self._receive_thread = _BlockValidationSchedulerThread(
            self._incoming, self.handle_incoming_block)

    def start(self):
        self._receive_thread.start()

    def stop(self):
        self._receive_thread.stop()

    def on_block_validated(self, block_id):
        """Listen for blocks that have been processed and schedule blocks that
        are now ready for processing.
        """
        LOGGER.debug("Removing block from processing %s", block_id)
        self._blocks_processing.remove(block_id)
        for block in self.release_pending_blocks(block_id):
            self.schedule_block(block)

    def handle_incoming_block(self, block):
        """Handle the block on the incoming queue."""
        # If we already have the block, just drop it
        if block.header_signature in self._block_cache:
            LOGGER.debug("Received duplicate block: %s", block)
            return

        LOGGER.debug("Received block: %s", block)

        self._block_cache[block.header_signature] = block

        # If this is a genesis block, schedule it immediately
        if block.previous_block_id == NULL_BLOCK_IDENTIFIER:
            LOGGER.debug("Scheduling genesis block: %s", block)
            self.schedule_block(block)
            return

        # If predecessor is not in block cache, something external is wrong
        # and all we can do is report an error
        try:
            previous = self._block_cache[block.previous_block_id]
        except KeyError:
            LOGGER.error("Received block with missing predecessor: %s", block)
            return

        # If predecessor's status is known, put the block in outgoing
        if previous.status != BlockStatus.Unknown:
            LOGGER.debug("Scheduling block: %s", block)
            self.schedule_block(block)
            return

        # If predecessor's status is unknown, and in inproc or pending, add to
        # pending
        if self.is_pending(previous.header_signature):
            LOGGER.debug(
                "Previous block is pending, adding block to pending: %s",
                block)
            self.add_to_pending(block)
            return

        if self.is_processing(previous.header_signature):
            LOGGER.debug(
                "Previous block is processing, adding block to pending: %s",
                block)
            self.add_to_pending(block)
            return

        # If predecessor's status is unknown, and not inproc or pending,
        # something is very wrong.
        LOGGER.error("Received block before predecessor: %s", block)

    def schedule_block(self, block):
        self._outgoing.put(block)
        self._blocks_processing.add(block.header_signature)

    def add_to_pending(self, block):
        """Add the block to pending so it can be scheduled when its dependencies
        are done."""
        self._blocks_pending.add(block.header_signature)
        self._block_dependencies.append_if_unique(
            block.previous_block_id,
            block,
            lambda a, b: a.header_signature == b.header_signature)

    def is_pending(self, block_id):
        """Return whether this block is pending validation."""
        return block_id in self._blocks_pending

    def is_processing(self, block_id):
        """Return whether this block is being validated."""
        return block_id in self._blocks_processing

    def release_pending_blocks(self, block_id):
        """Remove blocks that were pending on the validation of the block with
        block_id."""
        ready = self._block_dependencies.pop(block_id, [])
        block_ids = [block.header_signature for block in ready]
        self._blocks_pending.remove_all(block_ids)
        return ready
