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
import configparser
import getpass
import logging
import os
import shutil
import unittest

from sawtooth_private_utxo.cli.main import main as cli


LOGGER = logging.getLogger(__name__)


class TestPrivateUtxoCliInit(unittest.TestCase):
    """ Tests that the Private UTXO CLI init and reset works correctly.
    """

    def cli(self, args):
        cli('private_utxo', args)

    def clean_config(self):
        home = os.path.expanduser('~')
        config_dir = os.path.join(home, '.sawtooth')

        if os.path.exists(config_dir):
            shutil.rmtree(config_dir)
            LOGGER.info("Removing directory %s", config_dir)

    def config_filename(self, username=None):
        if username is None:
            username = getpass.getuser()
        home = os.path.expanduser('~')
        return os.path.join(home, '.sawtooth',
                            'private_utxo_{}.cfg'.format(username))

    def key_file_names(self, username=None):
        username = username or getpass.getuser()
        home = os.path.expanduser('~')
        priv_filename = os.path.join(
            home, '.sawtooth', 'keys', '{}.priv'.format(username))
        addr_filename = os.path.join(
            home, '.sawtooth', 'keys', '{}.addr'.format(username))

        return [priv_filename, addr_filename]

    def expect_files(self, files):
        for fle in files:
            if not os.path.exists(fle):
                self.fail('File {} does not exist.'.format(fle))

    def expect_no_files(self, files):
        for fle in files:
            if os.path.exists(fle):
                self.fail('File {} exists and should not.'.format(fle))

    def expect_config(self, config_filename, username, key_file, url):
        config = configparser.ConfigParser()
        config.read(config_filename)
        self.assertEqual(
            key_file, config.get('DEFAULT', 'key_file'))
        self.assertEqual(
            url, config.get('DEFAULT', 'url'))

    def test_init_reset(self):
        '''
        Test the Private UTXO CLI implementation of environment initialization
        '''
        # Clean the environment
        username = getpass.getuser()
        url = '127.0.0.1:8080'
        config_filename = self.config_filename()
        key_files = self.key_file_names(username)
        config_files = [config_filename] + key_files
        self.clean_config()
        self.expect_no_files(config_files)

        # make sure a configuration is created
        self.cli(['init'])
        self.expect_files(config_files)
        self.expect_config(
            config_filename, username, key_files[0], url)

        # see that the configuration is cleaned up.
        self.cli(['reset'])
        self.expect_no_files(config_files)

    def test_init_reset_overrides(self):
        '''
        Test the Private UTXO CLI implementation of environment initialization
        Verify the username and url overrides are honored.
        '''

        # verify the overrides
        username = "fred"
        url = '127.0.0.1:8080'
        config_filename = self.config_filename(username)
        key_files = self.key_file_names(username)
        config_files = [config_filename] + key_files

        self.cli(['init', '--user', username, '--url', url])
        self.expect_config(
            config_filename, username, key_files[0], url)

        # see that the configuration is cleaned up.
        self.cli(['reset', '--user', username])
        self.expect_no_files(config_files)
