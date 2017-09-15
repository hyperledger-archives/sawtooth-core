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
from argparse import Namespace
import configparser

import logging
import os
import unittest

import sawtooth_signing.secp256k1_signer as signing

from sawtooth_private_utxo.common.addressing import Addressing
from sawtooth_private_utxo.cli.common import create_client
from sawtooth_private_utxo.cli.common import get_config_file_name
from sawtooth_private_utxo.cli.main import main as cli
from sawtooth_private_utxo.protobuf.utxo_document_pb2 import UtxoDocument


LOGGER = logging.getLogger(__name__)


class TestPrivateUtxoIntegration(unittest.TestCase):
    """ Tests that the Private UTXO CLI generates the correct parameters to be
    passed to the PrivateUtxoClient.
    """

    def setUp(self):
        self._configs = {}
        self._public_keys = {}
        self._private_keys = {}

        # create a valid configuration for the tests
        cli('private_utxo', ['reset',
                             '--user', 'alice'])
        cli('private_utxo', ['init',
                             '--user', 'alice',
                             '--url', 'rest-api:8080'])
        cli('private_utxo', ['reset',
                             '--user', 'bob'])
        cli('private_utxo', ['init',
                             '--user', 'bob',
                             '--url', 'rest-api:8080'])

        self.load_public_key('alice')
        self.load_public_key('bob')

    def cli(self, args):
        ret = cli('private_utxo', args)
        if ret != 0:
            raise RuntimeError("Command failed: %s", args)

    def load_public_key(self, user):
        arguments = Namespace(user=user)
        config_file = get_config_file_name(arguments)
        config = configparser.ConfigParser()
        config.read(config_file)
        key_file = config.get('DEFAULT', 'key_file')
        self._configs[user] = config

        with open(key_file) as fd:
            self._private_keys[user] = fd.read().strip()

        self._public_keys[user] = signing.generate_pubkey(
            self._private_keys[user])

    def test_cli_tp_integration(self):

        try:
            client = create_client(self._configs['alice'])

            # issue asset
            asset_name = "test asset"
            asset_nonce = 'nonce'
            utxo_filename = 'utxo'
            alice_public_key = self._public_keys['alice']
            bob_public_key = self._public_keys['bob']
            self.cli(
                ['issue_asset',
                 '--user', 'alice',
                 '--name', asset_name,
                 '--amount', '100',
                 '--nonce', asset_nonce,
                 '--wait'])

            asset_address = Addressing.asset_type_address(
                alice_public_key, asset_name, asset_nonce)

            asset_type = client.asset_type_get(asset_address)
            LOGGER.debug("AssetType: %s", asset_type)
            self.assertTrue(asset_type is not None)

            # transfer asset
            self.cli(
                ['transfer_asset',
                 '--user', 'alice',
                 '--type', asset_address,
                 '--amount', '1',
                 '--recipient', bob_public_key,
                 '--wait'])

            alice_holdings = client.get_asset_holdings(alice_public_key,
                                                       asset_address)
            LOGGER.info("alice_holdings: %s", alice_holdings)
            self.assertIsNotNone(alice_holdings)
            self.assertEqual(alice_holdings.amount, 99)

            bob_holdings = client.get_asset_holdings(bob_public_key,
                                                     asset_address)
            LOGGER.info("bob_holdings: %s", bob_holdings)
            self.assertIsNotNone(bob_holdings)
            self.assertEqual(bob_holdings.amount, 1)

            # convert asset to utxo
            self.cli(
                ['convert_to_utxo',
                 '--user', 'alice',
                 '--type', asset_address,
                 '--amount', '1',
                 '--utxo-document', utxo_filename,
                 '--wait'])

            alice_holdings = client.get_asset_holdings(alice_public_key,
                                                       asset_address)
            self.assertIsNotNone(alice_holdings)
            self.assertEqual(alice_holdings.amount, 98)
            LOGGER.info("alice_holdings %s", alice_holdings)

            uxto_document = UtxoDocument()
            with open(utxo_filename, "rb") as in_file:
                uxto_document.ParseFromString(in_file.read())

            LOGGER.info("alice uxto_document %s", uxto_document)

            # transfer utxo
            self.cli(
                ['transfer_utxo',
                 '--user', 'alice',
                 '--input', utxo_filename,
                 '--recipient', "{}:{}".format(bob_public_key, 1),
                 '--wait'])

            uxto_document = UtxoDocument()
            utxo_filename_2 = "{}.utxo".format(bob_public_key)
            with open(utxo_filename_2, "rb") as in_file:
                uxto_document.ParseFromString(in_file.read())
            LOGGER.info("bob uxto_document %s", utxo_filename_2)

            # convert from utxo
            self.cli(
                ['convert_from_utxo',
                 '--user', 'bob',
                 '--utxo-document', utxo_filename,
                 '--wait'])

            bob_holdings = client.get_asset_holdings(bob_public_key,
                                                     asset_address)
            LOGGER.info("bob_holdings: %s", bob_holdings)
            self.assertIsNotNone(bob_holdings)
            self.assertEqual(bob_holdings.amount, 2)
        finally:
            if os.path.exists(utxo_filename):
                os.remove(utxo_filename)
            if os.path.exists(utxo_filename_2):
                os.remove(utxo_filename_2)
