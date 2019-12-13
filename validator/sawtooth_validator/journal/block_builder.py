# Copyright 2016 Intel Corporation
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


class BlockBuilder:
    """
    Utility class to assemble new blocks. Used by the block publisher.
    """

    def __init__(self, block_header):
        self._header_signature = None
        self.batches = []
        self.block_header = block_header

    def add_batches(self, batches):
        batch_id_list = [batch.header_signature for batch in batches]
        self.block_header.batch_ids.extend(batch_id_list)
        self.batches = self.batches + batches

    def add_batch(self, batch):
        self.block_header.batch_ids.append(batch.header_signature)
        self.batches.append(batch)

    def build_block(self):
        """
        Assembles the candidate block into it's finalized form for broadcast.
        """
        header_bytes = self.block_header.SerializeToString()
        block = Block(header=header_bytes,
                      header_signature=self._header_signature)
        block.batches.extend(self.batches)
        return block

    @property
    def identifier(self):
        return self._header_signature

    @property
    def previous_block_id(self):
        """
        Returns the identifier of the previous block.
        """
        return self.block_header.previous_block_id

    def set_state_hash(self, state_hash):
        self.block_header.state_root_hash = state_hash

    def set_signature(self, sig):
        self._header_signature = sig

    def __str__(self):
        return "({}, S:{}, P:{})". \
            format(self.block_header.block_num,
                   self.block_header.state_root_hash[:8],
                   self.block_header.previous_block_id[:8])
