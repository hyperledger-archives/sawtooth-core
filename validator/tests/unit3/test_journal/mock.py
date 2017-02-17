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
from concurrent.futures import Executor
from sawtooth_validator.protobuf import batch_pb2
from sawtooth_validator.protobuf import block_pb2
from sawtooth_validator.execution.scheduler import Scheduler
from sawtooth_validator.execution.scheduler import BatchExecutionResult
from sawtooth_validator.journal.block_sender import BlockSender


class SynchronousExecutor(Executor):
    def __init__(self):
        self._work_queue = []

    def submit(self, job):
        self._work_queue.append(job)

    def process_next(self):
        job = self._work_queue.pop()
        job()

    def process_all(self):
        while len(self._work_queue):
            self.process_next()


class MockNetwork(object):
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
    def __init__(self):
        self.batches = {}

    def add_batch(self, batch, state_hash=None):
        self.batches[batch.header_signature] = batch

    def get_batch_execution_result(self, batch_signature):


        return BatchExecutionResult(is_valid=True, state_hash="0000000000")

    def set_transaction_execution_result(
            self, txn_signature, is_valid, context_id):
        raise NotImplementedError()

    def next_transaction(self):
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


class MockTransactionExecutor(object):
    def __init__(self):
        self.messages = []

    def create_scheduler(self, squash_handler, first_state_root):
        return MockScheduler()

    def execute(self, scheduler, state_hash=None):
        pass


class MockBlockSender(BlockSender):
    def __init__(self):
        self.new_block = None

    def send(self, block):
         self.new_block = block


class MockStateViewFactory(object):
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


    def create_view(self, state_root_hash):
        """Creates a StateView for the given state root hash.

        Returns:
            StateView: state view locked to the given root hash.
        """
        return MockStateView(self._database)


class MockStateView(object):
    """The StateView provides read-only access to a particular merkle tree root.

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
