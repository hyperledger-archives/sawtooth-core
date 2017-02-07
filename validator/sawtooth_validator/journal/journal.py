# Copyright 2016 Intel Corporation
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

from concurrent.futures import ThreadPoolExecutor
import logging
import queue
from threading import Thread
import time

from sawtooth_validator.journal.publisher import BlockPublisher
from sawtooth_validator.journal.chain import ChainController
from sawtooth_validator.journal.block_wrapper import BlockState
from sawtooth_validator.journal.block_wrapper import BlockStatus

LOGGER = logging.getLogger(__name__)


NULLIDENTIFIER = "0000000000000000"


class Journal(object):
    """
    Manages the block chain, This responsibility boils down
    1) to evaluating new blocks to determine if they should extend or replace
    the current chain. Handled by the ChainController/
    2) Claiming new blocks, handled by the BlockPublisher

    This object provides the threading and event queue for the processors.

    """

    class _ChainThread(Thread):
        def __init__(self, chain_controller, block_queue):
            Thread.__init__(self)
            self._block_publisher = chain_controller
            self._block_queue = block_queue
            self._exit = False

        def run(self):
            while True:
                try:
                    block = self._block_queue.get(timeout=0.1)
                    self._block_publisher.on_block_received(block)
                except queue.Empty:
                    time.sleep(0.1)
                if self._exit:
                    return

        def stop(self):
            self._exit = True

    class _PublisherThread(Thread):
        def __init__(self, block_publisher, batch_queue):
            Thread.__init__(self)
            self._block_publisher = block_publisher
            self._batch_queue = batch_queue
            self._exit = False

        def run(self):
            while True:
                try:
                    batch = self._batch_queue.get(timeout=0.1)
                    self._block_publisher.on_batch_received(batch)
                except queue.Empty:
                    time.sleep(0.1)

                self._block_publisher.on_check_publish_block()
                if self._exit:
                    return

        def stop(self):
            self._exit = True

    def __init__(self,
                 consensus,
                 block_store,
                 send_message,
                 transaction_executor,
                 squash_handler,
                 first_state_root):
        self._consensus = consensus
        self._block_store = block_store
        self._send_message = send_message
        self._squash_handler = squash_handler

        self._block_publisher = BlockPublisher(
            consensus=consensus.BlockPublisher(),
            transaction_executor=transaction_executor,
            send_message=send_message,
            squash_handler=squash_handler
        )
        self._batch_queue = queue.Queue()
        self._publisher_thread = self._PublisherThread(self._block_publisher,
                                                       self._batch_queue)
        # HACK until genesis tool is working
        if "chain_head_id" not in self._block_store:
            genesis_block = BlockState(
                block_wrapper=self._block_publisher.generate_genesis_block(),
                weight=0,
                status=BlockStatus.Valid)
            genesis_block.block.set_state_hash(first_state_root)

            self._block_store[genesis_block.block.header_signature] = \
                genesis_block
            self._block_store["chain_head_id"] = \
                genesis_block.block.header_signature
            self._block_publisher.on_chain_updated(genesis_block.block)
            LOGGER.info("Journal created genesis block: %s",
                        genesis_block.block.header_signature)

        self._chain_controller = ChainController(
            consensus=consensus.BlockVerifier(),
            block_store=block_store,
            send_message=send_message,
            executor=ThreadPoolExecutor(1),
            transaction_executor=transaction_executor,
            on_chain_updated=self._block_publisher.on_chain_updated,
            squash_handler=self._squash_handler
        )
        self._block_queue = queue.Queue()
        self._chain_thread = self._ChainThread(self._chain_controller,
                                               self._block_queue)

    def get_current_root(self):
        # return self._block_publisher._chain_head.state_root_hash
        return self._chain_controller.chain_head.block.state_root_hash

    def get_block_store(self):
        return self._block_store

    def start(self):
        # TBD do load activities....
        # TBD transfer activities - request chain-head from
        # network
        self._publisher_thread.start()
        self._chain_thread.start()

    def stop(self):
        # time to murder the child threads. First ask politely for
        # suicide
        self._publisher_thread.stop()
        self._chain_thread.stop()

    def on_block_received(self, block):
        self._block_queue.put(block)

    def on_batch_received(self, batch):
        self._batch_queue.put(batch)

    def on_block_request(self, block_id):
        if block_id in self._block_store:
            self._send_message(self._block_store[block_id].block)
