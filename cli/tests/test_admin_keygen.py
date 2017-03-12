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

import argparse
import os
import unittest

from sawtooth_signing import secp256k1_signer as signing
from sawtooth_cli.admin_command import keygen
from sawtooth_cli.admin_command.utils import ensure_directory
from sawtooth_cli.exceptions import CliException


class TestKeygen(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._parser = None
        cls._key_dir = ensure_directory('etc/keys', '/etc/sawtooth/keys')
        cls._key_name = 'test_key'
        cls._wif_filename = os.path.join(cls._key_dir,
                                         cls._key_name + '.wif')
        cls._addr_filename = os.path.join(cls._key_dir,
                                          cls._key_name + '.addr')

    def setUp(self):
        self._parser = argparse.ArgumentParser(add_help=False)

        parent_parser = argparse.ArgumentParser(prog='test_keygen',
                                                add_help=False)

        subparsers = self._parser.add_subparsers(title='subcommands',
                                                 dest='command')

        keygen.add_keygen_parser(subparsers, parent_parser)

    def tearDown(self):
        self.remove_key_files()

    def _parse_keygen_command(self, *args):
        cmd_args = ['keygen']
        cmd_args += args
        return self._parser.parse_args(cmd_args)

    def test_writes_valid_key(self):
        """Remove existing test files before creating new keys.
        """
        self.remove_key_files()

        args = self._parse_keygen_command(self._key_name)
        keygen.do_keygen(args)

        pubkey, signing_key = _read_signing_keys(self._wif_filename)

        self.assertIsNotNone(pubkey)
        self.assertIsNotNone(signing_key)

    def test_force_write(self):
        """Write key files to be overwritten by test of --force option.
        """
        self.remove_key_files()
        args = self._parse_keygen_command(self._key_name)
        keygen.do_keygen(args)

        args = self._parse_keygen_command('--force', self._key_name)
        keygen.do_keygen(args)

        pubkey, signing_key = _read_signing_keys(self._wif_filename)

        self.assertIsNotNone(pubkey)
        self.assertIsNotNone(signing_key)

    def remove_key_files(self):
        '''Removes the key files.
        '''
        try:
            os.remove(self._wif_filename)
            os.remove(self._addr_filename)
        except FileNotFoundError:
            pass


def _read_signing_keys(key_filename):
    """Reads the given file as a WIF formatted key.

    Args:
        key_filename: The filename where the key is stored.

    Returns:
        tuple (str, str): the public and private key pair

    Raises:
        CliException: If unable to read the file.
    """

    filename = key_filename

    try:
        with open(filename, 'r') as key_file:
            wif_key = key_file.read().strip()
            signing_key = signing.encode_privkey(
                signing.decode_privkey(wif_key, 'wif'), 'hex')
            pubkey = signing.encode_pubkey(
                signing.generate_pubkey(signing_key), 'hex')

            return pubkey, signing_key
    except IOError as e:
        raise CliException('Unable to read key file: {}'.format(str(e)))
