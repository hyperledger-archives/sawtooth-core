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

from gossip import signed_object
from gossip.common import dict2json
from journal.global_store_manager import KeyValueStore

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

    def test_register_validator_valid(self):
        key = signed_object.generate_signing_key()
        validator_id = signed_object.generate_identifier(key)
        name = 'DasValidator'
        signup_info = dict2json({'poet_public_key': 'fake_key',
                                 'anti_sybil_id': 'some_token',
                                 'proof_data': 'proof'})
        store = KeyValueStore()
        transaction = ValidatorRegistryTransaction.register_validator(
            name, validator_id, signup_info)
        transaction.sign_object(key)
        try:
            transaction.check_valid(store)
            transaction.apply(store)
        except InvalidTransactionError:
            self.fail("Bad: Failed valid transaction")

    def test_register_validator_re_register(self):
        key = signed_object.generate_signing_key()
        validator_id = signed_object.generate_identifier(key)
        name = 'DasValidator'
        signup_info = dict2json({'poet_public_key': 'fake_key',
                                 'anti_sybil_id': 'some_token',
                                 'proof_data': 'proof'})
        store = KeyValueStore()
        transaction = ValidatorRegistryTransaction.register_validator(
            name, validator_id, signup_info)
        transaction.sign_object(key)
        try:
            transaction.check_valid(store)
            transaction.apply(store)
        except InvalidTransactionError:
            self.fail("Failure: Failed valid transaction")
        try:  # check if valid to register again
            transaction.check_valid(store)
        except InvalidTransactionError:
            self.fail("Failure: Double registered validator.")

    def test_register_validator_key_mismatch(self):
        key = signed_object.generate_signing_key()
        key2 = signed_object.generate_signing_key()
        validator_id = signed_object.generate_identifier(key)
        name = 'DasValidator'
        signup_info = dict2json({'poet_public_key': 'fake_key',
                                 'anti_sybil_id': 'some_token',
                                 'proof_data': 'proof'})
        store = KeyValueStore()
        transaction = ValidatorRegistryTransaction.register_validator(
            name, validator_id, signup_info)
        transaction.sign_object(key2)
        with self.assertRaises(InvalidTransactionError):
            transaction.check_valid(store)
            transaction.apply(store)
            self.fail("Failure: Verified an invalid transaction")
