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

from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.timed_cache import TimedCache
from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.state.batch_tracker import BatchTracker

def _increment_key(key, offset=1):
    if type(key) == int:
        return key + offset
    try:
        return str(int(key) + offset)
    except ValueError:
        return chr(ord(key) + offset)

def _make_mock_transaction(base_id='id', payload='payload'):
    txn_id = 't-' + base_id
    header = TransactionHeader(
        batcher_pubkey='pubkey-' + base_id,
        family_name='family',
        family_version='0.0',
        nonce=txn_id,
        signer_pubkey='pubkey-' + base_id)

    return Transaction(
        header=header.SerializeToString(),
        header_signature=txn_id,
        payload=payload.encode())

def make_mock_batch(base_id='id'):
    batch_id = 'b-' + base_id
    txn = _make_mock_transaction(base_id)

    header = BatchHeader(
        signer_pubkey='pubkey-' + base_id,
        transaction_ids=[txn.header_signature])

    return Batch(
        header=header.SerializeToString(),
        header_signature=batch_id,
        transactions=[txn])


class MockBlockStore(BlockStore):
    """
    Creates a block store with a preseeded chain of blocks.
    With defaults, creates three blocks with ids ranging from 'B-0' to 'B-2',
    and a single batch, and single transaction in each, with ids prefixed by
    'b-' or 't-'. Using the optional root parameter for add_block, it is
    possible to save meaningful state_root_hashes to a block.
    """
    def __init__(self, size=3, start='0'):
        super().__init__(DictDatabase())

        for i in range(size):
            self.add_block(_increment_key(start, i))

    def add_block(self, base_id, root='merkle_root'):
        block_id = 'B-' + base_id
        head = self.chain_head
        if head:
            previous_id = head.header_signature
            num = head.header.block_num + 1
        else:
            previous_id = 'zzzzz'
            num = 0

        header = BlockHeader(
            block_num=num,
            previous_block_id=previous_id,
            signer_pubkey='pubkey-' + base_id,
            batch_ids=[block_id],
            consensus=b'consensus',
            state_root_hash=root)

        block = Block(
            header=header.SerializeToString(),
            header_signature=block_id,
            batches=[make_mock_batch(base_id)])

        self.update_chain([BlockWrapper(block)], [])


def make_db_and_store(size=3, start='a'):
    """
    Creates and returns three related objects for testing:
        * database - dict database with evolving state
        * store - blocks with root hashes corresponding to that state
        * roots - list of root hashes used in order
    With defaults, the values at the three roots look like this:
        * 0 - {'a': b'1'}
        * 1 - {'a': b'2', 'b': b'4'}
        * 2 - {'a': b'3', 'b': b'5', 'c': b'7'}
    """
    database = DictDatabase()
    store = MockBlockStore(size=0);
    roots = []

    merkle = MerkleDatabase(database)
    data = {}

    for i in range(size):
        for k, v in data.items():
            data[k] = str(int(v) + 1).encode()
        data[_increment_key(start, i)] = str(i * size + 1).encode()

        root = merkle.update(data, virtual=False)
        roots.append(root)
        store.add_block(str(i), root)

    return database, store, roots


def make_store_and_tracker(size=3):
    """
    Creates and returns two related objects for testing:
        * store - a mock block store, with a default start
        * tracker - a batch tracker attached to the store, with one pending batch

    With defaults, the three block ids in the store will be:
        * 'B-0', 'B-1', B-2'
    The three batch ids in the store will be:
        * 'b-0', 'b-1', b-2'
    The pending batch in the tracker will be:
        * 'b-3'
    """
    store = MockBlockStore(size=size)
    tracker = BatchTracker(store)
    store.add_update_observer(tracker)
    tracker.notify_batch_pending('b-pending')

    return store, tracker
