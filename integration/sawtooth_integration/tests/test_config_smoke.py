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

import logging
import unittest
import traceback
import time
import tempfile
import os
import subprocess
import argparse
from sawtooth_cli import config
import sys
from io import StringIO


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)

TEST_WIF = '5Jq6nhPbVjgi9vTUuK7e2W81VT5dpQR7qPweYJZPVJKNzSornyv'

class TestConfigSmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._temp_dir = None

        parent_parser = create_parent_parser('main')
        cls._parser = argparse.ArgumentParser(parents=[parent_parser])
        subparsers = cls._parser.add_subparsers(title='subcommands',
                                                 dest='command')

        config.add_config_parser(subparsers, parent_parser)

        cls._ExpectedSettingResults = 'x: 1\ny: 1\n'

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()
        self._data_dir = os.path.join(self._temp_dir, 'data')
        os.makedirs(self._data_dir)

        # create a wif key for signing
        self._wif_file = os.path.join(self._temp_dir, 'test.wif')
        with open(self._wif_file, 'wb') as wif:
            wif.write(TEST_WIF.encode())

    def _run(self, args):
        try:
            LOGGER.debug("Running %s", " ".join(args))
            proc = subprocess.run(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            LOGGER.debug(proc.stdout.decode())
        except subprocess.CalledProcessError as err:
            LOGGER.debug(err)
            LOGGER.debug(err.stderr.decode())
            traceback.print_exc()
            self.fail(self.__class__.__name__)

    def _parse_list_command(self):
        cmd_args = ['config', 'settings', 'list', '--url', 'http://rest_api:8080']

        return self._parser.parse_args(cmd_args)


    def test_submit_then_list_settings(self):
        ''' Test ability to list settings after submission of a setting.
            Test submits a simple config transaction to the validator,
            then confirms that the settings can be retrieved by the
            command 'sawtooth config settings list', and that the retrieved
            setting equals the input setting.
            '''

        print("test_list_settings")

        # Submit transaction, then list it using subprocess
        cmds = [
            ['sawtooth','config', 'proposal', 'create', '-k', self._wif_file,
             '--url', 'http://rest_api:8080', 'x=1', 'y=1'],
            ['sawtooth', 'config', 'settings', 'list', '--url',
             'http://rest_api:8080']
        ]

        for cmd in cmds:
            self._run(cmd)

        # Retrieve string of setting contents for comparison to input settings
        args = self._parse_list_command()

        # backup the environment
        backup = sys.stdout
        sys.stdout = StringIO()   # Capture the output of next statement
        config.do_config(args)
        settings = sys.stdout.getvalue() # release the output and store
        sys.stdout.close()
        # Restore the environment
        sys.stdout = backup

        self.assertEqual(settings, self._ExpectedSettingResults, 'Setting results did not match.' )

def create_parent_parser(prog_name):
    parent_parser = argparse.ArgumentParser(prog=prog_name, add_help=False)
    parent_parser.add_argument(
        '-v', '--verbose',
        action='count',
        help='enable more verbose output')

    return parent_parser

