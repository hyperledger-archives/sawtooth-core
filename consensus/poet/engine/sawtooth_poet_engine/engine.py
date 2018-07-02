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

import json

from sawtooth_sdk.consensus.engine import Engine
from sawtooth_sdk.consensus import exceptions
from sawtooth_sdk.protobuf.validator_pb2 import Message

from sawtooth_poet_engine.oracle import PoetOracle, PoetBlock
from sawtooth_poet_engine.pending import PendingForks


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

        self._pending_forks_to_resolve = PendingForks()

    def name(self):
        return 'PoET'

    def version(self):
        return '0.1'

    def stop(self):
        self._exit = True

    def _initialize_block(self):
        chain_head = self._get_chain_head()

        initialize = self._oracle.initialize_block(chain_head)

        if initialize:
            self._service.initialize_block(previous_id=chain_head.block_id)

        return initialize

    def _check_consensus(self, block):
        return self._oracle.verify_block(block)

    def _switch_forks(self, current_head, new_head):
        try:
            switch = self._oracle.switch_forks(current_head, new_head)
        # The PoET fork resolver raises TypeErrors in certain cases,
        # e.g. when it encounters non-PoET blocks.
        except TypeError as err:
            switch = False
            LOGGER.warning('PoET fork resolution error: %s', err)

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
        except exceptions.InvalidState as err:
            LOGGER.warning(err)
            return None
        except exceptions.BlockNotReady:
            return None

    def _finalize_block(self):
        summary = None
        while summary is None:
            summary = self._summarize_block()

            if summary is None:
                LOGGER.debug('Block not ready to be summarized')
                time.sleep(1)
                continue
            else:
                LOGGER.info('Block summary: %s', summary.hex())
                break

        consensus = self._oracle.finalize_block(summary)

        if consensus is None:
            return None

        while True:
            try:
                block_id = self._service.finalize_block(consensus)
                LOGGER.info(
                    'Finalized %s with %s',
                    block_id.hex(),
                    json.loads(consensus.decode()))
                return block_id
            except exceptions.BlockNotReady:
                LOGGER.debug('Block not ready to be finalized')
                time.sleep(1)
                continue
            except exceptions.InvalidState:
                LOGGER.warning('block cannot be finalized')
                return None

    def _check_publish_block(self):
        # Publishing is based solely on wait time, so just give it None.
        return self._oracle.check_publish_block(None)

    def start(self, updates, service, startup_state):
        self._service = service
        self._oracle = PoetOracle(
            service=service,
            component_endpoint=self._component_endpoint,
            config_dir=self._path_config.config_dir,
            data_dir=self._path_config.data_dir,
            key_dir=self._path_config.key_dir)

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
                try:
                    type_tag, data = updates.get(timeout=0.1)
                except queue.Empty:
                    pass
                else:
                    LOGGER.debug('Received message: %s',
                                 Message.MessageType.Name(type_tag))

                    try:
                        handle_message = handlers[type_tag]
                    except KeyError:
                        LOGGER.error('Unknown type tag: %s',
                                     Message.MessageType.Name(type_tag))
                    else:
                        handle_message(data)

                if self._exit:
                    break

                self._try_to_publish()
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unhandled exception in message loop")

    def _try_to_publish(self):
        if self._published:
            return

        if not self._building:
            if self._initialize_block():
                self._building = True

        if self._building:
            if self._check_publish_block():
                block_id = self._finalize_block()
                if block_id:
                    LOGGER.info("Published block %s", block_id.hex())
                    self._published = True
                    self._building = False
                else:
                    self._cancel_block()
                    self._building = False

    def _handle_new_block(self, block):
        block = PoetBlock(block)
        LOGGER.info('Received %s', block)

        if self._check_consensus(block):
            LOGGER.info('Passed consensus check: %s', block.block_id.hex())
            self._check_block(block.block_id)
        else:
            LOGGER.info('Failed consensus check: %s', block.block_id.hex())
            self._fail_block(block.block_id)

    def _handle_valid_block(self, block_id):
        block = self._get_block(block_id)

        self._pending_forks_to_resolve.push(block)

        self._process_pending_forks()

    def _process_pending_forks(self):
        while not self._committing:
            block = self._pending_forks_to_resolve.pop()
            if block is None:
                break

            self._resolve_fork(block)

    def _resolve_fork(self, block):
        chain_head = self._get_chain_head()

        LOGGER.info(
            'Choosing between chain heads -- current: %s -- new: %s',
            chain_head.block_id.hex(),
            block.block_id.hex())

        if self._switch_forks(chain_head, block):
            LOGGER.info('Committing %s', block.block_id.hex())
            self._commit_block(block.block_id)
            self._committing = True
        else:
            LOGGER.info('Ignoring %s', block.block_id.hex())
            self._ignore_block(block.block_id)

    def _handle_committed_block(self, block_id):
        LOGGER.info(
            'Chain head updated to %s, abandoning block in progress',
            block_id.hex())

        self._cancel_block()

        self._building = False
        self._published = False
        self._committing = False

        self._process_pending_forks()
