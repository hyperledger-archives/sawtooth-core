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

from __future__ import print_function

import unittest
import os
import time

from txnintegration.integer_key_load_cli import IntKeyLoadTest
from txnintegration.utils import sit_rep
from txnintegration.utils import is_convergent
from txnintegration.utils import TimeOut
from sawtooth.exceptions import MessageException

RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False


@unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
class TestValidatorShutdownRestart(unittest.TestCase):
    def __init__(self, test_name, urls=None, node_controller=None, nodes=None):
        super(TestValidatorShutdownRestart, self).__init__(test_name)
        self.urls = urls
        self.node_controller = node_controller
        self.nodes = nodes

    def test_validator_shutdown_restart_ext(self):
        try:
            keys = 10
            rounds = 2
            txn_intv = 0

            print("Testing transaction load.")
            test = IntKeyLoadTest()
            urls = self.urls
            self.assertEqual(5, len(urls))
            test.setup(self.urls, keys)
            test.run(keys, rounds, txn_intv)
            test.validate()

            print("test validator shutdown w/ SIGTERM")
            node_names = self.node_controller.get_node_names()
            node_names.sort()
            self.node_controller.stop(node_names[4])
            to = TimeOut(120)
            while len(self.node_controller.get_node_names()) > 4:
                if to.is_timed_out():
                    self.fail("Timed Out")
            print('check state of validators:')
            sit_rep(self.urls[:-1], verbosity=2)

            print("sending more txns after SIGTERM")
            urls = self.urls[:-1]
            self.assertEqual(4, len(urls))
            test.setup(urls, keys)
            test.run(keys, rounds, txn_intv)
            test.validate()

            print(("relaunching removed_validator", 4))
            self.node_controller.start(self.nodes[4])
            to = TimeOut(120)
            while len(self.node_controller.get_node_names()) < 1:
                if to.is_timed_out():
                    self.fail("Timed Out")
            report_after_relaunch = None
            while report_after_relaunch is None:
                try:
                    report_after_relaunch = \
                        sit_rep([self.urls[4]], verbosity=1)
                except MessageException:
                    if to.is_timed_out():
                        self.fail("Timed Out")
                time.sleep(4)
            print('check state of validators:')
            sit_rep(self.urls, verbosity=2)
            if is_convergent(self.urls, tolerance=2, standard=5) is True:
                print("all validators are on the same chain")
            else:
                print("all validators are not on the same chain")

            print("sending more txns after relaunching validator 4")
            urls = self.urls
            self.assertEqual(5, len(urls))
            test.setup(urls, keys)
            test.run(keys, rounds, txn_intv)
            test.validate()
        finally:
            print("No validators")
