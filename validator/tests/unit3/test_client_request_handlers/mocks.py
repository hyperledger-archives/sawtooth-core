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
from sawtooth_validator.journal.block_store_adapter import BlockStoreAdapter


class MockBlockStore(BlockStoreAdapter):
    """
    Creates a block store with a preseeded chain of blocks.
    With defaults, creates blocks with ids ranging from '0' to '2'.
    """
    def __init__(self, size=3):
        super().__init__({})

        for i in range(size):
            self.add_block(str(i))

    def add_block(self, block_id):
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
            state_root_hash='merkle_root')

        block = Block(
            header=header.SerializeToString(),
            header_signature=block_id,
            batches=[])

        self[block_id] = BlockWrapper(block)
        self.set_chain_head(block_id)
