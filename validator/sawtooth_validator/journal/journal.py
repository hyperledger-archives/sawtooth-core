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
            self._chain_controller = chain_controller
            self._block_queue = block_queue
            self._exit = False

        def run(self):
            try:
                while True:
                    try:
                        block = self._block_queue.get(timeout=0.1)
                        self._chain_controller.on_block_received(block)
                    except queue.Empty:
                        time.sleep(0.1)
                    if self._exit:
                        return
            # pylint: disable=broad-except
            except Exception as exc:
                LOGGER.exception(exc)
                LOGGER.critical("BlockPublisher thread exited.")

        def stop(self):
            self._exit = True

    class _PublisherThread(Thread):
        def __init__(self, block_publisher, batch_queue):
            Thread.__init__(self)
            self._block_publisher = block_publisher
            self._batch_queue = batch_queue
            self._exit = False

        def run(self):
            try:
                while True:
                    try:
                        batch = self._batch_queue.get(timeout=0.1)
                        self._block_publisher.on_batch_received(batch)
                    except queue.Empty:
                        time.sleep(0.1)

                    self._block_publisher.on_check_publish_block()
                    if self._exit:
                        return
            # pylint: disable=broad-except
            except Exception as exc:
                LOGGER.exception(exc)
                LOGGER.critical("BlockPublisher thread exited.")

        def stop(self):
            self._exit = True

    def __init__(self,
                 consensus,
                 block_store,
                 block_sender,
                 transaction_executor,
                 squash_handler):
        self._consensus = consensus
        self._block_store = block_store
        self._transaction_executor = transaction_executor
        self._squash_handler = squash_handler
        self._block_sender = block_sender

        self._block_publisher = None
        self._batch_queue = queue.Queue()
        self._publisher_thread = None

        self._chain_controller = None
        self._block_queue = queue.Queue()
        self._chain_thread = None

    def _init_subprocesses(self):
        chain_head = self._get_chain_head()
        self._block_publisher = BlockPublisher(
            consensus=self._consensus.BlockPublisher(),
            transaction_executor=self._transaction_executor,
            block_sender=self._block_sender,
            squash_handler=self._squash_handler,
            chain_head=chain_head
        )
        self._publisher_thread = self._PublisherThread(self._block_publisher,
                                                       self._batch_queue)
        self._chain_controller = ChainController(
            consensus=self._consensus.BlockVerifier(),
            block_store=self._block_store,
            block_sender=self._block_sender,
            executor=ThreadPoolExecutor(1),
            transaction_executor=self._transaction_executor,
            on_chain_updated=self._block_publisher.on_chain_updated,
            squash_handler=self._squash_handler
        )
        self._chain_thread = self._ChainThread(self._chain_controller,
                                               self._block_queue)

    def _get_chain_head(self):
        if 'chain_head_id' in self._block_store:
            return self._block_store[self._block_store["chain_head_id"]]

        return None

    def get_current_root(self):
        chain_head = self._get_chain_head()
        return chain_head.block.state_root_hash if chain_head else None

    def get_block_store(self):
        return self._block_store

    def start(self):
        # TBD do load activities....
        # TBD transfer activities - request chain-head from
        # network
        if self._publisher_thread is None and self._chain_thread is None:
            self._init_subprocesses()

        self._publisher_thread.start()
        self._chain_thread.start()

    def stop(self):
        # time to murder the child threads. First ask politely for
        # suicide
        if self._publisher_thread is not None:
            self._publisher_thread.stop()
        if self._chain_thread is not None:
            self._chain_thread.stop()

    def on_block_received(self, block):
        self._block_queue.put(block)

    def on_batch_received(self, batch):
        self._batch_queue.put(batch)

    def on_block_request(self, block_id):
        if block_id in self._block_store:
            self._send_message.send(self._block_store[block_id].block)
