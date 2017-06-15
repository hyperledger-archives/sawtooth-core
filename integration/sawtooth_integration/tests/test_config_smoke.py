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
import tempfile
import os
import subprocess
from sawtooth_cli.main import main
import sys
from io import StringIO

from sawtooth_integration.tests.integration_tools import wait_for_rest_apis

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)

TEST_WIF = '5Jq6nhPbVjgi9vTUuK7e2W81VT5dpQR7qPweYJZPVJKNzSornyv'
TEST_PUBKEY = \
    '033775c26a68a3872f03314ccd080b8d8ec828572469737c7d3aa467f853a069d5'


class TestConfigSmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        wait_for_rest_apis(['rest_api:8080'])

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()
        self._data_dir = os.path.join(self._temp_dir, 'data')
        os.makedirs(self._data_dir)

        # create a wif key for signing
        self._wif_file = os.path.join(self._temp_dir, 'test.priv')
        with open(self._wif_file, 'wb') as wif:
            wif.write(TEST_WIF.encode())

    def _run(self, args):
        try:
            LOGGER.debug("Running %s", " ".join(args))
            proc = subprocess.run(args,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  check=True)
            LOGGER.debug(proc.stdout.decode())
        except subprocess.CalledProcessError as err:
            LOGGER.debug(err)
            LOGGER.debug(err.stderr.decode())
            traceback.print_exc()
            self.fail(self.__class__.__name__)

    def _read_from_stdout(self, cmd, args):
        # Retrieve string of setting contents for comparison to input settings
        backup = sys.stdout  # backup the environment
        sys.stdout = StringIO()  # Capture the output of next statement

        main(cmd, args)
        settings = sys.stdout.getvalue()  # release the output and store
        sys.stdout.close()
        # Restore the environment
        sys.stdout = backup
        return settings

    def test_submit_then_list_settings(self):
        ''' Test ability to list settings after submission of a setting.
            Test submits a simple config transaction to the validator,
            then confirms that the settings can be retrieved by the
            command 'sawtooth config settings list', and that the retrieved
            setting equals the input setting.
            '''
        # Submit transaction, then list it using subprocess
        cmds = [
            ['sawtooth', 'config', 'proposal', 'create', '-k', self._wif_file,
             '--url', 'http://rest_api:8080', 'x=1', 'y=1'],
            ['sawtooth', 'config', 'settings', 'list', '--url',
             'http://rest_api:8080']
        ]

        for cmd in cmds:
            self._run(cmd)

        command = 'sawtooth'
        args = ['config', 'settings', 'list', '--url', 'http://rest_api:8080']
        settings = self._read_from_stdout(command, args).split('\n')

        _expected_output = [
            'sawtooth.settings.vote.authorized_keys: {:15}'.format(TEST_PUBKEY),
            'x: 1',
            'y: 1']
        _fail_msg = 'Setting results did not match.'

        self.assertTrue(settings[0].startswith(_expected_output[0]), _fail_msg)
        self.assertEqual(settings[1], _expected_output[1], _fail_msg)
        self.assertEqual(settings[2], _expected_output[2], _fail_msg)
