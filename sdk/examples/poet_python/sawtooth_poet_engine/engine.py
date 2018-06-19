# Copyright 2018 Intel Corporation
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
# -----------------------------------------------------------------------------

import logging
import queue
import time

from sawtooth_sdk.consensus.engine import Engine
from sawtooth_sdk.consensus import exceptions
from sawtooth_sdk.protobuf.validator_pb2 import Message

from sawtooth_poet_engine.oracle import PoetOracle, PoetBlock, NewBlockHeader


LOGGER = logging.getLogger(__name__)


class PoetEngine(Engine):
    def __init__(self, path_config, component_endpoint):
        # components
        self._path_config = path_config
        self._component_endpoint = component_endpoint
        self._service = None
        self._oracle = None

        # state variables
        self._exit = False
        self._published = False
        self._building = False
        self._committing = False

        self._pending_blocks = queue.Queue()

        time.sleep(10)

    def name(self):
        return 'PoET'

    def version(self):
        return '0.1'

    def stop(self):
        self._exit = True

    def _initialize_block(self):
        chain_head = self._get_chain_head()

        header = NewBlockHeader(chain_head)

        initialize = self._oracle.initialize_block(header)

        LOGGER.info('PoET initialization: %s', initialize)

        if initialize:
            self._service.initialize_block()

        return initialize

    def _check_consensus(self, block):
        verify = self._oracle.verify_block(block)

        LOGGER.debug('PoET verification: %s', verify)

        return verify

    def _switch_forks(self, current_head, new_head):
        try:
            switch = self._oracle.switch_forks(current_head, new_head)
        # The PoET fork resolver raises TypeErrors in certain cases,
        # e.g. when it encounters non-PoET blocks.
        except TypeError as err:
            switch = False
            LOGGER.warning('PoET fork error: %s', err)

        LOGGER.debug('PoET switch forks: %s', switch)

        return switch

    def _check_block(self, block_id):
        self._service.check_blocks([block_id])

    def _fail_block(self, block_id):
        self._service.fail_block(block_id)

    def _get_chain_head(self):
        return PoetBlock(self._service.get_chain_head())

    def _get_block(self, block_id):
        return PoetBlock(self._service.get_blocks([block_id])[block_id])

    def _commit_block(self, block_id):
        self._service.commit_block(block_id)

    def _ignore_block(self, block_id):
        self._service.ignore_block(block_id)

    def _cancel_block(self):
        try:
            self._service.cancel_block()
        except exceptions.InvalidState:
            pass

    def _summarize_block(self):
        try:
            return self._service.summarize_block()
        except (exceptions.InvalidState, exceptions.BlockNotReady) as err:
            LOGGER.warning(err)
            return None

    def _finalize_block(self):
        time.sleep(1)

        summary = self._summarize_block()

        if summary is None:
            LOGGER.warning('No summary available')
            return None
        else:
            LOGGER.info('summary: %s', summary)

        consensus = self._oracle.finalize_block(summary)

        if consensus is None:
            return None

        while True:
            try:
                block_id = self._service.finalize_block(consensus)
                LOGGER.info('finalized %s with %s', block_id, consensus)
                return block_id
            except exceptions.BlockNotReady:
                LOGGER.warning('block not ready')
                time.sleep(1)
                continue
            except exceptions.InvalidState:
                LOGGER.warning('block cannot be finalized')
                return None

    def _check_publish_block(self):
        # Publishing is based solely on wait time, so just give it None.
        publish = self._oracle.check_publish_block(None)

        LOGGER.debug('PoET publishing: %s', publish)

        return publish

    def start(self, updates, service, chain_head, peers):
        self._service = service
        self._oracle = PoetOracle(
            service=service,
            path_config=self._path_config,
            component_endpoint=self._component_endpoint)

        # 1. Wait for an incoming message.
        # 2. Check for exit.
        # 3. Handle the message.
        # 4. Check for publishing.

        handlers = {
            Message.CONSENSUS_NOTIFY_BLOCK_NEW: self._handle_new_block,
            Message.CONSENSUS_NOTIFY_BLOCK_VALID: self._handle_valid_block,
            Message.CONSENSUS_NOTIFY_BLOCK_COMMIT:
                self._handle_committed_block,
        }

        while True:
            try:
                type_tag, data = updates.get(timeout=1)
            except queue.Empty:
                pass
            else:
                LOGGER.debug('Received message: %s', type_tag)

                try:
                    handle_message = handlers[type_tag]
                except KeyError:
                    LOGGER.error('Unknown type tag: %s', type_tag)
                else:
                    handle_message(data)

            if self._exit:
                break

            ##########

            # publisher activity #

            if self._published:
                LOGGER.debug('already published at this height')
                continue

            if not self._building:
                LOGGER.debug('not building: attempting to initialize')
                if self._initialize_block():
                    self._building = True

            if self._building:
                LOGGER.debug('building: attempting to publish')
                if self._check_publish_block():
                    LOGGER.debug('finalizing block')
                    self._finalize_block()
                    self._published = True
                    self._building = False

    def _handle_new_block(self, block):
        block = PoetBlock(block)

        LOGGER.info('Checking consensus data: %s', block)

        if self._check_consensus(block):
            LOGGER.info('Passed consensus check: %s', block)
            self._check_block(block.block_id)
        else:
            LOGGER.info('Failed consensus check: %s', block)
            self._fail_block(block.block_id)

    def _handle_valid_block(self, block_id):
        block = self._get_block(block_id)

        chain_head = self._get_chain_head()

        if self._committing:
            LOGGER.info(
                'Waiting for block to be committed before resolving fork')
            self._pending_blocks.put(block)
            return

        try:
            queued_block = self._pending_blocks.get(timeout=1)
        except queue.Empty:
            LOGGER.debug('No pending blocks')
            pass
        else:
            LOGGER.debug('Handling pending block')
            self._pending_blocks.put(block)
            block = queued_block

        LOGGER.info(
            'Choosing between chain heads -- current: %s -- new: %s',
            chain_head,
            block)

        if self._switch_forks(chain_head, block):
            LOGGER.info('Committing %s', block)
            self._commit_block(block.block_id)
            self._committing = True
        else:
            LOGGER.info('Ignoring %s', block)
            self._ignore_block(block.block_id)

    def _handle_committed_block(self, _block_id):
        chain_head = self._get_chain_head()

        LOGGER.info(
            'Chain head updated to %s, abandoning block in progress',
            chain_head.block_id)

        self._cancel_block()

        self._building = False
        self._published = False
        self._committing = False
