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
import hashlib
import base64
import json

from sawtooth_signing import secp256k1_signer as signing

from sawtooth_sdk.processor.state import StateEntry
from sawtooth_sdk.client.future import FutureTimeoutError
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_poet.protobuf.validator_registry_pb2 import \
    ValidatorInfo
from sawtooth_poet.protobuf.validator_registry_pb2 import \
    ValidatorMap
from sawtooth_poet.protobuf.validator_registry_pb2 import \
    ValidatorRegistryPayload

LOGGER = logging.getLogger(__name__)

STATE_TIMEOUT_SEC = 10
VAL_REG_NAMESPACE = \
    hashlib.sha256("validator_registry".encode()).hexdigest()[0:6]


def _get_address(key):
    address = VAL_REG_NAMESPACE + hashlib.sha256(key.encode()).hexdigest()
    return address


def _get_validator_state(state, validator_id=None):
    if validator_id is None:
        address = _get_address('validator_map')
        validator_state = ValidatorMap()
    else:
        validator_state = ValidatorInfo()
        address = _get_address(validator_id)
    try:
        entries_list = state.get([address], timeout=STATE_TIMEOUT_SEC)
    except FutureTimeoutError:
        LOGGER.warning('Timeout occured on state.get([%s])', address)
        raise InternalError('Unable to get {}'.format(address))

    if len(entries_list) != 0:
        validator_state.ParseFromString(entries_list[0].data)

    return validator_state


def _update_validator_state(state,
                            validator_id,
                            anti_sybil_id,
                            validator_info):

    validator_map = _get_validator_state(state)
    add_to_map = True
    for entry in validator_map.entries:
        if anti_sybil_id == entry.key:
            # The validator's old signup info is stale and needs to be revoked
            revoked_info = _get_validator_state(state, entry.value)

            revoked_info.registered = "revoked"
            revoked_info = revoked_info.SerializeToString()
            address = _get_address(validator_id)
            _set_data(state, address, revoked_info)
            add_to_map = False
            break

    # This is a new validator that needs to be added to the map
    if add_to_map:
        validator_map.entries.add(key=anti_sybil_id, value=validator_id)
        address_map = _get_address('validator_map')
        _set_data(state, address_map, validator_map.SerializeToString())

    address = _get_address(validator_id)
    _set_data(state, address, validator_info)
    LOGGER.info("Validator id %s was added to the validator_map and set.",
                validator_id)


def _set_data(state, address, data):
    try:
        addresses = list(state.set(
            [StateEntry(address=address, data=data)],
            timeout=STATE_TIMEOUT_SEC)
        )

    except FutureTimeoutError:
        LOGGER.warning(
            'Timeout occured on state.set([%s, <value>])', address)
        raise InternalError(
            'Failed to save value on address {}'.format(address))

    if len(addresses) != 1:
        LOGGER.warning(
            'Failed to save value on address %s', address)
        raise InternalError(
            'Failed to save value on address {}'.format(address))


