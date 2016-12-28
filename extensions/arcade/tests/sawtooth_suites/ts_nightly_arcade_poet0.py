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
import time
import traceback
import unittest

from sawtooth_test_suite import SawtoothTestSuite
from test_battleship import TestBattleshipCommands
from test_xo_cli import TestXoCli


LOGGER = logging.getLogger(__name__)


class Poet0ArcadeTestSuite(SawtoothTestSuite):
    def test_suite(self):
        cfg = {"LedgerType": "poet0",
               "TransactionFamilies": ["sawtooth_xo",
                                       "sawtooth_battleship"]}

        success = False
        try:
            self._do_setup(cfg)
            self._poll_for_convergence(timeout=128, tolerance=1, standard=2)
            urls = self.urls
            suite = unittest.TestSuite()
            suite.addTest(TestBattleshipCommands('test_all_commands'))
            suite.addTest(TestXoCli('test_xo_create_no_keyfile'))
            suite.addTest(TestXoCli('test_xo_create'))
            suite.addTest(TestXoCli('test_xo_p1_win'))
            runner = unittest.TextTestRunner(verbosity=2)
            result = runner.run(suite)
            if len(result.failures) == 0 and len(result.errors) == 0:
                success = True
        except:
            traceback.print_exc()
            raise
        finally:
            self._do_teardown()
            if success is False:
                self.fail(self.__class__.__name__)
