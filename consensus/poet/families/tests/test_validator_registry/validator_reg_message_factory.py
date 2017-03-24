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
import base64
import json
import hashlib

from collections import OrderedDict

from cryptography.hazmat import backends
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

import sawtooth_signing as signing

from sawtooth_processor_test.message_factory import MessageFactory

from sawtooth_poet_common import sgx_structs
from sawtooth_poet_common.protobuf.validator_registry_pb2 import \
    ValidatorInfo
from sawtooth_poet_common.protobuf.validator_registry_pb2 import \
    SignUpInfo
from sawtooth_poet_common.protobuf.validator_registry_pb2 import \
    ValidatorMap


class ValidatorRegistryMessageFactory(object):
    # The basename and enclave measurement values we will put into the enclave
    # quote in the attestation verification report.
    __VALID_BASENAME__ = \
        bytes.fromhex(
            'b785c58b77152cbe7fd55ee3851c4990'
            '00000000000000000000000000000000')
    __VALID_ENCLAVE_MEASUREMENT__ = \
        bytes.fromhex(
            'c99f21955e38dbb03d2ca838d3af6e43'
            'ef438926ed02db4cc729380c8c7a174e')

    __REPORT_PRIVATE_KEY_PEM__ = \
        '-----BEGIN PRIVATE KEY-----\n' \
        'MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCsy/NmLwZP6Uj0\n' \
        'p5mIiefgK8VOK7KJ34g3h0/X6aFOd/Ff4j+e23wtQpkxsjVHWLM5SjElGhfpVDhL\n' \
        '1WAMsQI9bpCWR4sjV6p7gOJhv34nkA2Grj5eSHCAJRQXCl+pJ9dYIeKaNoaxkdtq\n' \
        '+Xme//ohtkkv/ZjMTfsjMl0RLXokJ+YhSuTpNSovRaCtZfLB5MihVJuV3Qzb2ROh\n' \
        'KQxcuyPy9tBtOIrBWJaFiXOLRxAijs+ICyzrqUBbRfoAztkljIBx9KNItHiC4zPv\n' \
        'o6DxpGSO2yMQSSrs13PkfyGWVZSgenEYOouEz07X+H5B29PPuW5mCl4nkoH3a9gv\n' \
        'rI6VLEx9AgMBAAECggEAImfFge4RCq4/eX85gcc7pRXyBjuLJAqe+7d0fWAmXxJg\n' \
        'vB+3XTEEi5p8GDoMg7U0kk6kdGe6pRnAz9CffEduU78FCPcbzCCzcD3cVWwkeUok\n' \
        'd1GQV4OC6vD3DBNjsrGdHg45KU18CjUphCZCQhdjvXynG+gZmWxZecuYXkg4zqPT\n' \
        'LwOkcdWBPhJ9CbjtiYOtKDZbhcbdfnb2fkxmvnAoz1OWNfVFXh+x7651FrmL2Pga\n' \
        'xGz5XoxFYYT6DWW1fL6GNuVrd97wkcYUcjazMgunuUMC+6XFxqK+BoqnxeaxnsSt\n' \
        'G2r0sdVaCyK1sU41ftbEQsc5oYeQ3v5frGZL+BgrYQKBgQDgZnjqnVI/B+9iarx1\n' \
        'MjAFyhurcKvFvlBtGKUg9Q62V6wI4VZvPnzA2zEaR1J0cZPB1lCcMsFACpuQF2Mr\n' \
        '3VDyJbnpSG9q05POBtfLjGQdXKtGb8cfXY2SwjzLH/tvxHm3SP+RxvLICQcLX2/y\n' \
        'GTJ+mY9C6Hs6jIVLOnMWkRWamQKBgQDFITE3Qs3Y0ZwkKfGQMKuqJLRw29Tyzw0n\n' \
        'XKaVmO/pEzYcXZMPBrFhGvdmNcJLo2fcsmGZnmit8RP4ChwHUlD11dH1Ffqw9FWc\n' \
        '387i0chlE5FhQPirSM8sWFVmjt2sxC4qFWJoAD/COQtKHgEaVKVc4sH/yRostL1C\n' \
        'r+7aWuqzhQKBgQDcuC5LJr8VPGrbtPz1kY3mw+r/cG2krRNSm6Egj6oO9KFEgtCP\n' \
        'zzjKQU9E985EtsqNKI5VdR7cLRLiYf6r0J6j7zO0IAlnXADP768miUqYDuRw/dUw\n' \
        'JsbwCZneefDI+Mp325d1/egjla2WJCNqUBp4p/Zf62f6KOmbGzzEf6RuUQKBgG2y\n' \
        'E8YRiaTOt5m0MXUwcEZk2Hg5DF31c/dkalqy2UYU57aPJ8djzQ8hR2x8G9ulWaWJ\n' \
        'KiCm8s9gaOFNFt3II785NfWxPmh7/qwmKuUzIdWFNxAsbHQ8NvURTqyccaSzIpFO\n' \
        'hw0inlhBEBQ1cB2r3r06fgQNb2BTT0Itzrd5gkNVAoGBAJcMgeKdBMukT8dKxb4R\n' \
        '1PgQtFlR3COu2+B00pDyUpROFhHYLw/KlUv5TKrH1k3+E0KM+winVUIcZHlmFyuy\n' \
        'Ilquaova1YSFXP5cpD+PKtxRV76Qlqt6o+aPywm81licdOAXotT4JyJhrgz9ISnn\n' \
        'J13KkHoAZ9qd0rX7s37czb3O\n' \
        '-----END PRIVATE KEY-----'

    def __init__(self, private=None, public=None):
        self._factory = MessageFactory(
            encoding="application/protobuf",
            family_name="sawtooth_validator_registry",
            family_version="1.0",
            namespace="6a4372",
            private=private,
            public=public
        )
        self.pubkey_hash = hashlib.sha256(public.encode()).hexdigest()
        self._report_private_key = \
            serialization.load_pem_private_key(
                self.__REPORT_PRIVATE_KEY_PEM__.encode(),
                password=None,
                backend=backends.default_backend())

        # First we need to create a public/private key pair for the PoET
        # enclave to use.
        self._poet_private_key = \
            "1f70fa2518077ad18483f48e77882d11983b537fa5f7cf158684d2c670fe4f1f"
        self.poet_public_key = \
            signing.generate_pubkey(self._poet_private_key)

    @property
    def public_key(self):
        return self._factory.get_public_key()

    def _key_to_address(self, key):
        return self._factory.namespace + \
            self._factory.sha256(key.encode("utf-8"))

    def create_tp_register(self):
        return self._factory.create_tp_register()

    def create_tp_response(self, status):
        return self._factory.create_tp_response(status)

    # Utility function for creating proof data as we need to be
    # able to update signatures when verification report changes
    # Returns a serialized proof data
    def create_proof_data(self, verification_report, evidence_payload):
        verification_report_json = json.dumps(verification_report)
        signature = \
            self._report_private_key.sign(
                verification_report_json.encode(),
                padding.PKCS1v15(),
                hashes.SHA256())
        proof_data_dict = OrderedDict([
            ('evidence_payload', evidence_payload),
            ('verification_report', verification_report_json),
            ('signature', base64.b64encode(signature).decode())]
        )

        return json.dumps(proof_data_dict)

    # Currently this is done in the enclave
    def create_signup_info(self, originator_public_key_hash,
                           most_recent_wait_certificate_id):
        # currently not used
        # _active_wait_timer = None

        # We are going to fake out the sealing the signup data.
        signup_data = {
            'poet_public_key':
                signing.encode_pubkey(self.poet_public_key, 'hex'),
            'poet_private_key':
                signing.encode_privkey(
                    self._poet_private_key,
                    'hex')
        }

        # Build up a fake SGX quote containing:
        # 1. The basename
        # 2. The report body that contains:
        #    a. The enclave measurement
        #    b. The report data SHA256(SHA256(OPK)|PPK)
        sgx_basename = \
            sgx_structs.SgxBasename(name=self.__VALID_BASENAME__)
        sgx_measurement = \
            sgx_structs.SgxMeasurement(
                m=self.__VALID_ENCLAVE_MEASUREMENT__)

        hash_input = \
            '{0}{1}'.format(
                originator_public_key_hash.upper(),
                signing.encode_pubkey(
                    self.poet_public_key,
                    'hex').upper()).encode()
        report_data = hashlib.sha256(hash_input).digest()

        sgx_report_data = sgx_structs.SgxReportData(d=report_data)
        sgx_report_body = \
            sgx_structs.SgxReportBody(
                mr_enclave=sgx_measurement,
                report_data=sgx_report_data)

        sgx_quote = \
            sgx_structs.SgxQuote(
                basename=sgx_basename,
                report_body=sgx_report_body)

        # Create a fake PSE manifest.  A base64 encoding of the
        # originator public key hash should suffice.
        pse_manifest = \
            base64.b64encode(originator_public_key_hash.encode())

        timestamp = '2017-02-16T15:21:24.437048'

        # Fake our "proof" data.
        verification_report = OrderedDict([
            ('epidPseudonym', originator_public_key_hash),
            ('id', base64.b64encode(
                hashlib.sha256(
                    timestamp.encode()).hexdigest().encode()).decode()),
            ('isvEnclaveQuoteStatus', 'OK'),
            ('isvEnclaveQuoteBody',
                base64.b64encode(sgx_quote.serialize_to_bytes()).decode()),
            ('pseManifestStatus', 'OK'),
            ('pseManifestHash',
                base64.b64encode(
                    hashlib.sha256(
                        pse_manifest).hexdigest().encode()).decode()),
            ('nonce', most_recent_wait_certificate_id),
            ('timestamp', timestamp)
        ])

        proof_data = \
            self.create_proof_data(
                verification_report=verification_report,
                evidence_payload={
                    'pse_manifest': pse_manifest.decode()
                })

        return \
            SignUpInfo(
                poet_public_key=signup_data['poet_public_key'],
                proof_data=proof_data,
                anti_sybil_id=originator_public_key_hash)

    def create_tp_process_request(self, validator_id, payload):
        inputs = [
            self._key_to_address('validator_list')
        ]

        outputs = [
            self._key_to_address('validator_list'),
            self._key_to_address(validator_id)
        ]

        return self._factory.create_tp_process_request(
            payload.SerializeToString(), inputs, outputs, [], False)

    def create_get_request_validator_info(self):
        addresses = [self._key_to_address(self.public_key)]
        return self._factory.create_get_request(addresses)

    def create_get_response_validator_info(self, validator_name):
        signup_info = self.create_signup_info(self.pubkey_hash, "000")
        data = ValidatorInfo(
            registered="registered",
            name=validator_name,
            id=self.public_key,
            signup_info=signup_info,
            transaction_id="7a79305e9734fd511386ae877da8770d66c22e4c7b18db8eb2"
                           "ff6ec16f5a3452749ee49a04ea8a805ec5ec8b5d1fdfbcc6f3"
                           "bf6374c99c9a906bc2837d0ad25a"
        ).SerializeToString()

        address = self._key_to_address(self.public_key)
        return self._factory.create_get_response({address: data})

    def create_set_request_validator_info(self, validator_name, reg):
        signup_info = self.create_signup_info(self.pubkey_hash, "000")
        data = ValidatorInfo(
            registered=reg,
            name=validator_name,
            id=self.public_key,
            signup_info=signup_info,
            transaction_id="7a79305e9734fd511386ae877da8770d66c22e4c7b18db8eb2"
                           "ff6ec16f5a3452749ee49a04ea8a805ec5ec8b5d1fdfbcc6f3"
                           "bf6374c99c9a906bc2837d0ad25a"
        ).SerializeToString()

        address = self._key_to_address(self.public_key)
        return self._factory.create_set_request({address: data})

    def create_set_response_validator_info(self):
        addresses = [self._key_to_address(self.public_key)]
        return self._factory.create_set_response(addresses)

    def create_get_request_validator_map(self):
        address = self._key_to_address("validator_map")
        addresses = [address]
        return self._factory.create_get_request(addresses)

    def create_get_empty_resposne_validator_map(self):
        address = self._key_to_address("validator_map")
        data = ValidatorMap().SerializeToString()
        return self._factory.create_get_response({address: data})

    def create_get_response_validator_map(self):
        address = self._key_to_address("validator_map")
        validator_map = ValidatorMap()
        validator_map.entries.add(key=self.pubkey_hash, value=self.public_key)
        data = validator_map.SerializeToString()
        return self._factory.create_get_response({address: data})

    def create_set_request_validator_map(self):
        address = self._key_to_address("validator_map")
        validator_map = ValidatorMap()
        validator_map.entries.add(key=self.pubkey_hash, value=self.public_key)
        data = validator_map.SerializeToString()
        return self._factory.create_set_request({address: data})

    def create_set_response_validator_map(self):
        addresses = [self._key_to_address("validator_map")]
        return self._factory.create_set_response(addresses)
