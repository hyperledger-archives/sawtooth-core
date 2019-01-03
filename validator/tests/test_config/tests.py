# Copyright 2017 Intel Corporation
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
import shutil
import tempfile

from sawtooth_validator.config.path import load_path_config
from sawtooth_validator.exceptions import LocalConfigurationError
from sawtooth_validator.config.validator import load_default_validator_config
from sawtooth_validator.config.validator import load_toml_validator_config


class TestPathConfig(unittest.TestCase):
    def test_path_config_defaults_sawtooth_home(self):
        """Tests the default path configuration settings when SAWTOOTH_HOME
        is set.

        Sets the SAWTOOTH_HOME environment variable to
        /tmp/no-such-sawtooth-home, then compares all path settings for their
        expected values.

            - config_dir = /tmp/no-such-sawtooth-home/etc
            - key_dir    = /tmp/no-such-sawtooth-home/keys
            - data_dir   = /tmp/no-such-sawtooth-home/data
            - log_dir    = /tmp/no-such-sawtooth-home/logs

        Also specifies a configuration directory which does not exist (as we
        want to avoid loading any files for this test).  We use a different
        directory than SAWTOOTH_HOME as the config directory specified for
        config files should not impact the settings.

        The test also attempts to avoid environment variables from interfering
        with the test by clearing os.environ and restoring it after the test.
        """
        orig_environ = dict(os.environ)
        os.environ.clear()
        try:
            os.environ['SAWTOOTH_HOME'] = '/tmp/no-such-sawtooth-home'

            config = load_path_config()
            self.assertEqual(config.config_dir,
                             "/tmp/no-such-sawtooth-home/etc")
            self.assertEqual(config.key_dir,
                             "/tmp/no-such-sawtooth-home/keys")
            self.assertEqual(config.data_dir,
                             "/tmp/no-such-sawtooth-home/data")
            self.assertEqual(config.log_dir,
                             "/tmp/no-such-sawtooth-home/logs")
            self.assertEqual(config.policy_dir,
                             "/tmp/no-such-sawtooth-home/policy")
        finally:
            os.environ.clear()
            os.environ.update(orig_environ)

    def test_path_config_load_from_file(self):
        """Tests loading config settings from a TOML configuration file.

        Sets the SAWTOOTH_HOME environment variable to a temporary directory,
        writes a path.toml config file, then loads that config and verifies
        all the path settings are their expected values.

        The test also attempts to avoid environment variables from interfering
        with the test by clearing os.environ and restoring it after the test.
        """
        orig_environ = dict(os.environ)
        os.environ.clear()
        directory = tempfile.mkdtemp(prefix="test-path-config-")
        try:
            os.environ['SAWTOOTH_HOME'] = directory

            config_dir = os.path.join(directory, 'etc')
            os.mkdir(config_dir)

            with open(os.path.join(config_dir, 'path.toml'), 'w') as fd:
                fd.write('key_dir = "/tmp/no-such-dir-from-config/keys"')
                fd.write(os.linesep)
                fd.write('data_dir = "/tmp/no-such-dir-from-config/data"')
                fd.write(os.linesep)
                fd.write('log_dir = "/tmp/no-such-dir-from-config/logs"')
                fd.write(os.linesep)
                fd.write('policy_dir = "/tmp/no-such-dir-from-config/policy"')
                fd.write(os.linesep)

            config = load_path_config()
            self.assertEqual(config.config_dir, config_dir)
            self.assertEqual(config.key_dir,
                             "/tmp/no-such-dir-from-config/keys")
            self.assertEqual(config.data_dir,
                             "/tmp/no-such-dir-from-config/data")
            self.assertEqual(config.log_dir,
                             "/tmp/no-such-dir-from-config/logs")
            self.assertEqual(config.policy_dir,
                             "/tmp/no-such-dir-from-config/policy")
        finally:
            os.environ.clear()
            os.environ.update(orig_environ)
            shutil.rmtree(directory)

    def test_path_config_invalid_setting_in_file(self):
        """Tests detecting invalid settings defined in a TOML configuration
        file.

        Sets the SAWTOOTH_HOME environment variable to a temporary directory,
        writes a path.toml config file with an invalid setting inside, then
        loads that config and verifies an exception is thrown.

        The test also attempts to avoid environment variables from interfering
        with the test by clearing os.environ and restoring it after the test.
        """
        orig_environ = dict(os.environ)
        os.environ.clear()
        directory = tempfile.mkdtemp(prefix="test-path-config-")
        try:
            os.environ['SAWTOOTH_HOME'] = directory

            config_dir = os.path.join(directory, 'etc')
            os.mkdir(config_dir)

            with open(os.path.join(config_dir, 'path.toml'), 'w') as fd:
                fd.write('invalid = "a value"')
                fd.write(os.linesep)

            self.assertRaises(LocalConfigurationError, load_path_config)
        finally:
            os.environ.clear()
            os.environ.update(orig_environ)
            shutil.rmtree(directory)


