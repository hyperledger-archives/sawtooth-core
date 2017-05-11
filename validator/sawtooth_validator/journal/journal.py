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
from sawtooth_validator.journal.block_cache import BlockCache


LOGGER = logging.getLogger(__name__)


class Journal(object):
    """
    Manages the block chain, This responsibility boils down
    1) to evaluating new blocks to determine if they should extend or replace
    the current chain. Handled by the ChainController
    2) Claiming new blocks. Handled by the BlockPublisher.
    This object provides the threading and event queue for the processors.
    """
    class _ChainThread(Thread):
        def __init__(self, chain_controller, block_queue, block_cache,
                     block_cache_purge_frequency):
            Thread.__init__(self)
            self._chain_controller = chain_controller
            self._block_queue = block_queue
            self._block_cache = block_cache
            self._block_cache_purge_frequency = block_cache_purge_frequency
            self._exit = False

        def run(self):
            try:
                block_cache_purge_time = time.time() + \
                    self._block_cache_purge_frequency
                while True:
                    try:
                        block = self._block_queue.get(
                            timeout=self._block_cache_purge_frequency)
                        self._chain_controller.on_block_received(block)
                    except queue.Empty:
                        pass  # this exception only happens if the
                        # wait on an empty queue after it times out.

                    if block_cache_purge_time < time.time():
                        self._block_cache.purge_expired()
                        block_cache_purge_time = time.time() + \
                            self._block_cache_purge_frequency

                    if self._exit:
                        return
            # pylint: disable=broad-except
            except Exception as exc:
                LOGGER.exception(exc)
                LOGGER.critical("ChainController thread exited with error.")

        def stop(self):
            self._exit = True

    class _PublisherThread(Thread):
        def __init__(self, block_publisher, batch_queue,
                     check_publish_block_frequency):
            Thread.__init__(self)
            self._block_publisher = block_publisher
            self._batch_queue = batch_queue
            self._check_publish_block_frequency = \
                check_publish_block_frequency
            self._exit = False

        def run(self):
            try:
                # make sure we don't check to publish the block
                # to frequently.
                next_check_publish_block_time = time.time() + \
                    self._check_publish_block_frequency
                while True:
                    try:
                        batch = self._batch_queue.get(
                            timeout=self._check_publish_block_frequency)
                        self._block_publisher.on_batch_received(batch)
                    except queue.Empty:
                        pass  # this exception only happens if the
                        # wait on an empty queue after it times out.

                    if next_check_publish_block_time < time.time():
                        self._block_publisher.on_check_publish_block()
                        next_check_publish_block_time = time.time() + \
                            self._check_publish_block_frequency
                    if self._exit:
                        return
            # pylint: disable=broad-except
            except Exception as exc:
                LOGGER.exception(exc)
                LOGGER.critical("BlockPublisher thread exited with error.")

        def stop(self):
            self._exit = True

    def __init__(self,
                 block_store,
                 state_view_factory,
                 block_sender,
                 batch_sender,
                 transaction_executor,
                 squash_handler,
                 identity_signing_key,
                 chain_id_manager,
                 state_delta_processor,
                 data_dir,
                 check_publish_block_frequency=0.1,
                 block_cache_purge_frequency=30,
                 block_cache_keep_time=300,
                 block_cache=None):
        """
        Creates a Journal instance.

        Args:
            block_store (:obj:): The block store.
            state_view_factory (:obj:`StateViewFactory`): StateViewFactory for
                read-only state views.
            block_sender (:obj:`BlockSender`): The BlockSender instance.
            batch_sender (:obj:`BatchSender`): The BatchSender instance.
            transaction_executor (:obj:`TransactionExecutor`): A
                TransactionExecutor instance.
            squash_handler (function): Squash handler function for merging
                contexts.
            identity_signing_key (str): Private key for signing blocks
            chain_id_manager (:obj:`ChainIdManager`) The ChainIdManager
                instance.
            state_delta_processor (:obj:`StateDeltaProcessor`): The state
                delta processor.
            data_dir (str): directory for data storage.
            check_publish_block_frequency(float): delay in seconds between
                checks if a block should be claimed.
            block_cache_purge_frequency (float): delay in seconds between
            purges of the BlockCache.
            block_cache_keep_time (float): time in seconds to hold unaccess
            blocks in the BlockCache.
            block_cache (:obj:`BlockCache`, optional): A BlockCache to use in
                place of an internally created instance. Defaults to None.
        """
        self._block_store = block_store
        self._block_cache = block_cache
        if self._block_cache is None:
            self._block_cache = BlockCache(
                self._block_store, keep_time=block_cache_keep_time)
        self._block_cache_purge_frequency = block_cache_purge_frequency
        self._state_view_factory = state_view_factory

        self._transaction_executor = transaction_executor
        self._squash_handler = squash_handler
        self._identity_signing_key = identity_signing_key
        self._block_sender = block_sender
        self._batch_sender = batch_sender

        self._block_publisher = None
        self._check_publish_block_frequency = check_publish_block_frequency
        self._batch_queue = queue.Queue()
        self._publisher_thread = None

        self._chain_controller = None
        self._block_queue = queue.Queue()
        self._chain_thread = None
        self._chain_id_manager = chain_id_manager
        self._state_delta_processor = state_delta_processor
        self._data_dir = data_dir

    def _init_subprocesses(self):
        self._block_publisher = BlockPublisher(
            transaction_executor=self._transaction_executor,
            block_cache=self._block_cache,
            state_view_factory=self._state_view_factory,
            block_sender=self._block_sender,
            batch_sender=self._batch_sender,
            squash_handler=self._squash_handler,
            chain_head=self._block_store.chain_head,
            identity_signing_key=self._identity_signing_key,
            data_dir=self._data_dir
        )
        self._publisher_thread = self._PublisherThread(
            block_publisher=self._block_publisher,
            batch_queue=self._batch_queue,
            check_publish_block_frequency=self._check_publish_block_frequency
        )
        self._chain_controller = ChainController(
            block_sender=self._block_sender,
            block_cache=self._block_cache,
            state_view_factory=self._state_view_factory,
            executor=ThreadPoolExecutor(1),
            transaction_executor=self._transaction_executor,
            chain_head_lock=self._block_publisher.chain_head_lock,
            on_chain_updated=self._block_publisher.on_chain_updated,
            squash_handler=self._squash_handler,
            chain_id_manager=self._chain_id_manager,
            state_delta_processor=self._state_delta_processor,
            identity_signing_key=self._identity_signing_key,
            data_dir=self._data_dir
        )
        self._chain_thread = self._ChainThread(
            chain_controller=self._chain_controller,
            block_queue=self._block_queue,
            block_cache=self._block_cache,
            block_cache_purge_frequency=self._block_cache_purge_frequency
        )

    # FXM: this is an inaccurate name.
    def get_current_root(self):
        return self._chain_controller.chain_head.state_root_hash

    def get_block_store(self):
        return self._block_store

    def start(self):
        if self._publisher_thread is None and self._chain_thread is None:
            self._init_subprocesses()

        self._publisher_thread.start()
        self._chain_thread.start()

    def stop(self):
        # time to murder the child threads. First ask politely for
        # suicide
        if self._publisher_thread is not None:
            self._publisher_thread.stop()
            self._publisher_thread = None

        if self._chain_thread is not None:
            self._chain_thread.stop()
            self._chain_thread = None

    def on_block_received(self, block):
        """
        New block has been received, queue it with the chain controller
        for processing.
        """
        self._block_queue.put(block)

    def on_batch_received(self, batch):
        """
        New batch has been received, queue it with the BlockPublisher for
        inclusion in the next block.
        """
        self._batch_queue.put(batch)
