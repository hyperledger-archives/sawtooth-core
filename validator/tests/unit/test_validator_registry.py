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

import unittest
import hashlib

import pybitcointools

from gossip import signed_object
from journal.object_store import ObjectStore
from journal.consensus.poet1.validator_registry \
    import ValidatorRegistryTransaction
from sawtooth.exceptions import InvalidTransactionError
from journal.consensus.poet1.signup_info import SignupInfo


class TestValidatorRegistryTransaction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from journal.consensus.poet1.poet_enclave_simulator \
            import poet_enclave_simulator
        SignupInfo.poet_enclave = poet_enclave_simulator

        poet_enclave_simulator.initialize(**{'NodeName': "DasValidator"})

    def test_register_validator_valid(self):
        key = signed_object.generate_signing_key()
        public_key_hash = \
            hashlib.sha256(
                pybitcointools.encode_pubkey(
                    pybitcointools.privtopub(key),
                    'hex')).hexdigest()
        validator_id = signed_object.generate_identifier(key)
        name = 'DasValidator'
        signup_info = \
            SignupInfo.create_signup_info(
                originator_public_key_hash=public_key_hash,
                most_recent_wait_certificate_id='0' * 16)

        store = ObjectStore()
        transaction = \
            ValidatorRegistryTransaction.register_validator(
                name,
                validator_id,
                signup_info)
        transaction.sign_object(key)
        try:
            transaction.check_valid(store)
            transaction.apply(store)
        except InvalidTransactionError as e:
            self.fail('Failed valid transaction: {}'.format(e))

    def test_register_validator_re_register(self):
        key = signed_object.generate_signing_key()
        public_key_hash = \
            hashlib.sha256(
                pybitcointools.encode_pubkey(
                    pybitcointools.privtopub(key),
                    'hex')).hexdigest()
        validator_id = signed_object.generate_identifier(key)
        name = 'DasValidator'
        signup_info = \
            SignupInfo.create_signup_info(
                originator_public_key_hash=public_key_hash,
                most_recent_wait_certificate_id='0' * 16)

        store = ObjectStore()
        transaction = \
            ValidatorRegistryTransaction.register_validator(
                name,
                validator_id,
                signup_info)
        transaction.sign_object(key)
        try:
            transaction.check_valid(store)
            transaction.apply(store)
        except InvalidTransactionError as e:
            self.fail('Failed valid transaction: {}'.format(e))
        try:  # check if valid to register again
            transaction.check_valid(store)
        except InvalidTransactionError as e:
            self.fail('Failure: Double registered validator: {}'.format(e))

    def test_register_validator_key_mismatch(self):
        key = signed_object.generate_signing_key()
        public_key_hash = \
            hashlib.sha256(
                pybitcointools.encode_pubkey(
                    pybitcointools.privtopub(key),
                    'hex')).hexdigest()
        key2 = signed_object.generate_signing_key()
        validator_id = signed_object.generate_identifier(key)
        name = 'DasValidator'
        signup_info = \
            SignupInfo.create_signup_info(
                originator_public_key_hash=public_key_hash,
                most_recent_wait_certificate_id='0' * 16)

        store = ObjectStore()
        transaction = \
            ValidatorRegistryTransaction.register_validator(
                name,
                validator_id,
                signup_info)
        transaction.sign_object(key2)
        with self.assertRaises(InvalidTransactionError):
            transaction.check_valid(store)
            self.fail("Failure: Verified an invalid transaction")
