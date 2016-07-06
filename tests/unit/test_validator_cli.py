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

from txnmain.validator_cli import get_configuration


class TestValidatorCLI(unittest.TestCase):
    def test_currency_home(self):
        os.environ.clear()
        os.environ["CURRENCYHOME"] = "/test_path"

        cfg = get_configuration(args=[], config_files_required=False)

        self.assertIn("CurrencyHome", cfg)
        self.assertEquals(cfg["CurrencyHome"], "/test_path")
        self.assertEquals(cfg["ConfigDirectory"], "/test_path/etc")
        self.assertEquals(cfg["LogDirectory"], "/test_path/logs")
        self.assertEquals(cfg["DataDirectory"], "/test_path/data")

    def test_default_config_posix(self):
        os.environ.clear()
        cfg = get_configuration(args=[],
                                os_name='posix',
                                config_files_required=False)

        self.assertNotIn("CurrencyHome", cfg)
        self.assertEquals(cfg["ConfigDirectory"], "/etc/sawtooth-validator")
        self.assertEquals(cfg["LogDirectory"], "/var/log/sawtooth-validator")
        self.assertEquals(cfg["DataDirectory"], "/var/lib/sawtooth-validator")

    def test_default_config_nt(self):
        os.environ.clear()
        cfg = get_configuration(args=[],
                                os_name='nt',
                                config_files_required=False)

        self.assertNotIn("CurrencyHome", cfg)
        self.assertEquals(
            cfg["ConfigDirectory"],
            "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\conf")
        self.assertEquals(
            cfg["LogDirectory"],
            "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\logs")
        self.assertEquals(
            cfg["DataDirectory"],
            "C:\\Program Files (x86)\\Intel\\sawtooth-validator\\data")

    def test_logconfig_arg(self):
        os.environ.clear()

        cfg = get_configuration(args=["--log-config=Logging.js"],
                                config_files_required=False)

        self.assertIn("LogConfigFile", cfg)
        self.assertEquals(cfg["LogConfigFile"], "Logging.js")

    def test_options_mapping_conf_dir(self):
        os.environ.clear()

        cfg = get_configuration(args=["--conf-dir=/test_path/etc"],
                                config_files_required=False)

        self.assertIn("ConfigDirectory", cfg)
        self.assertEquals(cfg["ConfigDirectory"], "/test_path/etc")

    def test_options_mapping_data_dir(self):
        os.environ.clear()

        cfg = get_configuration(args=["--data-dir=/test_path/data"],
                                config_files_required=False)

        self.assertIn("DataDirectory", cfg)
        self.assertEquals(cfg["DataDirectory"], "/test_path/data")

    def test_options_mapping_type(self):
        os.environ.clear()

        cfg = get_configuration(args=["--type=test"],
                                config_files_required=False)

        self.assertIn("LedgerType", cfg)
        self.assertEquals(cfg["LedgerType"], "test")

    def test_options_mapping_key_file(self):
        os.environ.clear()

        cfg = get_configuration(args=["--keyfile=/test_path/keys/key.wif"],
                                config_files_required=False)

        self.assertIn("KeyFile", cfg)
        self.assertEquals(cfg["KeyFile"], "/test_path/keys/key.wif")

    def test_options_mapping_node(self):
        os.environ.clear()

        cfg = get_configuration(args=["--node=test000"],
                                config_files_required=False)

        self.assertIn("NodeName", cfg)
        self.assertEquals(cfg["NodeName"], "test000")

    def test_options_mapping_host(self):
        os.environ.clear()

        cfg = get_configuration(args=["--host=testhost"],
                                config_files_required=False)

        self.assertIn("Host", cfg)
        self.assertEquals(cfg["Host"], "testhost")

    def test_options_mapping_port(self):
        os.environ.clear()

        cfg = get_configuration(args=["--port=7777"],
                                config_files_required=False)

        self.assertIn("Port", cfg)
        self.assertEquals(cfg["Port"], 7777)

    def test_options_mapping_http(self):
        os.environ.clear()

        cfg = get_configuration(args=["--http=8888"],
                                config_files_required=False)

        self.assertIn("HttpPort", cfg)
        self.assertEquals(cfg["HttpPort"], 8888)

    def test_options_mapping_restore(self):
        os.environ.clear()

        cfg = get_configuration(args=["--restore"],
                                config_files_required=False)

        self.assertEquals(cfg["Restore"], True)

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
