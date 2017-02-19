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

import unittest
import json
import base64

from sawtooth_signing import pbct as signing
from validator_registry_test.validator_reg_message_factory \
    import ValidatorRegistryMessageFactory
from sawtooth_poet.protobuf.validator_registry_pb2 import \
    ValidatorRegistryPayload


class TestValidatorRegistry(unittest.TestCase):
    """
    Set of tests to run in a test suite with an existing TPTester and
    transaction processor.
    """

    def __init__(self, test_name, tester):
        super().__init__(test_name)
        self.tester = tester
        self.private_key = signing.generate_privkey()
        self.public_key = signing.encode_pubkey(
            signing.generate_pubkey(self.private_key), "hex")
        self.factory = ValidatorRegistryMessageFactory(
            private=self.private_key, public=self.public_key)
        self._report_private_key = \
            signing.encode_privkey(
                signing.decode_privkey(
                    '5Jz5Kaiy3kCiHE537uXcQnJuiNJshf2bZZn43CrALMGoCd3zRuo',
                    'wif'), 'hex')

    def _expect_invalid_transaction(self):
        self.tester.expect(
            self.factory.create_tp_response("INVALID_TRANSACTION"))

    def _expect_ok(self):
        self.tester.expect(self.factory.create_tp_response("OK"))

    def test_valid_signup_info(self):
        """
        Testing valid validator_registry transaction. This includes sending new
        signup info for a validator that has already been registered.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.pubkey_hash, "000")

        payload = ValidatorRegistryPayload(
            verb="reg", name="val_1", id=self.factory.public_key,
            signup_info=signup_info, block_num=0)

        # Send validator registry paylaod
        self.tester.send(
            self.factory.create_tp_process_request(payload.id, payload))

        # Expect Request for the ValidatorMap
        received = self.tester.expect(
            self.factory.create_get_request_validator_map())

        # Respond with a empty validator Map
        self.tester.respond(
            self.factory.create_get_empty_resposne_validator_map(), received)

        # Expect a set the new validator to the ValidatorMap
        received = self.tester.expect(
            self.factory.create_set_request_validator_map())

        # Respond with the ValidatorMap address
        self.tester.respond(self.factory.create_set_response_validator_map(),
                            received)

        # Expect a request to set ValidatorInfo for val_1
        received = self.tester.expect(
            self.factory.create_set_request_validator_info("val_1",
                                                           "registered"))

        # Respond with address for val_1
        # val_1 address is derived from the validators id
        # val id is the same as the pubkey for the factory
        self.tester.respond(self.factory.create_set_response_validator_info(),
                            received)

        self._expect_ok()
        # --------------------------
        signup_info = self.factory.create_signup_info(
            self.factory.pubkey_hash, "000")

        payload = ValidatorRegistryPayload(
            verb="reg", name="val_1", id=self.factory.public_key,
            signup_info=signup_info, block_num=0)

        # Send validator registry paylaod
        self.tester.send(
            self.factory.create_tp_process_request(payload.id, payload))

        # Expect Request for the ValidatorMap
        received = self.tester.expect(
            self.factory.create_get_request_validator_map())

        # Respond with a validator Map
        self.tester.respond(self.factory.create_get_response_validator_map(),
                            received)
        # Expect to receive a validator_info request
        received = self.tester.expect(
            self.factory.create_get_request_validator_info())

        # Respond with the ValidatorInfo
        self.tester.respond(
            self.factory.create_get_response_validator_info("val_1"), received)

        # Expect a request to set ValidatorInfo for val_1
        received = self.tester.expect(
            self.factory.create_set_request_validator_info("val_1", "revoked"))

        # Respond with address for val_1
        # val_1 address is derived from the validators id
        # val id is the same as the pubkey for the factory
        self.tester.respond(
            self.factory.create_set_response_validator_info(), received)

        # Expect a request to set ValidatorInfo for val_1
        received = self.tester.expect(
            self.factory.create_set_request_validator_info("val_1",
                                                           "registered"))

        # Respond with address for val_1
        # val_1 address is derived from the validators id
        # val id is the same as the pubkey for the factory
        self.tester.respond(self.factory.create_set_response_validator_info(),
                            received)

        self._expect_ok()

    def test_invalid_name(self):
        """
        Test that a transaction with an invalid name returns an invalid
        transaction.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.pubkey_hash, "000")

        # The name is longer the 64 characters
        payload = ValidatorRegistryPayload(
            verb="reg",
            name="val_11111111111111111111111111111111111111111111111111111111"
                 "11111",
            id=self.factory.public_key,
            signup_info=signup_info,
            block_num=0)

        # Send validator registry paylaod
        self.tester.send(
            self.factory.create_tp_process_request(payload.id, payload))

        self._expect_invalid_transaction()

    def test_invalid_id(self):
        """
        Test that a transaction with an id that does not match the
        signer_pubkey returns an invalid transaction.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.pubkey_hash, "000")

        # The idea should match the signer_pubkey in the transaction_header
        payload = ValidatorRegistryPayload(
            verb="reg",
            name="val_1",
            id="bad",
            signup_info=signup_info,
            block_num=0)

        # Send validator registry paylaod
        self.tester.send(
            self.factory.create_tp_process_request(payload.id, payload))

        self._expect_invalid_transaction()

    def test_invalid_poet_pubkey(self):
        """
        Test that a transaction without a poet_public_key returns an invalid
        transaction.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.pubkey_hash, "000")

        signup_info.poet_public_key = "bad"

        payload = ValidatorRegistryPayload(
            verb="reg",
            name="val_1",
            id=self.factory.public_key,
            signup_info=signup_info,
            block_num=0)

        # Send validator registry paylaod
        self.tester.send(
            self.factory.create_tp_process_request(payload.id, payload))

        self._expect_invalid_transaction()

    def _test_bad_signup_info(self, signup_info):
        payload = ValidatorRegistryPayload(
            verb="reg",
            name="val_1",
            id=self.factory.public_key,
            signup_info=signup_info,
            block_num=0)

        # Send validator registry paylaod
        self.tester.send(
            self.factory.create_tp_process_request(payload.id, payload))
        self._expect_invalid_transaction()

    def test_invalid_verfication_report(self):
        """
        Test that a transaction whose verication report is invalid returns an
        invalid transaction.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.pubkey_hash, "000")

        # Verifcation Report is None
        proof_data = signup_info.proof_data
        signup_info.proof_data = json.dumps({})
        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # No verification signature
        proof_data_dict = json.loads(proof_data)
        del proof_data_dict["signature"]

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Bad verification signature
        proof_data_dict["signature"] = "bads"

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # No Nonce
        verification_report = \
            json.loads(proof_data_dict["verification_report"])

        verification_report["nonce"] = None
        proof_data_dict = {
            'verification_report': json.dumps(verification_report),
            'signature':
                signing.sign(
                    json.dumps(verification_report),
                    self._report_private_key)
        }

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

    def test_invalid_pse_manifest(self):
        """
        Test that a transaction whose pse_manifast is invalid returns an
        invalid transaction.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.pubkey_hash, "000")

        proof_data = signup_info.proof_data
        proof_data_dict = json.loads(proof_data)

        # ------------------------------------------------------
        # no pseManifestStatus
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        pse_status = verification_report['pseManifestStatus']
        verification_report['pseManifestStatus'] = None
        proof_data_dict = {
            'verification_report': json.dumps(verification_report),
            'signature':
                signing.sign(
                    json.dumps(verification_report),
                    self._report_private_key)
        }

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Bad  pseManifestStatus
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        verification_report['pseManifestStatus'] = "bad"
        proof_data_dict = {
            'verification_report': json.dumps(verification_report),
            'signature':
                signing.sign(
                    json.dumps(verification_report),
                    self._report_private_key)
        }

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # No pseManifestHash
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        verification_report['pseManifestStatus'] = pse_status
        verification_report['pseManifestHash'] = None
        proof_data_dict = {
            'verification_report': json.dumps(verification_report),
            'signature':
                signing.sign(
                    json.dumps(verification_report),
                    self._report_private_key)
        }

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Bad pseManifestHash
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        verification_report['pseManifestHash'] = "Bad"
        proof_data_dict = {
            'verification_report': json.dumps(verification_report),
            'signature':
                signing.sign(
                    json.dumps(verification_report),
                    self._report_private_key)
        }

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

    def test_invalid_envalve_body(self):
        """
        Test that a transaction whose enclave_body is invalid returns an
        invalid transaction.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.pubkey_hash, "000")

        proof_data = signup_info.proof_data
        proof_data_dict = json.loads(proof_data)

        # ------------------------------------------------------
        # No isvEnclaveQuoteStatus
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        enclave_status = verification_report["isvEnclaveQuoteStatus"]
        verification_report["isvEnclaveQuoteStatus"] = None
        proof_data_dict = {
            'verification_report': json.dumps(verification_report),
            'signature':
                signing.sign(
                    json.dumps(verification_report),
                    self._report_private_key)
        }

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # No isvEnclaveQuoteStatus
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        verification_report["isvEnclaveQuoteStatus"] = "Bad"
        proof_data_dict = {
            'verification_report': json.dumps(verification_report),
            'signature':
                signing.sign(
                    json.dumps(verification_report),
                    self._report_private_key)
        }

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # No isvEnclaveQuoteBody
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        verification_report["isvEnclaveQuoteStatus"] = enclave_status
        verification_report['isvEnclaveQuoteBody'] = None
        proof_data_dict = {
            'verification_report': json.dumps(verification_report),
            'signature':
                signing.sign(
                    json.dumps(verification_report),
                    self._report_private_key)
        }

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # No report body in isvEnclaveQuoteBody
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        quote = {"test": "none"}

        verification_report['isvEnclaveQuoteBody'] = \
            base64.b64encode(
                json.dumps(quote).encode()).decode()

        proof_data_dict = {
            'verification_report': json.dumps(verification_report),
            'signature':
                signing.sign(
                    json.dumps(verification_report),
                    self._report_private_key)
        }

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Bad isvEnclaveQuoteBody
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        quote = {"report_body": "none"}

        verification_report['isvEnclaveQuoteBody'] = \
            base64.b64encode(
                json.dumps(quote).encode()).decode()

        proof_data_dict = {
            'verification_report': json.dumps(verification_report),
            'signature':
                signing.sign(
                    json.dumps(verification_report),
                    self._report_private_key)
        }

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)
