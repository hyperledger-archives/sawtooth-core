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
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.state.merkle import MerkleDatabase


class MockBlockStore(BlockStore):
    """
    Creates a block store with a preseeded chain of blocks.
    With defaults, creates three blocks with ids ranging from '0' to '2'.
    Using optional root parameter for add_block, it is possible to save
    meaningful state_root_hashes to a block.
    """
    def __init__(self, size=3):
        super().__init__(DictDatabase())

        for i in range(size):
            self.add_block(str(i))

    def add_block(self, block_id, root='merkle_root'):
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
            signer_pubkey='pubkey',
            batch_ids=[],
            consensus=b'consensus',
            state_root_hash=root)

        block = Block(
            header=header.SerializeToString(),
            header_signature=block_id,
            batches=[])

        self.update_chain([BlockWrapper(block)], [])


def make_db_and_store(size=3, start='a'):
    """
    Creates and returns three related objects for testing:
        * database - dict database with evolving state
        * store - blocks with with root hashes corresponding to that state
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
    start_ord = ord(start)
    data = {}

    for i in range(size):
        for k, v in data.items():
            data[k] = str(int(v) + 1).encode()
        data[chr(start_ord + i)] = str(i * size + 1).encode()

        root = merkle.update(data, virtual=False)
        roots.append(root)
        store.add_block(str(i), root)

    return database, store, roots

