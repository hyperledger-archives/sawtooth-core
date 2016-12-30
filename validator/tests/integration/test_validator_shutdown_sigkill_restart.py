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
from txnintegration.utils import Progress
from sawtooth.exceptions import MessageException

RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False


@unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
class TestValidatorShutdownSigKillRestart(unittest.TestCase):
    def __init__(self, test_name, urls=None, node_controller=None, nodes=None):
        super(TestValidatorShutdownSigKillRestart, self).__init__(test_name)
        self.urls = urls
        self.node_controller = node_controller
        self.nodes = nodes

    def test_validator_shutdown_sigkill_restart_ext(self):
        try:
            keys = 10
            rounds = 2
            txn_intv = 0
            timeout = 5

            print("Testing transaction load.")
            test = IntKeyLoadTest()
            urls = self.urls
            self.assertEqual(5, len(urls))
            test.setup(self.urls, keys)
            test.run(keys, rounds, txn_intv)
            test.validate()

            to = TimeOut(timeout)
            convergent = False
            with Progress("Checking for validators convergence") as p:
                while convergent is False or not to.is_timed_out():
                    time.sleep(timeout)
                    p.step()
                    convergent = is_convergent(self.urls,
                                               tolerance=2,
                                               standard=5)
            self.assertTrue(convergent, "All validators are "
                                        "not on the same chain.")
            print("all validators are on the same chain")
            report_before_shutdown = sit_rep(self.urls, verbosity=1)
            validator_report = report_before_shutdown[4]
            valid_dict_value = validator_report['Status']
            validator_blocks_shutdown = valid_dict_value['Blocks']
            print("validator_blocks", validator_blocks_shutdown)

            print("shutdown validator 4 w/ SIGKILL")
            node_names = self.node_controller.get_node_names()
            node_names.sort()
            self.node_controller.kill(node_names[4])
            to = TimeOut(120)
            while len(self.node_controller.get_node_names()) > 4:
                if to.is_timed_out():
                    self.fail("Timed Out")
            print('check state of validators:')
            sit_rep(self.urls[:-1], verbosity=2)

            print("sending more txns after SIGKILL")
            urls = self.urls[:-1]
            self.assertEqual(4, len(urls))
            test.setup(urls, keys)
            test.run(keys, rounds, txn_intv)
            test.validate()

            print("turn off entire validator network")
            for node in node_names:
                self.node_controller.stop(node)
            to = TimeOut(120)
            while len(self.node_controller.get_node_names()) > 0:
                if to.is_timed_out():
                    self.fail("Timed Out")

            print("relaunch validator 4")
            self.node_controller.start(self.nodes[4])
            report_after_relaunch = None
            to = TimeOut(120)
            while report_after_relaunch is None:
                try:
                    report_after_relaunch = \
                        sit_rep([self.urls[4]], verbosity=1)
                except MessageException:
                    if to.is_timed_out():
                        self.fail("Timed Out")
                time.sleep(4)
            validator_report = report_after_relaunch[0]
            valid_dict_value = validator_report['Status']
            validator_blocks_relaunch = valid_dict_value['Blocks']
            print("validator_blocks_relaunch", validator_blocks_relaunch)

            if len(validator_blocks_relaunch) == \
                    len(validator_blocks_shutdown):
                if validator_blocks_shutdown == validator_blocks_relaunch:
                    print("relaunched validator restored from local db")
            else:
                for i in range(0, len(validator_blocks_shutdown)):
                    self.assertEqual(validator_blocks_relaunch[i],
                                     validator_blocks_shutdown[i],
                                     "relaunched validator didn't"
                                     " restore fr local db")
                    break
                print("relaunched validator restored from local database")

        finally:
            print("restart validators ")
            for node in self.nodes:
                self.node_controller.start(node)
            to = TimeOut(120)
            while len(self.node_controller.get_node_names()) < 5:
                if to.is_timed_out():
                    self.fail("Timed Out")
            report_after_relaunch = None
            while report_after_relaunch is None:
                try:
                    report_after_relaunch = \
                        sit_rep(self.urls, verbosity=1)
                except MessageException:
                    if to.is_timed_out():
                        self.fail("Timed Out")
                time.sleep(4)
            print("No validators")
