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
import os
import time
import unittest

from txnintegration.utils import is_convergent
from txnintegration.utils import Progress
from txnintegration.utils import sit_rep
from txnintegration.utils import TimeOut
from sawtooth.exceptions import MessageException

logger = logging.getLogger(__name__)

RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False


class TestConvergence(unittest.TestCase):
    def __init__(self, test_name, urls=None):
        super(TestConvergence, self).__init__(test_name)
        self.urls = urls

    def _poll_for_convergence(self, timeout=256, tolerance=2, standard=5):
        convergent = False
        with Progress('awaiting convergence') as p:
            to = TimeOut(timeout)
            while convergent is False:
                self.assertFalse(to.is_timed_out(),
                                 'timed out awaiting convergence')
                p.step()
                time.sleep(4)
                try:
                    convergent = is_convergent(self.urls, standard=standard,
                                               tolerance=tolerance)
                except MessageException:
                    pass
        sit_rep(self.urls, verbosity=1)
        return convergent

    @unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
    def test_bootstrap(self):
        '''
        Ensures that the network (self.urls) is convergent on at least 2
        blocks, with a fork tolerance of one.  This is usually sufficient to
        proceed unhindered.  This test is not a substitute for our
        test_genesis_util tests, because it cannot determine whether the first
        block on the network is the 'intended' block.  To do so, it would need
        to have additional, internal knowledge about the validator subsystem.
        '''
        convergent = self._poll_for_convergence(timeout=240, tolerance=1,
                                                standard=2)
        self.assertTrue(convergent, 'network divergent')

    @unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
    def test_convergence(self):
        '''
        Ensures that the network (self.urls) is convergent on at least 10
        blocks, with a fork tolerance of two.
        '''
        convergent = self._poll_for_convergence()
        self.assertTrue(convergent, 'network divergent')
