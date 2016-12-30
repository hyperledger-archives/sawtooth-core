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

import os
import unittest

from txnmain.admin_cli import get_configuration


class TestClientCLI(unittest.TestCase):
    def setUp(self):
        self.save_environ = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.save_environ)

    def test_currency_home(self):
        os.environ.clear()
        os.environ["CURRENCYHOME"] = "/test_path"

        cfg = get_configuration(args=[], config_files_required=False)

        self.assertIn("CurrencyHome", cfg)
        self.assertEqual(cfg["CurrencyHome"], "/test_path")
        self.assertEqual(cfg["ConfigDirectory"], "/test_path/etc")
        self.assertEqual(cfg["LogDirectory"], "/test_path/logs")
        self.assertEqual(cfg["DataDirectory"], "/test_path/data")

    def test_default_config_posix(self):
        os.environ.clear()
        cfg = get_configuration(args=["--config=invalid-config.js"],
                                os_name='posix',
                                config_files_required=False)

        self.assertNotIn("CurrencyHome", cfg)
        self.assertEqual(cfg["ConfigDirectory"], "/etc/sawtooth-validator")
        self.assertEqual(cfg["LogDirectory"], "/var/log/sawtooth-validator")
        self.assertEqual(cfg["DataDirectory"], "/var/lib/sawtooth-validator")

    def test_default_config_nt(self):
        os.environ.clear()
        cfg = get_configuration(args=["--config=invalid-config.js"],
                                os_name='nt',
                                config_files_required=False)

        self.assertNotIn("CurrencyHome", cfg)
        self.assertEqual(
            cfg["ConfigDirectory"],
            "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\conf")
        self.assertEqual(
            cfg["LogDirectory"],
            "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\logs")
        self.assertEqual(
            cfg["DataDirectory"],
            "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\data")

    def test_logconfig_arg(self):
        os.environ.clear()

        cfg = get_configuration(
            args=["--config=invalid-config.js", "--log-config=Logging.js"],
            config_files_required=False)

        self.assertIn("LogConfigFile", cfg)
        self.assertEqual(cfg["LogConfigFile"], "Logging.js")


if __name__ == '__main__':
    unittest.main()
