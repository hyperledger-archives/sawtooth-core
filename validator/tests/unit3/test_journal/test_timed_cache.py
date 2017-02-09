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

from sawtooth_validator.journal.timed_cache import TimedCache

LOGGER = logging.getLogger(__name__)


class TestTimedCache(unittest.TestCase):
    def test_cache(self):
        bc = TimedCache(keep_time=1)

        with self.assertRaises(KeyError):
            bc["test"]

        bc["test"] = "value"

        self.assertEqual(len(bc), 1)

        del bc["test"]
        self.assertFalse("test" in bc)


    def test_evict_expired(self):
        """ Test that values will be evicted from the
        cache as they time out.
        """

        # use an invasive technique so that we don't have to sleep for
        # the item to expire

        bc = TimedCache(keep_time=1)

        bc["test"] = "value"
        bc["test2"] = "value2"
        self.assertEqual(len(bc), 2)

        # test that expired item i
        bc.cache["test"].timestamp = bc.cache["test"].timestamp - 2
        bc.purge_expired()
        self.assertEqual(len(bc), 1)
        self.assertFalse("test" in bc)
        self.assertTrue("test2" in bc)

    def test_access_update(self):

        bc = TimedCache(keep_time=1)

        bc["test"] = "value"
        bc["test2"] = "value2"
        self.assertEqual(len(bc), 2)

        bc["test"] = "value"
        bc.cache["test"].timestamp = bc.cache["test"].timestamp - 2
        bc["test"]  # access to update timestamp
        bc.purge_expired()
        self.assertEqual(len(bc), 2)
        self.assertTrue("test" in bc)
        self.assertTrue("test2" in bc)