class TestValidatorConfig(unittest.TestCase):
    def test_validator_config_defaults(self):
        """Tests the default validator configuration when no other configs.
        The defaults should be as follows:
            - bind_network = "tcp://127.0.0.1:8800"
            - bind_component = "tcp://127.0.0.1:4004"
            - peering = "static"
            - endpoint = None
        """
        config = load_default_validator_config()
        self.assertEqual(config.bind_network, "tcp://127.0.0.1:8800")
        self.assertEqual(config.bind_component, "tcp://127.0.0.1:4004")
        self.assertEqual(config.endpoint, None)
        self.assertEqual(config.peering, "static")
        self.assertEqual(config.scheduler, "parallel")
        self.assertEqual(config.minimum_peer_connectivity, 3)
        self.assertEqual(config.maximum_peer_connectivity, 10)

    def test_validator_config_load_from_file(self):
        """Tests loading config settings from a TOML configuration file.

        Creates a temporary directory and writes a validator.toml config file,
        then loads that config and verifies all the validator settings are
        their expected values.

        The test also attempts to avoid environment variables from interfering
        with the test by clearing os.environ and restoring it after the test.
        """
        orig_environ = dict(os.environ)
        os.environ.clear()
        directory = tempfile.mkdtemp(prefix="test-path-config-")
        try:
            os.environ['SAWTOOTH_HOME'] = directory

            config_dir = os.path.join(directory, 'etc')
            os.mkdir(config_dir)
            filename = os.path.join(config_dir, 'validator.toml')
            with open(filename, 'w') as fd:
                fd.write('bind = ["network:tcp://test:8800",'
                         '"component:tcp://test:4004"]')
                fd.write(os.linesep)
                fd.write('peering = "dynamic"')
                fd.write(os.linesep)
                fd.write('endpoint = "tcp://test:8800"')
                fd.write(os.linesep)
                fd.write('peers = ["tcp://peer:8801"]')
                fd.write(os.linesep)
                fd.write('seeds = ["tcp://peer:8802"]')
                fd.write(os.linesep)
                fd.write('scheduler = "parallel"')
                fd.write(os.linesep)
                fd.write('opentsdb_db = "data_base"')
                fd.write(os.linesep)
                fd.write('opentsdb_url = "http://data_base:0000"')
                fd.write(os.linesep)
                fd.write('opentsdb_username = "name"')
                fd.write(os.linesep)
                fd.write('opentsdb_password = "secret"')
                fd.write(os.linesep)
                fd.write('minimum_peer_connectivity = 1')
                fd.write(os.linesep)
                fd.write('maximum_peer_connectivity = 100')
                fd.write(os.linesep)
                fd.write('[roles]')
                fd.write(os.linesep)
                fd.write('network = "trust"')
                fd.write(os.linesep)

            config = load_toml_validator_config(filename)
            self.assertEqual(config.bind_network, "tcp://test:8800")
            self.assertEqual(config.bind_component, "tcp://test:4004")
            self.assertEqual(config.peering, "dynamic")
            self.assertEqual(config.endpoint, "tcp://test:8800")
            self.assertEqual(config.peers, ["tcp://peer:8801"])
            self.assertEqual(config.seeds, ["tcp://peer:8802"])
            self.assertEqual(config.scheduler, "parallel")
            self.assertEqual(config.roles, {"network": "trust"})
            self.assertEqual(config.opentsdb_db, "data_base")
            self.assertEqual(config.opentsdb_url, "http://data_base:0000")
            self.assertEqual(config.opentsdb_username, "name")
            self.assertEqual(config.opentsdb_password, "secret")
            self.assertEqual(config.minimum_peer_connectivity, 1)
            self.assertEqual(config.maximum_peer_connectivity, 100)

        finally:
            os.environ.clear()
            os.environ.update(orig_environ)
            shutil.rmtree(directory)

    def test_path_config_invalid_setting_in_file(self):
        """Tests detecting invalid settings defined in a TOML configuration
        file.

        Creates a temporary directory and writes a validator.toml
        config file with an invalid setting inside, then loads that
        config and verifies an exception is thrown.


        The test also attempts to avoid environment variables from
        interfering with the test by clearing os.environ and restoring
        it after the test.
        """
        orig_environ = dict(os.environ)
        os.environ.clear()
        directory = tempfile.mkdtemp(prefix="test-path-config-")
        try:
            os.environ['SAWTOOTH_HOME'] = directory

            config_dir = os.path.join(directory, 'etc')
            os.mkdir(config_dir)
            filename = os.path.join(config_dir, 'validator.toml')
            with open(filename, 'w') as fd:
                fd.write('invalid = "a value"')
                fd.write(os.linesep)
            with self.assertRaises(LocalConfigurationError):
                load_toml_validator_config(filename)
        finally:
            os.environ.clear()
            os.environ.update(orig_environ)
            shutil.rmtree(directory)
