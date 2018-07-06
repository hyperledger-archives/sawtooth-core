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


LOGGER = logging.getLogger(__name__)


class PoetEngine(Engine):
    def __init__(self):
        self._exit = False
        self._service = None
        self._chain_head = None

    def name(self):
        return 'PoET'

    def version(self):
        return '0.1'

    def stop(self):
        self._exit = True

    def _initialize_block(self):
        self._service.initialize_block(None)

    def _check_consensus(self, block):
        return True

    def _compare_forks(self, current_head, new_head):
        return True

    def _check_block(self, block_id):
        self._service.check_blocks([block_id])

    def _fail_block(self, block_id):
        self._service.fail_block(block_id)

    def _get_chain_head(self):
        return self._service.get_chain_head()

    def _get_block(self, block_id):
        return self._service.get_blocks([block_id])

    def _commit_block(self, block_id):
        self._service.commit_block(block_id)

    def _ignore_block(self, block_id):
        self._service.ignore_block(block_id)

    def _cancel_block(self):
        try:
            self._service.cancel_block()
        except exceptions.InvalidState:
            pass

    def _finalize_block(self):
        time.sleep(1)

        while True:
            try:
                block_id = self._service.finalize_block(b'consensus')
                break
            except exceptions.BlockNotReady:
                time.sleep(1)
                continue
            except exceptions.InvalidState:
                return None

        return block_id

    def _check_publish_block(self):
        return True

    def start(self, updates, service, startup_state):
        self._service = service
        self._chain_head = chain_head

        self._initialize_block()

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

                try:
                    handle_message = handlers[type_tag]
                except KeyError:
                    pass
                else:
                    handle_message(data)

            except queue.Empty:
                LOGGER.warning('empty queue')

            if self._exit:
                break

            if self._check_publish_block():
                self._finalize_block()

    def _handle_new_block(self, block):
        LOGGER.info('Checking consensus data: %s', block)

        if self._check_consensus(block):
            LOGGER.info('Passed consensus check: %s', block)
            self._check_block(block.block_id)
        else:
            LOGGER.info('Failed consensus check: %s', block)
            self._fail_block(block.block_id)

    def _handle_valid_block(self, block_id):
        block = self._get_block(block_id)

        self._chain_head = self._get_chain_head()

        LOGGER.info(
            'Choosing between chain heads -- current: %s -- new: %s',
            self._chain_head,
            block_id)

        if self._compare_forks(self._chain_head, block):
            LOGGER.info('Committing %s', block)
            self._commit_block(block_id)
        else:
            LOGGER.info('Ignoring %s', block)
            self._ignore_block(block_id)

    def _handle_committed_block(self, _block_id):
        self._chain_head = self._get_chain_head()

        LOGGER.info(
            'Chain head updated to %s, abandoning block in progress',
            self._chain_head)

        self._cancel_block()

        self._initialize_block()
