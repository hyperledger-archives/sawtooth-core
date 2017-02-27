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

from sawtooth_signing import secp256k1_signer as signing

from sawtooth_processor_test.message_factory import MessageFactory
from sawtooth_poet.protobuf.validator_registry_pb2 import \
    ValidatorInfo
from sawtooth_poet.protobuf.validator_registry_pb2 import \
    SignUpInfo
from sawtooth_poet.protobuf.validator_registry_pb2 import \
    ValidatorMap


class ValidatorRegistryMessageFactory(object):
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

    # Currently this is done in the enclave
    def create_signup_info(self, originator_public_key_hash,
                           most_recent_wait_certificate_id):
        # First we need to create a public/private key pair for the PoET
        # enclave to use.
        _poet_private_key = \
            "1f70fa2518077ad18483f48e77882d11983b537fa5f7cf158684d2c670fe4f1f"
        _poet_public_key = \
            signing.generate_pubkey(_poet_private_key)
        # currently not used
        # _active_wait_timer = None

        _report_private_key = \
            signing.encode_privkey(
                signing.decode_privkey(
                    '5Jz5Kaiy3kCiHE537uXcQnJuiNJshf2bZZn43CrALMGoCd3zRuo',
                    'wif'), 'hex')

        # We are going to fake out the sealing the signup data.
        signup_data = {
            'poet_public_key':
                signing.encode_pubkey(_poet_public_key, 'hex'),
            'poet_private_key':
                signing.encode_privkey(
                    _poet_private_key,
                    'hex')
        }

        # Create a fake report
        report_data = '{0}{1}'.format(
            originator_public_key_hash.upper(),
            signing.encode_pubkey(
                _poet_public_key,
                'hex').upper()
        )
        quote = {
            'report_body': hashlib.sha256(
                json.dumps(report_data).encode()).hexdigest()
        }

        # Fake our "proof" data.
        verification_report = {
            'id': base64.b64encode(
                bytes(hashlib.sha256(b'2017-02-16T15:21:24.437048')
                      .hexdigest().encode())).decode(),
            'isvEnclaveQuoteStatus': 'OK',
            'isvEnclaveQuoteBody':
                base64.b64encode(
                    json.dumps(quote).encode()).decode(),
            'pseManifestStatus': 'OK',
            'pseManifestHash':
                base64.b64encode(
                    hashlib.sha256(
                        bytes(b'Do you believe in '
                              b'manifest destiny?')).hexdigest()
                    .encode()).decode(),
            'nonce': most_recent_wait_certificate_id
        }

        proof_data_dict = {
            'verification_report': json.dumps(verification_report),
            'signature':
                signing.sign(
                    json.dumps(verification_report),
                    _report_private_key)
        }
        proof_data = json.dumps(proof_data_dict)

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
            payload.SerializeToString(), inputs, outputs, [])

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
            block_num=0
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
            block_num=0
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
