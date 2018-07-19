# Copyright 2018 Intel Corporation
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

import logging
import unittest

from sawtooth_validator.journal.block_manager import BlockManager
from sawtooth_validator.journal.block_manager import MissingPredecessor
from sawtooth_validator.journal.block_manager import \
    MissingPredecessorInBranch
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.protobuf import block_pb2


LOGGER = logging.getLogger(__name__)


def _build_block(block_num, block_id, previous_block_id):
    header = block_pb2.BlockHeader(
        block_num=block_num,
        previous_block_id=previous_block_id)

    return block_pb2.Block(
        header_signature=block_id,
        header=header.SerializeToString())


class TestBlockManager(unittest.TestCase):

    def setUp(self):
        self.block_manager = BlockManager()

    def test_block_manager(self):
        block_a = _build_block(1, "A", NULL_BLOCK_IDENTIFIER)
        block_b = _build_block(2, "B", "A")
        block_c = _build_block(3, "C", "B")

        self.block_manager.put([block_a, block_b, block_c])

        block_e = _build_block(5, "E", "D")

        with self.assertRaises(MissingPredecessor):
            self.block_manager.put([block_e])

        block_d = _build_block(4, "D", "C")

        self.block_manager.put([block_d, block_e])

        block_c2 = _build_block(3, "C2", "B")

        block_d2 = _build_block(4, "D2", "C2")

        block_e2 = _build_block(5, "E2", "D2")

        with self.assertRaises(MissingPredecessorInBranch):
            self.block_manager.put([block_c2, block_e2, block_d2])

        block_id = "D"
        for block in self.block_manager.branch("D"):
            self.assertEqual(block.header_signature, block_id)
            header = block_pb2.BlockHeader()
            header.ParseFromString(block.header)
            block_id = header.previous_block_id

        self.block_manager.put([block_c2, block_d2, block_e2])

        block_id = "D"
        for block in self.block_manager.branch_diff("D", "E2"):
            self.assertEqual(block.header_signature, block_id)
            header = block_pb2.BlockHeader()
            header.ParseFromString(block.header)
            block_id = header.previous_block_id

        for block in self.block_manager.get("C"):
            self.assertEqual(block.header_signature, "C")
