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
import traceback
import unittest

from sawtooth_test_suite import SawtoothTestSuite

from integration.test_integration import TestIntegration
from integration.test_convergence import TestConvergence
from integration.test_validator_restart_restore \
    import TestValidatorShutdownRestartRestore
from integration.test_validator_restart import TestValidatorShutdownRestart
from integration.test_validator_shutdown_sigkill_restart \
    import TestValidatorShutdownSigKillRestart
from integration.test_sawtooth_stats import TestSawtoothStats

LOGGER = logging.getLogger(__name__)


class Poet0NightlyTestSuite(SawtoothTestSuite):
    def test_suite(self):
        cfg = {"LedgerType": "poet0"}

        success = False
        try:
            self._do_setup(cfg)
            urls = self.urls
            suite = unittest.TestSuite()
            # test_bootstrap will allow the validators to all come on line
            # before others tries to connect to the validators.
            suite.addTest(TestConvergence('test_bootstrap', urls))
            suite.addTest(TestIntegration('test_intkey_load_ext', urls))
            suite.addTest(TestIntegration('test_missing_dependencies', urls))
            suite.addTest(TestSawtoothStats('test_sawtooth_stats', urls))
            suite.addTest(TestValidatorShutdownRestart(
                'test_validator_shutdown_restart_ext',
                urls, self._node_ctrl, self._nodes))
            suite.addTest(TestConvergence('test_bootstrap', urls))
            suite.addTest(TestValidatorShutdownSigKillRestart(
                'test_validator_shutdown_sigkill_restart_ext',
                urls, self._node_ctrl, self._nodes))
            suite.addTest(TestConvergence('test_bootstrap', urls))
            suite.addTest(TestValidatorShutdownRestartRestore(
                'test_validator_shutdown_restart_restore_ext',
                urls, self._node_ctrl, self._nodes))
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
