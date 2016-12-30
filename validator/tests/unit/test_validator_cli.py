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

from txnserver.validator_cli import get_configuration


class TestValidatorCLI(unittest.TestCase):
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
        cfg = get_configuration(args=[],
                                os_name='posix',
                                config_files_required=False)

        self.assertNotIn("CurrencyHome", cfg)
        self.assertEqual(cfg["ConfigDirectory"], "/etc/sawtooth-validator")
        self.assertEqual(cfg["LogDirectory"], "/var/log/sawtooth-validator")
        self.assertEqual(cfg["DataDirectory"], "/var/lib/sawtooth-validator")

    def test_default_config_nt(self):
        os.environ.clear()
        cfg = get_configuration(args=[],
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

        cfg = get_configuration(args=["--log-config=Logging.js"],
                                config_files_required=False)

        self.assertIn("LogConfigFile", cfg)
        self.assertEqual(cfg["LogConfigFile"], "Logging.js")

    def test_options_mapping_conf_dir(self):
        os.environ.clear()

        cfg = get_configuration(args=["--conf-dir=/test_path/etc"],
                                config_files_required=False)

        self.assertIn("ConfigDirectory", cfg)
        self.assertEqual(cfg["ConfigDirectory"], "/test_path/etc")

    def test_options_mapping_data_dir(self):
        os.environ.clear()

        cfg = get_configuration(args=["--data-dir=/test_path/data"],
                                config_files_required=False)

        self.assertIn("DataDirectory", cfg)
        self.assertEqual(cfg["DataDirectory"], "/test_path/data")

    def test_options_mapping_type(self):
        os.environ.clear()

        cfg = get_configuration(args=["--type=test"],
                                config_files_required=False)

        self.assertIn("LedgerType", cfg)
        self.assertEqual(cfg["LedgerType"], "test")

    def test_options_mapping_key_file(self):
        os.environ.clear()

        cfg = get_configuration(args=["--keyfile=/test_path/keys/key.wif"],
                                config_files_required=False)

        self.assertIn("KeyFile", cfg)
        self.assertEqual(cfg["KeyFile"], "/test_path/keys/key.wif")

    def test_options_mapping_node(self):
        os.environ.clear()

        cfg = get_configuration(args=["--node=test000"],
                                config_files_required=False)

        self.assertIn("NodeName", cfg)
        self.assertEqual(cfg["NodeName"], "test000")

    def test_options_mapping_listsn(self):
        os.environ.clear()

        cfg = get_configuration(args=['--listen="localhost:5500/UDP gossip"'],
                                config_files_required=False)

        self.assertIn("Listen", cfg)
        self.assertEqual(cfg["Listen"], ['"localhost:5500/UDP gossip"'])

    def test_options_mapping_peers(self):
        os.environ.clear()

        cfg = get_configuration(args=["--peers=testpeer1"],
                                config_files_required=False)

        self.assertIn("Peers", cfg)
        self.assertIn("testpeer1", cfg["Peers"])

    def test_options_mapping_url(self):
        os.environ.clear()

        cfg = get_configuration(args=["--url",
                                      "http://testhost:8888,"
                                      "http://testhost:8889",
                                      "--url",
                                      "http://testhost:8890"],
                                config_files_required=False)

        self.assertIn("LedgerURL", cfg)
        self.assertIn("http://testhost:8888", cfg["LedgerURL"])
        self.assertIn("http://testhost:8889", cfg["LedgerURL"])
        self.assertIn("http://testhost:8890", cfg["LedgerURL"])


if __name__ == '__main__':
    unittest.main()
