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

# pylint: disable=arguments-differ

import logging

from concurrent.futures import Executor

from sawtooth_validator.consensus.notifier import ConsensusNotifier

from sawtooth_validator.protobuf import batch_pb2
from sawtooth_validator.protobuf import block_pb2


LOGGER = logging.getLogger(__name__)


class SynchronousExecutor(Executor):
    def __init__(self):
        self._work_queue = []

    def submit(self, job, *args, **kwargs):
        self._work_queue.append((job, args, kwargs))

    def process_next(self):
        job = self._work_queue.pop()
        job[0](*job[1], **job[2])

    def process_all(self):
        while self._work_queue:
            self.process_next()


class MockNetwork:
    def __init__(self):
        self.messages = []

        def nop_callback(msg):
            pass

        self.on_batch_received = nop_callback
        self.on_block_received = nop_callback
        self.on_block_requested = nop_callback

    def send_message(self, message):
        self.messages.append(message)

    @property
    def has_messages(self):
        return len(self.messages) != 0

    def dispatch_messages(self):
        while self.has_messages:
            self.dispatch_message()

    def dispatch_message(self):
        msg = self.messages.pop()
        if isinstance(msg, str):
            if self.on_block_request is not None:
                self.on_block_request(msg)
        elif isinstance(msg, block_pb2.Block):
            if self.on_block_received is not None:
                self.on_block_received(msg)
        elif isinstance(msg, batch_pb2.Batch):
            if self.on_batch_received is not None:
                self.on_batch_received(msg)

    def clear(self):
        self.messages = []


class MockChainIdManager:
    """Mock for the ChainIdManager, which provides the value of the
    block-chain-id stored in the data_dir.
    """

    def __init__(self):
        self._block_chain_id = None

    def save_block_chain_id(self, block_chain_id):
        self._block_chain_id = block_chain_id

    def get_block_chain_id(self):
        return self._block_chain_id


class MockConsensusNotifier(ConsensusNotifier):
    def __init__(self):
        super().__init__(consensus_service=None,
                         consensus_registry=None,
                         public_key=None)
        self._new_block = None
        self._committed_block = None

    def notify_block_new(self, block):
        self._new_block = block

    def notify_block_commit(self, block_id):
        self._committed_block = block_id

    @property
    def new_block(self):
        return self._new_block

    @property
    def committed_block(self):
        return self._committed_block
