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

from sawtooth_validator.execution.scheduler import Scheduler
from sawtooth_validator.execution.scheduler import BatchExecutionResult
from sawtooth_validator.execution.scheduler import TxnExecutionResult

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


class MockScheduler(Scheduler):
    def __init__(self, batch_execution_result=True):
        self.batches = {}
        self.batch_execution_result = batch_execution_result

    def add_batch(self, batch, state_hash=None, required=False):
        self.batches[batch.header_signature] = batch

    def get_batch_execution_result(self, batch_signature):
        result = True
        if self.batch_execution_result is None:
            batch = self.batches[batch_signature]
            for txn in batch.transactions:
                if txn.payload == b'BAD':
                    result = False
        else:
            result = self.batch_execution_result

        return BatchExecutionResult(
            is_valid=result,
            state_hash='0' * 70)

    def get_transaction_execution_results(self, batch_signature):
        txn_execution_results = []
        is_valid_always_false = False
        if not self.batch_execution_result:
            is_valid_always_false = True

        batch = self.batches[batch_signature]
        for txn in batch.transactions:
            if is_valid_always_false:
                is_valid = False
                context_id = None
            else:
                if txn.payload == b'BAD':
                    is_valid = False
                    context_id = None
                else:
                    is_valid = True
                    context_id = "test"
            txn_execution_results.append(
                TxnExecutionResult(
                    signature=txn.header_signature,
                    is_valid=is_valid,
                    context_id=context_id,
                    state_hash=None))
        return txn_execution_results

    def set_transaction_execution_result(
            self, txn_signature, is_valid, context_id):
        raise NotImplementedError()

    def next_transaction(self):
        raise NotImplementedError()

    def unschedule_incomplete_batches(self):
        pass

    def is_transaction_in_schedule(self, txn_id):
        raise NotImplementedError()

    def finalize(self):
        pass

    def complete(self, block):
        return True

    def __iter__(self):
        raise NotImplementedError()

    def get_transaction(self, index):
        raise NotImplementedError()

    def count(self):
        raise NotImplementedError()

    def cancel(self):
        pass

    def is_cancelled(self):
        return False


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
