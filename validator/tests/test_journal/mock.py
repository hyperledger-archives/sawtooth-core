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

from sawtooth_validator.journal.batch_sender import BatchSender
from sawtooth_validator.journal.block_sender import BlockSender
from sawtooth_validator.journal.batch_injector import BatchInjectorFactory
from sawtooth_validator.journal.batch_injector import BatchInjector

from sawtooth_validator.protobuf import batch_pb2
from sawtooth_validator.protobuf import block_pb2
from sawtooth_validator.protobuf.setting_pb2 import Setting

from sawtooth_validator.state.settings_view import SettingsView


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


class MockTransactionExecutor:
    def __init__(self, batch_execution_result=True):
        self.messages = []
        self.batch_execution_result = batch_execution_result

    def create_scheduler(self, first_state_root):
        return MockScheduler(self.batch_execution_result)

    def execute(self, scheduler, state_hash=None):
        pass


class MockBlockSender(BlockSender):
    def __init__(self):
        self.new_block = None

    def send(self, block, keep_batches=None):
        self.new_block = block


class MockBatchSender(BatchSender):
    def __init__(self):
        self.new_batch = None

    def send(self, batch):
        self.new_batch = batch


class MockStateViewFactory:
    """The StateViewFactory produces StateViews for a particular merkle root.

    This factory produces read-only views of a merkle tree. For a given
    database, these views are considered immutable.
    """

    def __init__(self, database=None):
        """Initializes the factory with a given database.

        Args:
            database (:obj:`Database`): the database containing the merkle
                tree.
        """
        self._database = database
        if self._database is None:
            self._database = {}

    def create_view(self, state_root_hash=None):
        """Creates a StateView for the given state root hash.

        Returns:
            StateView: state view locked to the given root hash.
        """
        return MockStateView(self._database)


class MockStateView:
    """The StateView provides read-only access to a particular merkle tree
    root.

    The StateView is a read-only view of a merkle tree. Access is limited to
    available addresses, collections of leaf nodes, and specific leaf nodes.
    The view is lock to a single merkle root, effectively making it an
    immutable snapshot.
    """

    def __init__(self, tree):
        """Creates a StateView with a given merkle tree.

        Args:
            tree (:obj:`MerkleDatabase`): the merkle tree for this view
        """
        self._database = tree

    def get(self, address):
        """
        Returns:
            bytes the state entry at the given address
        """
        return self._database[address]

    def addresses(self):
        """
        Returns:
            list of str: the list of addresses available in this view
        """
        return []

    def leaves(self, prefix):
        """
        Args:
            prefix (str): an address prefix under which to look for leaves

        Returns:
            dict of str,bytes: the state entries at the leaves
        """
        return []


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


# pylint: disable=invalid-name
def CreateSetting(key, value):
    """
    Create a setting object to include in a MockStateFactory.
    """
    addr = SettingsView.setting_address(key)

    setting = Setting()
    setting.entries.add(key=key, value=str(value))
    return addr, setting.SerializeToString()


class MockPermissionVerifier:
    def is_batch_signer_authorized(self, batch, state_root=None):
        return True


class MockBatchInjectorFactory(BatchInjectorFactory):
    def __init__(self, batch):
        self._batch = batch

    def create_injectors(self, previous_block_id):
        return [MockBatchInjector(self._batch)]


class MockBatchInjector(BatchInjector):
    def __init__(self, batch):
        self._batch = batch

    def block_start(self, previous_block_id):
        return [self._batch]


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
