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

from enum import Enum
from sawtooth_validator.protobuf.block_pb2 import Block


NullIdentifier = "0000000000000000"


class BlockStatus(Enum):
    Unknown = 0,
    Invalid = 1,
    Valid = 2,


class BlockState(object):
    def __init__(self, block_wrapper, weight=0, status=BlockStatus.Unknown):
        self.block = block_wrapper
        self.weight = weight
        self.status = status


class BlockWrapper(object):
    def __init__(self, block_header, block=None):
        self._header_signature = None
        self.batches = []
        self.block_header = block_header
        self.block = None
        if block is not None:
            self.block = block
            self._header_signature = block.header_signature
            self._batches = block.batches

    def __str__(self):
        return str(self.block_header) + str(self.block)

    def add_batches(self, batches):
        # need to update block_header and block.batches
        batch_id_list = [batch.header_signature for batch in batches]
        self.block_header.batch_ids.extend(batch_id_list)
        self.batches = self.batches + batches

    def set_state_hash(self, state_hash):
        self.block_header.state_root_hash = state_hash

    def get_block(self):
        if self.block is None:
            header_bytes = self.block_header.SerializeToString()
            block = Block(header=header_bytes,
                          header_signature=self._header_signature)
            block.batches.extend(self.batches)
        else:
            block = self.block

        return block

    def set_signature(self, sig):
        if self._header_signature is None:
            self._header_signature = sig

    @property
    def header_signature(self):
        return self._header_signature

    @property
    def block_num(self):
        if bool(self.block_header.block_num) or \
                self.block_header.block_num == 0:
            return self.block_header.block_num
        else:
            return None

    @property
    def state_root_hash(self):
        if bool(self.block_header.state_root_hash):
            return self.block_header.state_root_hash
        else:
            return None

    @property
    def previous_block_id(self):
        if bool(self.block_header.previous_block_id):
            return self.block_header.previous_block_id
        else:
            return None

    @property
    def consensus(self):
        if bool(self.block_header.consensus):
            return self.block_header.consensus
        else:
            return None
