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

from cryptography.hazmat import backends
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

from sawtooth_sdk.processor.state import StateEntry
from sawtooth_sdk.client.future import FutureTimeoutError
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_poet_common import sgx_structs
from sawtooth_poet_common.protobuf.validator_registry_pb2 import \
    ValidatorInfo
from sawtooth_poet_common.protobuf.validator_registry_pb2 import \
    ValidatorMap
from sawtooth_poet_common.protobuf.validator_registry_pb2 import \
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

    # The basename and enclave measurement values we expect to find
    # in the enclave quote in the attestation verification report.
    __VALID_BASENAME__ = \
        bytes.fromhex(
            'b785c58b77152cbe7fd55ee3851c4990'
            '00000000000000000000000000000000')
    __VALID_ENCLAVE_MEASUREMENT__ = \
        bytes.fromhex(
            'c99f21955e38dbb03d2ca838d3af6e43'
            'ef438926ed02db4cc729380c8c7a174e')

    # The report public key PEM is used to create the public key used to
    # verify the signature on the attestation verification reports.
    __REPORT_PUBLIC_KEY_PEM__ = \
        '-----BEGIN PUBLIC KEY-----\n' \
        'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArMvzZi8GT+lI9KeZiInn\n' \
        '4CvFTiuyid+IN4dP1+mhTnfxX+I/ntt8LUKZMbI1R1izOUoxJRoX6VQ4S9VgDLEC\n' \
        'PW6QlkeLI1eqe4DiYb9+J5ANhq4+XkhwgCUUFwpfqSfXWCHimjaGsZHbavl5nv/6\n' \
        'IbZJL/2YzE37IzJdES16JCfmIUrk6TUqL0WgrWXyweTIoVSbld0M29kToSkMXLsj\n' \
        '8vbQbTiKwViWhYlzi0cQIo7PiAss66lAW0X6AM7ZJYyAcfSjSLR4guMz76Og8aRk\n' \
        'jtsjEEkq7Ndz5H8hllWUoHpxGDqLhM9O1/h+QdvTz7luZgpeJ5KB92vYL6yOlSxM\n' \
        'fQIDAQAB\n' \
        '-----END PUBLIC KEY-----'

    def __init__(self):
        self._report_public_key = \
            serialization.load_pem_public_key(
                self.__REPORT_PUBLIC_KEY_PEM__.encode(),
                backend=backends.default_backend())

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

        try:
            self._report_public_key.verify(
                base64.b64decode(signature.encode()),
                verification_report.encode(),
                padding.PKCS1v15(),
                hashes.SHA256())
        except InvalidSignature:
            raise ValueError('Verification report signature is invalid')

        verification_report_dict = json.loads(verification_report)

        # Verify that the verification report contains an ID field
        if 'id' not in verification_report_dict:
            raise ValueError('Verification report does not contain an ID')

        # Verify that the verification report contains an EPID pseudonym and
        # that it matches the anti-Sybil ID
        epid_pseudonym = verification_report_dict.get('epidPseudonym')
        if epid_pseudonym is None:
            raise \
                ValueError(
                    'Verification report does not contain an EPID pseudonym')

        if epid_pseudonym != signup_info.anti_sybil_id:
            raise \
                ValueError(
                    'The anti-Sybil ID in the verification report [{0}] does '
                    'not match the one contained in the signup information '
                    '[{1}]'.format(
                        epid_pseudonym,
                        signup_info.anti_sybil_id))

        # Verify that the verification report contains a PSE manifest status
        # and it is OK
        pse_manifest_status = \
            verification_report_dict.get('pseManifestStatus')
        if pse_manifest_status is None:
            raise \
                ValueError(
                    'Verification report does not contain a PSE manifest '
                    'status')
        if pse_manifest_status.upper() != 'OK':
            raise \
                ValueError(
                    'PSE manifest status is {} (i.e., not OK)'.format(
                        pse_manifest_status))

        # Verify that the verification report contains a PSE manifest hash
        pse_manifest_hash = \
            verification_report_dict.get('pseManifestHash')
        if pse_manifest_hash is None:
            raise \
                ValueError(
                    'Verification report does not contain a PSE manifest '
                    'hash')

        # Verify that the proof data contains evidence payload
        evidence_payload = proof_data_dict.get('evidence_payload')
        if evidence_payload is None:
            raise ValueError('Evidence payload is missing from proof data')

        # Verify that the evidence payload contains a PSE manifest and then
        # use it to make sure that the PSE manifest hash is what we expect
        pse_manifest = evidence_payload.get('pse_manifest')
        if pse_manifest is None:
            raise ValueError('Evidence payload does not include PSE manifest')

        expected_pse_manifest_hash = \
            base64.b64encode(
                hashlib.sha256(
                    pse_manifest.encode()).hexdigest().encode()).decode()

        if pse_manifest_hash.upper() != expected_pse_manifest_hash.upper():
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
        if enclave_quote_status.upper() != 'OK':
            raise \
                ValueError(
                    'Enclave quote status is {} (i.e., not OK)'.format(
                        enclave_quote_status))

        # Verify that the verification report contains an enclave quote
        enclave_quote = verification_report_dict.get('isvEnclaveQuoteBody')
        if enclave_quote is None:
            raise \
                ValueError(
                    'Verification report does not contain an enclave quote')

        # The ISV enclave quote body is base 64 encoded, so decode it and then
        # create an SGX quote structure from it so we can inspect
        sgx_quote = sgx_structs.SgxQuote()
        sgx_quote.parse_from_bytes(base64.b64decode(enclave_quote))

        # The report body should be SHA256(SHA256(OPK)|PPK)
        #
        # NOTE - since the code that created the report data is in the enclave
        # code, this code needs to be kept in sync with it.  Any changes to how
        # the report data is created, needs to be reflected in how we re-create
        # the report data for verification.

        hash_input = \
            '{0}{1}'.format(
                originator_public_key_hash.upper(),
                signup_info.poet_public_key.upper().upper()).encode()
        hash_value = hashlib.sha256(hash_input).digest()
        expected_report_data = \
            hash_value + \
            (b'\x00' *
             (sgx_structs.SgxReportData.STRUCT_SIZE - len(hash_value)))

        if sgx_quote.report_body.report_data.d != expected_report_data:
            raise \
                ValueError(
                    'AVR report data [{0}] not equal to [{1}]'.format(
                        sgx_quote.report_body.report_data.d.hex(),
                        expected_report_data.hex()))

        # Compare the enclave measurement against the expected valid enclave
        # measurement.
        #
        # NOTE - this is only a temporary check.  Instead of checking against
        # a predefined enclave measurement value, we should be configured with
        # a set of one or more enclave measurement values that we will
        # consider as valid.

        if sgx_quote.report_body.mr_enclave.m != \
                self.__VALID_ENCLAVE_MEASUREMENT__:
            raise \
                ValueError(
                    'AVR enclave measurement [{0}] not equal to [{1}]'.format(
                        sgx_quote.report_body.mr_enclave.m.hex(),
                        self.__VALID_ENCLAVE_MEASUREMENT__.hex()))

        # Compare the enclave basename in the verification report against the
        # expected enclave basename.
        #
        # NOTE - this is only a temporary check.  Instead of checking against
        # a predefined enclave basenme value, we should be configured with a
        # set of one or more enclave basenames that we will consider as valid.

        if sgx_quote.basename.name != self.__VALID_BASENAME__:
            raise \
                ValueError(
                    'AVR enclave basename [{0}] not equal to [{1}]'.format(
                        sgx_quote.basename.name.hex(),
                        self.__VALID_BASENAME__.hex()))

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
