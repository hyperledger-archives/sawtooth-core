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

import logging
import unittest
import time

from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.journal.block_wrapper import BlockWrapper

from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader


LOGGER = logging.getLogger(__name__)


class BlockCacheTest(unittest.TestCase):
    def test_block_cache(self):
        block_store = {}
        cache = BlockCache(block_store=block_store, keep_time=1,
                           purge_frequency=1)

        header1 = BlockHeader(previous_block_id="000")
        block1 = BlockWrapper(Block(header=header1.SerializeToString(),
                                    header_signature="ABC"))

        header2 = BlockHeader(previous_block_id="ABC")
        block2 = BlockWrapper(Block(header=header2.SerializeToString(),
                                    header_signature="DEF"))

        header3 = BlockHeader(previous_block_id="BCA")
        block3 = BlockWrapper(Block(header=header3.SerializeToString(),
                                    header_signature="FED"))

        cache[block1.header_signature] = block1
        cache[block2.header_signature] = block2

        # Check that blocks are in the BlockCache
        self.assertIn("ABC", cache)
        self.assertIn("DEF", cache)

        # Wait for purge time to expire
        time.sleep(1)
        # Add "FED"
        cache[block3.header_signature] = block3

        # Check that "ABC" is still in the cache even though the keep time has
        # expired because it has a referecne count of 1 but "DEF" has been
        # removed
        self.assertIn("ABC", cache)
        self.assertNotIn("DEF", cache)
        self.assertIn("FED", cache)
