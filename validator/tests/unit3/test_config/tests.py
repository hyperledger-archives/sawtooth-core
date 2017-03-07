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
import sys
import tempfile

from sawtooth_validator.config.path import load_path_config
from sawtooth_validator.exceptions import LocalConfigurationError


class TestPathConfig(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)

    def test_path_config_defaults_for_linux(self):
        """Tests the default path configuration settings on Linux and other
        POSIX environments.

        Sets os.name to 'posix' (so the test works on all platforms), then
        compares all path settings to their expected default value.

            - config_dir = /etc/sawtooth
            - key_dir    = /etc/sawtooth/keys
            - data_dir   = /var/lib/sawtooth
            - log_dir    = /var/log/sawtooth

        Also specifies a configuration directory which does not exist (as we
        want to avoid loading any files for this test).

        The test also attempts to avoid environment variables from interfering
        with the test by clearing os.environ and restoring it after the test.
        """
        orig_os_name = os.name
        orig_environ = dict(os.environ)
        try:
            os.name = 'posix'
            os.environ.clear()

            config = load_path_config()
            self.assertEqual(config.config_dir, "/etc/sawtooth")
            self.assertEqual(config.key_dir, "/etc/sawtooth/keys")
            self.assertEqual(config.data_dir, "/var/lib/sawtooth")
            self.assertEqual(config.log_dir, "/var/log/sawtooth")
        finally:
            os.name = orig_os_name
            os.environ.update(orig_environ)

    def test_path_config_defaults_for_windows(self):
        """Tests the default path configuration settings on Windows operating
        systems.

        Sets os.name to 'nt' (so the test works on all platforms), then
        compares all path settings to their expected default value.

            - config_dir = /etc/sawtooth
            - key_dir    = /etc/sawtooth/keys
            - data_dir   = /var/lib/sawtooth
            - log_dir    = /var/log/sawtooth

        Also specifies a configuration directory which does not exist (as we
        want to avoid loading any files for this test).

        The test also attempts to avoid environment variables from interfering
        with the test by clearing os.environ and restoring it after the test.
        """
        orig_os_name = os.name
        orig_argv0 = sys.argv[0]
        try:
            os.name = 'nt'
            sys.argv[0] = "/tmp/no-such-directory/bin/validator"

            config = load_path_config()
            self.assertEqual(config.config_dir,
                             "/tmp/no-such-directory/conf")
            self.assertEqual(config.key_dir,
                             "/tmp/no-such-directory/conf/keys")
            self.assertEqual(config.data_dir,
                             "/tmp/no-such-directory/data")
            self.assertEqual(config.log_dir,
                             "/tmp/no-such-directory/logs")
        finally:
            os.name = orig_os_name
            sys.argv[0] = orig_argv0

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

            config = load_path_config()
            self.assertEqual(config.config_dir, config_dir)
            self.assertEqual(config.key_dir,
                             "/tmp/no-such-dir-from-config/keys")
            self.assertEqual(config.data_dir,
                             "/tmp/no-such-dir-from-config/data")
            self.assertEqual(config.log_dir,
                             "/tmp/no-such-dir-from-config/logs")
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
