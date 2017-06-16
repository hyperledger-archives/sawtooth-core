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
import time
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


class TestPermission(unittest.TestCase):

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

    def _try_to_get_output(self, cmd, args, required):
        # Temporary function until --wait is added to sawtooth config
        for i in range(10):
            settings = self._read_from_stdout(cmd, args)
            if required in settings:
                return settings
            time.sleep(1)
        self.fail("Changes were not committed in 5 seconds.")

    def _assert_line_starts_match(self, raw_output, expected_line_starts):
        output_lines = raw_output.split('\n')

        for output, expected in zip(output_lines, expected_line_starts):
            self.assertTrue(
                output.startswith(expected),
                'List output "{}" did not match "{}"'.format(output, expected))


    def test_allowed_signing_keys(self):
        ''' Test that keys set at sawtooth.validator.allowed_signing_keys are
            allowed to sumbit batches and other keys are not allowed.
            1. Test no keys set. In this case any public key may submit batches
            2. One key is set and can sumbit batches.
            3. Multiple keys can be set and one of those public keys may Submit
               batches.
            4. A public key, not in the allowed list, sends a batch. This
               batch should not be accepted and the settings list should not
               change.

        '''
        self._check_no_signing_keys_set()
        self._check_allowed_signing_key()
        self._check_multiple_allowed_signing_keys()
        self._check_unallowed_signing_key()

    def _check_no_signing_keys_set(self):
        ''' Test ability to sumbit a batch when no allowd signing keys are set.
            If no keys are set, any public key should be able to sumbit a
            batch.

            Try to set setting x=1 and check it was set correctly

        '''
        # Submit transaction, then list it using subprocess
        cmds = [
            ['sawtooth', 'config', 'proposal', 'create', '-k', self._wif_file,
             '--url', 'http://rest_api:8080', 'x=1'],
            ['sawtooth', 'config', 'settings', 'list', '--url',
             'http://rest_api:8080']
        ]
        for cmd in cmds:
            self._run(cmd)

        command = 'sawtooth'
        args = ['config', 'settings', 'list', '--url', 'http://rest_api:8080']
        settings = self._try_to_get_output(command, args, 'x: 1')
        _expected_output = [
            'sawtooth.settings.vote.authorized_keys: {}'.format(
                TEST_PUBKEY[:15]),
            'x: 1']
        _fail_msg ='Setting results did not match.'
        self._assert_line_starts_match(settings, _expected_output)

    def _check_allowed_signing_key(self):
        ''' Test ability to set approved signing key and check that a setting
            is added when set with an approved key.

            Add public_key to allowed_signing_keys and see if that key can
            can set y=1. Check settings output.

        '''
        # Set allowed_signing_keys
        command = 'sawtooth'
        args = ['config', 'settings', 'list', '--url', 'http://rest_api:8080']
        _fail_msg ='Setting results did not match.'
        self._run(['sawtooth', 'config', 'proposal', 'create', '-k',
                  self._wif_file, '--url', 'http://rest_api:8080',
                  'sawtooth.validator.allowed_signing_keys={}'
                  .format(TEST_PUBKEY)])
        self._try_to_get_output(command, args,
            'sawtooth.validator.allowed_signing_keys')
        self._run(['sawtooth', 'config', 'proposal', 'create', '-k',
                 self._wif_file, '--url', 'http://rest_api:8080', 'y=1'])
        # Wait for block to be processed
        self._run(['sawtooth', 'config', 'settings', 'list', '--url',
                  'http://rest_api:8080'])

        settings = self._try_to_get_output(command, args, 'y: 1')
        _expected_output = [
            'sawtooth.settings.vote.authorized_keys: {}'
                .format(TEST_PUBKEY[:15]),
            'sawtooth.validator.allowed_signing_keys: {}'
                .format(TEST_PUBKEY[:15]),
            'x: 1',
            'y: 1']
        self._assert_line_starts_match(settings, _expected_output)

    def _check_multiple_allowed_signing_keys(self):
        ''' Test ability to set multiple approved signing keys and check that
            a setting is added when set with an approved key.

            Set allowed signing key to a different key to SomeOtherKey and
            the public key. See if the public key can still set z=1.
            Check settings output.

        '''
        command = 'sawtooth'
        args = ['config', 'settings', 'list', '--url', 'http://rest_api:8080']
        _fail_msg ='Setting results did not match.'
        self._run(['sawtooth', 'config', 'proposal', 'create', '-k',
                  self._wif_file, '--url', 'http://rest_api:8080',
                  'sawtooth.validator.allowed_signing_keys=SomeOtherKey,{}'
                  .format(TEST_PUBKEY)])
        self._try_to_get_output(command, args, 'SomeOtherKey')
        self._run(['sawtooth', 'config', 'proposal', 'create', '-k',
                 self._wif_file, '--url', 'http://rest_api:8080', 'z=1'])
        # Wait for block to be processed
        self._run(['sawtooth', 'config', 'settings', 'list', '--url',
                  'http://rest_api:8080'])
        # Check that allowed_signing_keys is set.
        settings = self._try_to_get_output(command, args, 'z: 1')
        _expected_output = [
            'sawtooth.settings.vote.authorized_keys: {}'
                .format(TEST_PUBKEY[:15]),
            'sawtooth.validator.allowed_signing_keys: SomeOtherKey,{}'
                .format(TEST_PUBKEY[:2]),
            'x: 1',
            'y: 1',
            'z: 1']
        self._assert_line_starts_match(settings, _expected_output)

    def _check_unallowed_signing_key(self):
        ''' Test ability to set approved signing keys and check that a setting
            is not added when set with an unapproved key.

            Set allowed siging key to just SomeOtherKey.
            This should make any batches sent from the configured keys
            fail. Try to set a=1. This should fail, and not change the
            set settings.

        '''
        command = 'sawtooth'
        args = ['config', 'settings', 'list', '--url', 'http://rest_api:8080']
        _fail_msg ='Setting results did not match.'
        # Set allowed signing key to a different key to "SomeOtherKey".
        # This should make any batches sent from the configured keys fail.
        self._run(['sawtooth', 'config', 'proposal', 'create', '-k',
                  self._wif_file, '--url', 'http://rest_api:8080',
                  'sawtooth.validator.allowed_signing_keys=SomeOtherKey'])
        # Wait for block to be processed
        time.sleep(1)
        self._run(['sawtooth', 'config', 'settings', 'list', '--url',
                  'http://rest_api:8080'])

        # Check that allowed_signing_key is set.
        settings = self._try_to_get_output(
            command, args,
            "sawtooth.validator.allowed_signing_keys: SomeOtherKey")
        _expected_output = [
            'sawtooth.settings.vote.authorized_keys: {}'
                .format(TEST_PUBKEY[:15]),
            'sawtooth.validator.allowed_signing_keys: SomeOtherKey',
            'x: 1',
            'y: 1',
            'z: 1']
        self._assert_line_starts_match(settings, _expected_output)

        self._run(['sawtooth', 'config', 'proposal', 'create', '-k',
                 self._wif_file, '--url', 'http://rest_api:8080', 'a=1'])
        # Wait for block to be processed
        time.sleep(3)
        self._run(['sawtooth', 'config', 'settings', 'list', '--url',
                  'http://rest_api:8080'])
        settings = self._read_from_stdout(command, args)

        # Same _expected_setting_result as the last assert
        self._assert_line_starts_match(settings, _expected_output)
        self.assertTrue('a=1' not in settings)
