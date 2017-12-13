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

from sawtooth_rest_api.config import load_default_rest_api_config
from sawtooth_rest_api.config import load_toml_rest_api_config
from sawtooth_rest_api.exceptions import RestApiConfigurationError


class TestRestApiConfig(unittest.TestCase):
    def test_rest_api_defaults_sawtooth_home(self):
        """Tests the default REST API configuration.

            - bind = ["127.0.0.1:8008"]
            - connect = "tcp://localhost:4004"
            - timeout = 300

        """
        config = load_default_rest_api_config()
        self.assertEqual(config.bind, ["127.0.0.1:8008"])
        self.assertEqual(config.connect, "tcp://localhost:4004")
        self.assertEqual(config.timeout, 300)

    def test_rest_api_config_load_from_file(self):
        """Tests loading config settings from a TOML configuration file.

        Sets the SAWTOOTH_HOME environment variable to a temporary directory,
        writes a rest_api.toml config file, then loads that config and verifies
        all the rest_api settings are their expected values.

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
            filename = os.path.join(config_dir, 'rest_api.toml')
            with open(filename, 'w') as fd:
                fd.write('bind = ["test:1234"]')
                fd.write(os.linesep)
                fd.write('connect = "tcp://test:4004"')
                fd.write(os.linesep)
                fd.write('timeout = 10')
                fd.write(os.linesep)
                fd.write('opentsdb_db = "data_base"')
                fd.write(os.linesep)
                fd.write('opentsdb_url = "http://data_base:0000"')
                fd.write(os.linesep)
                fd.write('opentsdb_username = "name"')
                fd.write(os.linesep)
                fd.write('opentsdb_password = "secret"')

            config = load_toml_rest_api_config(filename)
            self.assertEqual(config.bind, ["test:1234"])
            self.assertEqual(config.connect, "tcp://test:4004")
            self.assertEqual(config.timeout, 10)
            self.assertEqual(config.opentsdb_db, "data_base")
            self.assertEqual(config.opentsdb_url, "http://data_base:0000")
            self.assertEqual(config.opentsdb_username, "name")
            self.assertEqual(config.opentsdb_password, "secret")

        finally:
            os.environ.clear()
            os.environ.update(orig_environ)
            shutil.rmtree(directory)

    def test_path_config_invalid_setting_in_file(self):
        """Tests detecting invalid settings defined in a TOML configuration
        file.

        Sets the SAWTOOTH_HOME environment variable to a temporary directory,
        writes a rest_api.toml config file with an invalid setting inside, then
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
            filename = os.path.join(config_dir, 'rest_api.toml')
            with open(filename, 'w') as fd:
                fd.write('invalid = "a value"')
                fd.write(os.linesep)

            with self.assertRaises(RestApiConfigurationError):
                load_toml_rest_api_config(filename)
        finally:
            os.environ.clear()
            os.environ.update(orig_environ)
            shutil.rmtree(directory)