class ValidatorRegistryTransactionHandler(object):

    __REPORT_PRIVATE_KEY_WIF = \
        '5Jz5Kaiy3kCiHE537uXcQnJuiNJshf2bZZn43CrALMGoCd3zRuo'

    def __init__(self):
        # Since signing works with WIF-encoded private keys, we don't have to
        # decode the encoded key string.
        self._report_private_key = self.__REPORT_PRIVATE_KEY_WIF
        self._report_public_key = signing.generate_pubkey(
            self._report_private_key)

    @property
    def family_name(self):
        return 'sawtooth_validator_registry'

    @property
    def family_versions(self):
        return ['1.0']

    @property
    def encodings(self):
        return ['application/protobuf']

    @property
    def namespaces(self):
        return [VAL_REG_NAMESPACE]

    def verify_signup_info(self,
                           signup_info,
                           originator_public_key_hash,
                           most_recent_wait_certificate_id):

        # Verify the attestation verification report signature
        proof_data_dict = json.loads(signup_info.proof_data)
        verification_report = proof_data_dict.get('verification_report')
        if verification_report is None:
            raise ValueError('Verification report is missing from proof data')

        signature = proof_data_dict.get('signature')
        if signature is None:
            raise ValueError('Signature is missing from proof data')

        if not signing.verify(
                verification_report,
                signature,
                self._report_public_key):
            raise ValueError('Verification report signature is invalid')

        verification_report_dict = json.loads(verification_report)

        # Verify that the verification report contains a PSE manifest status
        # and it is OK
        pse_manifest_status = \
            verification_report_dict.get('pseManifestStatus')
        if pse_manifest_status is None:
            raise \
                ValueError(
                    'Verification report does not contain a PSE manifest '
                    'status')
        if pse_manifest_status != 'OK':
            raise \
                ValueError(
                    'PSE manifest status is {} (i.e., not OK)'.format(
                        pse_manifest_status))

        # Verify that the verification report contains a PSE manifest hash
        # and it is the value we expect
        pse_manifest_hash = \
            verification_report_dict.get('pseManifestHash')
        if pse_manifest_hash is None:
            raise \
                ValueError(
                    'Verification report does not contain a PSE manifest '
                    'hash')

        expected_pse_manifest_hash = \
            base64.b64encode(
                hashlib.sha256(
                    bytes(b'Do you believe in '
                          b'manifest destiny?')).hexdigest()
                .encode()).decode()

        if pse_manifest_hash != expected_pse_manifest_hash:
            raise \
                ValueError(
                    'PSE manifest hash {0} does not match {1}'.format(
                        pse_manifest_hash,
                        expected_pse_manifest_hash))

        # Verify that the verification report contains an enclave quote and
        # that its status is OK
        enclave_quote_status = \
            verification_report_dict.get('isvEnclaveQuoteStatus')
        if enclave_quote_status is None:
            raise \
                ValueError(
                    'Verification report does not contain an enclave quote '
                    'status')
        if enclave_quote_status != 'OK':
            raise \
                ValueError(
                    'Enclave quote status is {} (i.e., not OK)'.format(
                        enclave_quote_status))

        enclave_quote = verification_report_dict.get('isvEnclaveQuoteBody')
        if enclave_quote is None:
            raise \
                ValueError(
                    'Verification report does not contain an enclave quote')

        # # Verify that the enclave quote contains a report body with the value
        # # we expect (i.e., SHA256(SHA256(OPK)|PPK)
        report_data = '{0}{1}'.format(
            originator_public_key_hash.upper(),
            signup_info.poet_public_key.upper()
        )
        expected_report_body = hashlib.sha256(
            json.dumps(report_data).encode()).hexdigest()

        enclave_quote_dict = \
            json.loads(base64.b64decode(enclave_quote).decode())
        report_body = enclave_quote_dict.get('report_body')
        if report_body is None:
            raise ValueError('Enclave quote does not contain a report body')

        if report_body != expected_report_body:
            raise \
                ValueError(
                    'Enclave quote report body {0} does not match {1}'.format(
                        report_body,
                        expected_report_body))

        # Verify that the wait certificate ID in the verification report
        # matches the provided wait certificate ID.  The wait certificate ID
        # is stored in the nonce field.
        nonce = verification_report_dict.get('nonce')
        if nonce is None:
            raise \
                ValueError(
                    'Verification report does not have a nonce')

        # NOTE - this check is currently not performed as a transaction
        #        does not have a good way to obtaining the most recent
        #        wait certificate ID.
        #
        # if nonce != most_recent_wait_certificate_id:
        #     raise \
        #         ValueError(
        #             'Attestation evidence payload nonce {0} does not match '
        #             'most-recently-committed wait certificate ID {1}'.format(
        #                 nonce,
        #                 most_recent_wait_certificate_id))

    def apply(self, transaction, state):
        txn_header = TransactionHeader()
        txn_header.ParseFromString(transaction.header)
        pubkey = txn_header.signer_pubkey

        val_reg_payload = ValidatorRegistryPayload()
        val_reg_payload.ParseFromString(transaction.payload)

        # Check name
        validator_name = val_reg_payload.name
        if len(validator_name) > 64:
            raise InvalidTransaction(
                'Illegal validator name {}'.format(validator_name))

        # Check registering validator matches transaction signer.
        validator_id = val_reg_payload.id
        if validator_id != pubkey:
            raise InvalidTransaction(
                'Signature mismatch on validator registration with validator'
                ' {} signed by {}'.format(validator_id, pubkey))

        public_key_hash = hashlib.sha256(pubkey.encode()).hexdigest()
        signup_info = val_reg_payload.signup_info

        try:
            self.verify_signup_info(
                signup_info=signup_info,
                originator_public_key_hash=public_key_hash,
                most_recent_wait_certificate_id='0' * 16)

        except ValueError as error:
            raise InvalidTransaction(
                'Invalid Signup Info: {0}, Reason: {1}'.format(
                    signup_info,
                    error))

        validator_info = ValidatorInfo(
            registered="registered",
            name=validator_name,
            id=validator_id,
            signup_info=val_reg_payload.signup_info,
            block_num=val_reg_payload.block_num
        )

        _update_validator_state(state,
                                validator_id,
                                signup_info.anti_sybil_id,
                                validator_info.SerializeToString())
