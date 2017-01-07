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

import argparse
import os
import tempfile
import unittest

from sawtooth.config import AggregateConfig
from sawtooth.config import ArgparseOptionsConfig
from sawtooth.config import Config
from sawtooth.config import EnvConfig
from sawtooth.config import JsonConfig
from sawtooth.config import JsonFileConfig


class TestEnvConfig(unittest.TestCase):
    def test_load_from_env_notset(self):
        """Verifies that a configuration variable will not be set if
        it is missing from os.environ."""
        env_bak = dict(os.environ)
        os.environ.clear()
        cfg = EnvConfig([("TEST_VAR", "test_env_var")])
        self.assertIsNotNone(cfg)
        self.assertNotIn("test_env_var", cfg)

        os.environ.update(env_bak)

    def test_load_from_env_set(self):
        """Verifies that a configuration variable will be set correctly if
        it is present in os.environ."""

        env_bak = dict(os.environ)
        os.environ.clear()
        os.environ["TEST_VAR"] = "set"
        cfg = EnvConfig([("TEST_VAR", "test_env_var")])
        self.assertIn("test_env_var", cfg)
        self.assertEqual(cfg["test_env_var"], "set")

        os.environ.update(env_bak)


class TestJsonishConfig(unittest.TestCase):
    def test_load_from_jsonish_file(self):
        """Verifies that we can load and retrieve a variable from a file
        when loading with a filename."""

        filename = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                filename = f.name
                f.write('{ "TestVar": "test_value" }\n')
            cfg = JsonFileConfig(filename)
        finally:
            if filename is not None:
                os.unlink(filename)

        self.assertIn("TestVar", cfg)
        self.assertEqual(cfg["TestVar"], "test_value")

    def test_load_from_jsonish_no_filename(self):
        """Verifies that we can use JsonConfig without specifying a
        filename."""

        cfg = JsonConfig(['{ "TestVar": "test_value" }'])

        self.assertIn("TestVar", cfg)
        self.assertEqual(cfg["TestVar"], "test_value")


class TestArgparseOptionsConfig(unittest.TestCase):
    def test_argparse_options_config(self):
        """Verifies that an option set via the command line is in the
        config and that an unset option is not."""

        parser = argparse.ArgumentParser()
        parser.add_argument('--cli-option')
        parser.add_argument('--unset')
        options = parser.parse_args(['--cli-option=value'])

        cfg = ArgparseOptionsConfig(
            [
                ("cli_option", "CliOption"), ("unset", "UnsetOption")
            ], options)

        self.assertIn("CliOption", cfg)
        self.assertNotIn("UnsetOption", cfg)
        self.assertEqual(cfg["CliOption"], "value")


class TestAggregateConfig(unittest.TestCase):
    def test_aggregate_config(self):
        """Test that resolution of values and sources operate as expected."""

        config1 = Config(source="config1name")
        config1["keya"] = "value1"
        config1["keyb"] = "value1"

        config2 = Config(source="config2name")
        config2["keyb"] = "value2"
        config2["keyc"] = "value2"

        config3 = Config(source="config3name")
        config3["keyc"] = "value3"

        multi = AggregateConfig([config1, config2, config3])

        self.assertEqual(multi["keya"], "value1")
        self.assertEqual(multi["keyb"], "value2")
        self.assertEqual(multi["keyc"], "value3")

        self.assertEqual(multi.get_source("keya"), "config1name")
        self.assertEqual(multi.get_source("keyb"), "config2name")
        self.assertEqual(multi.get_source("keyc"), "config3name")


class TestConfig(unittest.TestCase):
    def test_config_resolve(self):
        """Test that resolution of substituted values operate as expected.

        Tests the recursion of values, and that circular dependencies
        break in the expected manner."""

        cfg = Config()
        cfg["keya"] = "value1"
        cfg["keyb"] = "{A}"
        cfg["keyc"] = "{B}"
        cfg["keyd"] = "{C}"
        cfg["keye"] = "{D}"
        cfg["keyf"] = "{E}"
        cfg["keyg"] = "{F}"
        cfg["keyh"] = "{G}"
        cfg["keyi"] = "{H}"
        cfg["circ1"] = "{c2}"
        cfg["circ2"] = "{c1}"
        cfg["circular"] = "{circular}"
        cfg["list"] = ["should", "be", "ignored"]

        resolved = cfg.resolve({
            "A": "keya",
            "B": "keyb",
            "C": "keyc",
            "D": "keyd",
            "E": "keye",
            "F": "keyf",
            "G": "keyg",
            "H": "keyh",
            "c1": "circ1",
            "c2": "circ2",
            "circular": "circular",
            "undef": "undef",
        })

        self.assertEqual(resolved["keyb"], "value1")
        self.assertEqual(resolved["keyc"], "value1")
        self.assertEqual(resolved["keyd"], "value1")
        self.assertEqual(resolved["keye"], "value1")
        self.assertEqual(resolved["keyf"], "value1")
        self.assertEqual(resolved["keyg"], "value1")
        self.assertEqual(resolved["keyh"], "value1")
        self.assertEqual(resolved["keyi"], "value1")
        self.assertIn(resolved["circ1"], ["{c1}", "{c2}"])
        self.assertIn(resolved["circ2"], ["{c1}", "{c2}"])
        self.assertEqual(resolved["circular"], "{circular}")


if __name__ == '__main__':
    unittest.main()
