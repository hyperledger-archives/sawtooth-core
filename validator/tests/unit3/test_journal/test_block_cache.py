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

import logging
import sys
import time
import unittest

from sawtooth_validator.journal.block_cache import BlockCache

LOGGER = logging.getLogger(__name__)


class TestBlockCache(unittest.TestCase):
    def test_load_from_block_store(self):
        """ Test that misses will load from the block store.
        """
        bs = {}
        bs["test"] = "value"
        bc = BlockCache(bs)

        self.assertTrue("test" in bc)
        self.assertTrue(bc["test"] == "value")


