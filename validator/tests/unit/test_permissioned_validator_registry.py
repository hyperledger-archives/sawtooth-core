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

import json
import unittest

import pybitcointools

from gossip import signed_object
from journal.object_store import ObjectStore
from sawtooth_validator.consensus.poet1 import permissioned_validator_registry
from sawtooth_validator.consensus.poet1.permissioned_validator_registry \
    import PermissionedValidatorRegistryTransaction
from sawtooth.exceptions import InvalidTransactionError


class TestPermissionedValidatorRegistryTransaction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            with open('./etc/permissioned-validators.json') \
                    as whitelist_fd:
                permissioned_validators = json.load(whitelist_fd)
        except IOError, ex:
            raise Exception('IOError: {}'.format(str(ex)))

        whitelist = \
            permissioned_validators["WhitelistOfPermissionedValidators"]
        permissioned_validator_registry.\
            set_global_permissioned_validators(whitelist)

    def test_register_permissioned_validator_valid(self):
        signing_key = signed_object.generate_signing_key()

        try:
            priv_key1 = pybitcointools.decode_privkey(
                open('./tests/unit/keys/pv1.wif', "r")
                .read().strip(), 'wif')
            priv_key2 = pybitcointools.decode_privkey(
                open('./tests/unit/keys/pv2.wif', "r")
                .read().strip(), 'wif')
        except IOError as ex:
            raise Exception('IOError: {}'.format(str(ex)))

        pub_key1 = pybitcointools.encode_pubkey(
            pybitcointools.privtopub(priv_key1), 'hex')
        pub_key2 = pybitcointools.encode_pubkey(
            pybitcointools.privtopub(priv_key2), 'hex')
        permissioned_public_keys = [pub_key1, pub_key2]

        addr1 = signed_object.generate_identifier(priv_key1)
        addr2 = signed_object.generate_identifier(priv_key2)
        permissioned_addrs = [addr1, addr2]

        update = {
            'whitelist_name': "hyperledger.sawtooth-core.genesis-whitelist",
            'verb': 'reg',
            'permissioned_public_keys': permissioned_public_keys,
            'permissioned_addrs': permissioned_addrs
        }
        minfo = {'Update': update}
        transaction = PermissionedValidatorRegistryTransaction(minfo)
        transaction.sign_object(signing_key)

        store = ObjectStore()
        try:
            transaction.check_valid(store)
            transaction.apply(store)
        except InvalidTransactionError as e:
            self.fail('Failed valid transaction: {}'.format(e))

    def test_register_permissioned_validator_invalid(self):
        signing_key = signed_object.generate_signing_key()

        unpermissiond_private_key = signed_object.generate_signing_key()
        pub_key = pybitcointools.encode_pubkey(
            pybitcointools.privtopub(unpermissiond_private_key), 'hex')
        permissioned_public_keys = [pub_key]

        addr = signed_object.generate_identifier(unpermissiond_private_key)
        permissioned_addrs = [addr]

        update = {
            'whitelist_name': "hyperledger.sawtooth-core.genesis-whitelist",
            'verb': 'reg',
            'permissioned_public_keys': permissioned_public_keys,
            'permissioned_addrs': permissioned_addrs
        }
        minfo = {'Update': update}

        transaction = PermissionedValidatorRegistryTransaction(minfo)
        transaction.sign_object(signing_key)

        store = ObjectStore()
        with self.assertRaises(InvalidTransactionError):
            transaction.check_valid(store)
            self.fail("Failure: Verified an invalid transaction")
