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

# pylint: disable=attribute-defined-outside-init,abstract-method

import logging
import os

from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.database.native_lmdb import NativeLmdbDatabase
from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.state.batch_tracker import BatchTracker

LOGGER = logging.getLogger(__name__)


def _increment_key(key, offset=1):
    if isinstance(key, int):
        return key + offset
    try:
        return str(int(key) + offset)
    except ValueError:
        return chr(ord(key) + offset)


def _make_mock_transaction(base_id='id', payload='payload'):
    txn_id = 'c' * (128 - len(base_id)) + base_id
    header = TransactionHeader(
        batcher_public_key='public_key-' + base_id,
        family_name='family',
        family_version='0.0',
        nonce=txn_id,
        signer_public_key='public_key-' + base_id)

    return Transaction(
        header=header.SerializeToString(),
        header_signature=txn_id,
        payload=payload.encode())


def make_mock_batch(base_id='id'):
    batch_id = 'a' * (128 - len(base_id)) + base_id
    txn = _make_mock_transaction(base_id)

    header = BatchHeader(
        signer_public_key='public_key-' + base_id,
        transaction_ids=[txn.header_signature])

    return Batch(
        header=header.SerializeToString(),
        header_signature=batch_id,
        transactions=[txn])


class MockBlockStore(BlockStore):
    """
    Creates a block store with a preseeded chain of blocks. With defaults,
    creates three blocks with ids ranging from 'bbb...0' to 'bbb...2',
    with a single batch, and single transaction in each, with ids
    prefixed by 'aaa...'' or 'ccc...'. Using the optional root
    parameter for add_block, it is possible to save meaningful
    state_root_hashes to a block.
    """

    def __init__(self, size=3, start='0'):
        super().__init__(DictDatabase(
            indexes=BlockStore.create_index_configuration()))

        for i in range(size):
            self.add_block(_increment_key(start, i))

    def clear(self):
        self._block_store = DictDatabase(
            indexes=BlockStore.create_index_configuration())

    def add_block(self, base_id, root='merkle_root'):
        block_id = 'b' * (128 - len(base_id)) + base_id
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
            signer_public_key='public_key-' + base_id,
            batch_ids=[block_id],
            consensus=b'consensus',
            state_root_hash=root)

        block = Block(
            header=header.SerializeToString(),
            header_signature=block_id,
            batches=[make_mock_batch(base_id)])

        self.update_chain([BlockWrapper(block)], [])


def make_db_and_store(base_dir, size=3):
    """
    Creates and returns three related objects for testing:
        * database - dict database with evolving state
        * store - blocks with root hashes corresponding to that state
        * roots - list of root hashes used in order
    With defaults, the values at the three roots look like this:
        * 0 - {'000...1': b'1'}
        * 1 - {'000...1': b'2', '000...2': b'4'}
        * 2 - {'000...1': b'3', '000...2': b'5', '000...3': b'7'}
        * 3 - {'000...1': b'4', '000...2': b'6',
               '000...3': b'8', '000...4': b'10'}
    """
    database = NativeLmdbDatabase(
        os.path.join(base_dir, 'client_handlers_mock_db.lmdb'),
        indexes=MerkleDatabase.create_index_configuration(),
        _size=10 * 1024 * 1024)
    store = MockBlockStore(size=0)
    roots = []

    merkle = MerkleDatabase(database)
    data = {}

    # Create all the keys that will be used. Keys are zero-padded hex strings
    # starting with '1'.
    keys = [format(i, 'x').zfill(70) for i in range(1, size + 1)]

    for i in range(1, size + 1):
        # Construct the state for this root
        data = {}
        for key_idx in range(i):
            key = keys[key_idx]
            # Calculate unique values based on the key and root
            val = i + (2 * key_idx)
            data[key] = str(val).encode()

        root = merkle.update(data, virtual=False)
        roots.append(root)
        store.add_block(str(i), root)

    return database, store, roots


def make_store_and_tracker(size=3):
    """
    Creates and returns two related objects for testing:
        * store - a mock block store, with a default start

        * tracker - a batch tracker attached to the store, with one
          pending batch

    With defaults, the three block ids in the store will be:
        * 'bbb...0', 'bbb...1', 'bbb...2'
    The three batch ids in the store will be:
        * 'aaa...0', 'aaa...1', 'aaa...2'
    The pending batch in the tracker will be:
        * 'aaa...3'
    """
    store = MockBlockStore(size=size)
    tracker = BatchTracker(store.has_batch)
    tracker.notify_batch_pending(make_mock_batch('d'))
    tracker.notify_batch_pending(make_mock_batch('f'))
    tracker.notify_txn_invalid('c' * 127 + 'f', 'error message', b'error data')

    return store, tracker


class MockGossip:
    def get_peers(self):
        return {"connection_id": "Peer1"}
