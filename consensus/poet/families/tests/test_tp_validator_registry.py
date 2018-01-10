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

import json
import base64
import hashlib

from sawtooth_processor_test.transaction_processor_test_case \
    import TransactionProcessorTestCase
from validator_reg_message_factory import ValidatorRegistryMessageFactory

from sawtooth_poet_common import sgx_structs
from sawtooth_poet_common.protobuf.validator_registry_pb2 import \
    ValidatorRegistryPayload

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_signing.secp256k1 import Secp256k1PrivateKey


PRIVATE = '2f1e7b7a130d7ba9da0068b3bb0ba1d79e7e77110302c9f746c3c2a63fe40088'


class TestValidatorRegistry(TransactionProcessorTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        context = create_context('secp256k1')
        private_key = Secp256k1PrivateKey.from_hex(PRIVATE)
        signer = CryptoFactory(context).new_signer(private_key)

        cls.factory = ValidatorRegistryMessageFactory(
            signer=signer)

    def _expect_invalid_transaction(self):
        self.validator.expect(
            self.factory.create_tp_response("INVALID_TRANSACTION"))

    def _expect_ok(self):
        self.validator.expect(self.factory.create_tp_response("OK"))

    def _test_valid_signup_info(self, signup_info):
        """
        Testing valid validator_registry transaction.
        """
        payload = ValidatorRegistryPayload(
            verb="reg", name="val_1", id=self.factory.public_key,
            signup_info=signup_info)
        # Send validator registry payload
        transaction_message =\
            self.factory.create_tp_process_request(payload.id, payload)
        transaction_id = transaction_message.signature
        self.validator.send(
            transaction_message)

        # Expect Request for the address for report key PEM
        received = self.validator.expect(
            self.factory.create_get_request_report_key_pem())

        # Respond with simulator report key PEM
        self.validator.respond(
            self.factory.create_get_response_simulator_report_key_pem(),
            received)

        # Expect Request for the address for valid enclave measurements
        received = self.validator.expect(
            self.factory.create_get_request_enclave_measurements())

        # Respond with the simulator valid enclave measurements
        self.validator.respond(
            self.factory.create_get_response_simulator_enclave_measurements(),
            received)

        # Expect Request for the address for valid enclave basenames
        received = self.validator.expect(
            self.factory.create_get_request_enclave_basenames())

        # Respond with the simulator valid enclave basenames
        self.validator.respond(
            self.factory.create_get_response_simulator_enclave_basenames(),
            received)

        # Expect Request for the ValidatorMap
        received = self.validator.expect(
            self.factory.create_get_request_validator_map())

        # Respond with a empty validator Map
        self.validator.respond(
            self.factory.create_get_empty_response_validator_map(), received)

        # Expect a set the new validator to the ValidatorMap
        received = self.validator.expect(
            self.factory.create_set_request_validator_map())

        # Respond with the ValidatorMap address
        self.validator.respond(
            self.factory.create_set_response_validator_map(),
            received)

        # Expect a request to set ValidatorInfo for val_1
        received = self.validator.expect(
            self.factory.create_set_request_validator_info(
                "val_1", transaction_id, signup_info))

        # Respond with address for val_1
        # val_1 address is derived from the validators id
        # val id is the same as the public_key for the factory
        self.validator.respond(
            self.factory.create_set_response_validator_info(),
            received)

        self._expect_ok()

    def test_valid_signup_info(self):
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000")
        self._test_valid_signup_info(signup_info)

        # Re-register the same validator. Expect success.
        self._test_valid_signup_info(signup_info)

    def test_out_of_date_tcb(self):
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000", "OUT_OF_DATE")
        self._test_valid_signup_info(signup_info)

    def test_invalid_name(self):
        """
        Test that a transaction with an invalid name returns an invalid
        transaction.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000")

        # The name is longer the 64 characters
        payload = ValidatorRegistryPayload(
            verb="reg",
            name="val_11111111111111111111111111111111111111111111111111111111"
                 "11111",
            id=self.factory.public_key,
            signup_info=signup_info)

        # Send validator registry payload
        self.validator.send(
            self.factory.create_tp_process_request(payload.id, payload))

        self._expect_invalid_transaction()

    def test_invalid_id(self):
        """
        Test that a transaction with an id that does not match the
        signer_public_key returns an invalid transaction.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000")

        # The idea should match the signer_public_key in the transaction_header
        payload = ValidatorRegistryPayload(
            verb="reg",
            name="val_1",
            id="bad",
            signup_info=signup_info
        )

        # Send validator registry payload
        self.validator.send(
            self.factory.create_tp_process_request(payload.id, payload))

        self._expect_invalid_transaction()

    def test_invalid_poet_public_key(self):
        """
        Test that a transaction without a poet_public_key returns an invalid
        transaction.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000")

        signup_info.poet_public_key = "bad"

        payload = ValidatorRegistryPayload(
            verb="reg",
            name="val_1",
            id=self.factory.public_key,
            signup_info=signup_info)

        # Send validator registry payload
        self.validator.send(
            self.factory.create_tp_process_request(payload.id, payload))

        # Expect Request for the address for report key PEM
        received = self.validator.expect(
            self.factory.create_get_request_report_key_pem())

        # Respond with simulator report key PEM
        self.validator.respond(
            self.factory.create_get_response_simulator_report_key_pem(),
            received)

        # Expect Request for the address for valid enclave measurements
        received = self.validator.expect(
            self.factory.create_get_request_enclave_measurements())

        # Respond with the simulator valid enclave measurements
        self.validator.respond(
            self.factory.create_get_response_simulator_enclave_measurements(),
            received)

        # Expect Request for the address for valid enclave basenames
        received = self.validator.expect(
            self.factory.create_get_request_enclave_basenames())

        # Respond with the simulator valid enclave basenames
        self.validator.respond(
            self.factory.create_get_response_simulator_enclave_basenames(),
            received)

        self._expect_invalid_transaction()

    def _test_bad_signup_info(self, signup_info, expect_config=True):
        payload = ValidatorRegistryPayload(
            verb="reg",
            name="val_1",
            id=self.factory.public_key,
            signup_info=signup_info)

        # Send validator registry payload
        self.validator.send(
            self.factory.create_tp_process_request(payload.id, payload))

        if expect_config:
            # Expect Request for the address for report key PEM
            received = self.validator.expect(
                self.factory.create_get_request_report_key_pem())

            # Respond with simulator report key PEM
            self.validator.respond(
                self.factory.create_get_response_simulator_report_key_pem(),
                received)

            # Expect Request for the address for valid enclave measurements
            received = self.validator.expect(
                self.factory.create_get_request_enclave_measurements())

            # Respond with the simulator valid enclave measurements
            self.validator.respond(
                self.factory.
                create_get_response_simulator_enclave_measurements(),
                received)

            # Expect Request for the address for valid enclave basenames
            received = self.validator.expect(
                self.factory.create_get_request_enclave_basenames())

            # Respond with the simulator valid enclave basenames
            self.validator.respond(
                self.factory.create_get_response_simulator_enclave_basenames(),
                received)

        self._expect_invalid_transaction()

    def test_invalid_verification_report(self):
        """
        Test that a transaction whose verification report is invalid returns
        an invalid transaction.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000")

        # Verification Report is None
        proof_data = signup_info.proof_data
        signup_info.proof_data = json.dumps({})
        self._test_bad_signup_info(signup_info, expect_config=False)

        # ------------------------------------------------------
        # No verification signature
        proof_data_dict = json.loads(proof_data)
        del proof_data_dict["signature"]

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info, expect_config=False)

        # ------------------------------------------------------
        # Bad verification signature
        proof_data_dict["signature"] = "bads"

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # No EPID pseudonym
        proof_data_dict = json.loads(proof_data)
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        del verification_report["epidPseudonym"]

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Altered EPID pseudonym (does not match anti_sybil_id)
        proof_data_dict = json.loads(proof_data)
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        verification_report["epidPseudonym"] = "altered"

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Nonce does not match the one in signup_info
        proof_data_dict = json.loads(proof_data)
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))
        signup_info.nonce = 'a non-matching nonce'

        self._test_bad_signup_info(signup_info)

    def test_invalid_pse_manifest(self):
        """
        Test that a transaction whose pse_manifast is invalid returns an
        invalid transaction.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000")

        proof_data = signup_info.proof_data
        proof_data_dict = json.loads(proof_data)

        # ------------------------------------------------------
        # no pseManifestStatus
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        del verification_report['pseManifestStatus']

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Bad  pseManifestStatus
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        verification_report['pseManifestStatus'] = "bad"

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # No pseManifestHash
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        del verification_report['pseManifestHash']

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Bad pseManifestHash
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        verification_report['pseManifestHash'] = "Bad"

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Missing evidence payload
        evidence_payload = proof_data_dict["evidence_payload"]
        del proof_data_dict["evidence_payload"]

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Missing PSE manifest
        del evidence_payload["pse_manifest"]
        proof_data_dict["evidence_payload"] = evidence_payload

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Bad PSE manifest
        evidence_payload["pse_manifest"] = "bad"

        signup_info.proof_data = json.dumps(proof_data_dict)

        self._test_bad_signup_info(signup_info)

    def test_invalid_enclave_body(self):
        """
        Test that a transaction whose enclave_body is invalid returns an
        invalid transaction.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000")

        proof_data = signup_info.proof_data
        proof_data_dict = json.loads(proof_data)

        # ------------------------------------------------------
        # No isvEnclaveQuoteStatus
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        enclave_status = verification_report["isvEnclaveQuoteStatus"]
        verification_report["isvEnclaveQuoteStatus"] = None

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Bad isvEnclaveQuoteStatus
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        verification_report["isvEnclaveQuoteStatus"] = "Bad"

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # No isvEnclaveQuoteBody
        verification_report = \
            json.loads(proof_data_dict["verification_report"])
        verification_report["isvEnclaveQuoteStatus"] = enclave_status
        verification_report['isvEnclaveQuoteBody'] = None

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Malformed isvEnclaveQuoteBody (decode the enclave quote, chop off
        # the last byte, and re-encode)
        verification_report = \
            json.loads(proof_data_dict["verification_report"])

        verification_report['isvEnclaveQuoteBody'] = \
            base64.b64encode(
                base64.b64decode(
                    verification_report['isvEnclaveQuoteBody'].encode())[1:])\
            .decode()

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Invalid basename
        verification_report = \
            json.loads(proof_data_dict["verification_report"])

        sgx_quote = sgx_structs.SgxQuote()
        sgx_quote.parse_from_bytes(
            base64.b64decode(
                verification_report['isvEnclaveQuoteBody'].encode()))
        sgx_quote.basename.name = \
            b'\xCC' * sgx_structs.SgxBasename.STRUCT_SIZE

        verification_report['isvEnclaveQuoteBody'] = \
            base64.b64encode(sgx_quote.serialize_to_bytes()).decode()

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Report data is not valid (bad OPK hash)
        verification_report = \
            json.loads(proof_data_dict["verification_report"])

        sgx_quote = sgx_structs.SgxQuote()
        sgx_quote.parse_from_bytes(
            base64.b64decode(
                verification_report['isvEnclaveQuoteBody'].encode()))

        hash_input = \
            '{0}{1}'.format(
                'Not a valid OPK Hash',
                self.factory.poet_public_key).upper().encode()
        sgx_quote.report_body.report_data.d = \
            hashlib.sha256(hash_input).digest()

        verification_report['isvEnclaveQuoteBody'] = \
            base64.b64encode(sgx_quote.serialize_to_bytes()).decode()

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Report data is not valid (bad PPK)
        verification_report = \
            json.loads(proof_data_dict["verification_report"])

        sgx_quote = sgx_structs.SgxQuote()
        sgx_quote.parse_from_bytes(
            base64.b64decode(
                verification_report['isvEnclaveQuoteBody'].encode()))

        hash_input = \
            '{0}{1}'.format(
                self.factory.public_key_hash,
                "Not a valid PPK").encode()
        sgx_quote.report_body.report_data.d = \
            hashlib.sha256(hash_input).digest()

        verification_report['isvEnclaveQuoteBody'] = \
            base64.b64encode(sgx_quote.serialize_to_bytes()).decode()

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

        # ------------------------------------------------------
        # Invalid enclave measurement
        verification_report = \
            json.loads(proof_data_dict["verification_report"])

        sgx_quote = sgx_structs.SgxQuote()
        sgx_quote.parse_from_bytes(
            base64.b64decode(
                verification_report['isvEnclaveQuoteBody'].encode()))
        sgx_quote.report_body.mr_enclave.m = \
            b'\xCC' * sgx_structs.SgxMeasurement.STRUCT_SIZE

        verification_report['isvEnclaveQuoteBody'] = \
            base64.b64encode(sgx_quote.serialize_to_bytes()).decode()

        signup_info.proof_data = \
            self.factory.create_proof_data(
                verification_report=verification_report,
                evidence_payload=proof_data_dict.get('evidence_payload'))

        self._test_bad_signup_info(signup_info)

    def test_missing_report_key_pem(self):
        """
        Testing validator registry unable to retrieve the report public key
        PEM from the config setting.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000")

        payload = ValidatorRegistryPayload(
            verb="reg", name="val_1", id=self.factory.public_key,
            signup_info=signup_info)

        # Send validator registry payload
        self.validator.send(
            self.factory.create_tp_process_request(payload.id, payload))

        # Expect Request for the address for report key PEM
        received = self.validator.expect(
            self.factory.create_get_request_report_key_pem())

        # Respond with empty report key PEM
        self.validator.respond(
            self.factory.create_get_response_report_key_pem(),
            received)

        # Expect that the transaction will be rejected
        self._expect_invalid_transaction()

    def test_invalid_report_key_pem(self):
        """
        Testing validator registry unable to succcessfully parse the report
        public key PEM from the config setting.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000")

        payload = ValidatorRegistryPayload(
            verb="reg", name="val_1", id=self.factory.public_key,
            signup_info=signup_info)

        # Send validator registry payload
        self.validator.send(
            self.factory.create_tp_process_request(payload.id, payload))

        # Expect Request for the address for report key PEM
        received = self.validator.expect(
            self.factory.create_get_request_report_key_pem())

        # Respond with empty report key PEM
        self.validator.respond(
            self.factory.create_get_response_report_key_pem(pem='invalid'),
            received)

        # Expect that the transaction will be rejected
        self._expect_invalid_transaction()

    def test_missing_enclave_measurements(self):
        """
        Testing validator registry unable to retrieve the valid enclave
        measurements from the config setting.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000")

        payload = ValidatorRegistryPayload(
            verb="reg", name="val_1", id=self.factory.public_key,
            signup_info=signup_info)

        # Send validator registry payload
        self.validator.send(
            self.factory.create_tp_process_request(payload.id, payload))

        # Expect Request for the address for report key PEM
        received = self.validator.expect(
            self.factory.create_get_request_report_key_pem())

        # Respond with the simulator report key PEM
        self.validator.respond(
            self.factory.create_get_response_simulator_report_key_pem(),
            received)

        # Expect Request for the address for valid enclave measurements
        received = self.validator.expect(
            self.factory.create_get_request_enclave_measurements())

        # Respond with empty valid enclave measurements
        self.validator.respond(
            self.factory.create_get_response_enclave_measurements(),
            received)

        # Expect that the transaction will be rejected
        self._expect_invalid_transaction()

    def test_invalid_enclave_measurements(self):
        """
        Testing validator registry unable to successfully parse the valid
        enclave measurements from the config setting.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000")

        payload = ValidatorRegistryPayload(
            verb="reg", name="val_1", id=self.factory.public_key,
            signup_info=signup_info)

        # Send validator registry payload
        self.validator.send(
            self.factory.create_tp_process_request(payload.id, payload))

        # Expect Request for the address for report key PEM
        received = self.validator.expect(
            self.factory.create_get_request_report_key_pem())

        # Respond with the simulator report key PEM
        self.validator.respond(
            self.factory.create_get_response_simulator_report_key_pem(),
            received)

        # Expect Request for the address for valid enclave measurements
        received = self.validator.expect(
            self.factory.create_get_request_enclave_measurements())

        # Respond with invalid valid enclave measurements
        self.validator.respond(
            self.factory.create_get_response_enclave_measurements(
                measurements='invalid'),
            received)

        # Expect that the transaction will be rejected
        self._expect_invalid_transaction()

    def test_missing_enclave_basenames(self):
        """
        Testing validator registry unable to retrieve the valid enclave
        basenames from the config setting.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000")

        payload = ValidatorRegistryPayload(
            verb="reg", name="val_1", id=self.factory.public_key,
            signup_info=signup_info)

        # Send validator registry payload
        self.validator.send(
            self.factory.create_tp_process_request(payload.id, payload))

        # Expect Request for the address for report key PEM
        received = self.validator.expect(
            self.factory.create_get_request_report_key_pem())

        # Respond with the simulator report key PEM
        self.validator.respond(
            self.factory.create_get_response_simulator_report_key_pem(),
            received)

        # Expect Request for the address for valid enclave measurements
        received = self.validator.expect(
            self.factory.create_get_request_enclave_measurements())

        # Respond with simulator valid enclave measurements
        self.validator.respond(
            self.factory.create_get_response_simulator_enclave_measurements(),
            received)

        # Expect Request for the address for valid enclave basenames
        received = self.validator.expect(
            self.factory.create_get_request_enclave_basenames())

        # Respond with empty enclave basenames
        self.validator.respond(
            self.factory.create_get_response_enclave_basenames(),
            received)

        # Expect that the transaction will be rejected
        self._expect_invalid_transaction()

    def test_invalid_enclave_basenames(self):
        """
        Testing validator registry unable to successfully parse the valid
        enclave basenames from the config setting.
        """
        signup_info = self.factory.create_signup_info(
            self.factory.public_key_hash, "000")

        payload = ValidatorRegistryPayload(
            verb="reg", name="val_1", id=self.factory.public_key,
            signup_info=signup_info)

        # Send validator registry payload
        self.validator.send(
            self.factory.create_tp_process_request(payload.id, payload))

        # Expect Request for the address for report key PEM
        received = self.validator.expect(
            self.factory.create_get_request_report_key_pem())

        # Respond with the simulator report key PEM
        self.validator.respond(
            self.factory.create_get_response_simulator_report_key_pem(),
            received)

        # Expect Request for the address for valid enclave measurements
        received = self.validator.expect(
            self.factory.create_get_request_enclave_measurements())

        # Respond with simulator valid enclave measurements
        self.validator.respond(
            self.factory.create_get_response_simulator_enclave_measurements(),
            received)

        # Expect Request for the address for valid enclave basenames
        received = self.validator.expect(
            self.factory.create_get_request_enclave_basenames())

        # Respond with empty enclave basenames
        self.validator.respond(
            self.factory.create_get_response_enclave_basenames(
                basenames='invalid'),
            received)

        # Expect that the transaction will be rejected
        self._expect_invalid_transaction()
