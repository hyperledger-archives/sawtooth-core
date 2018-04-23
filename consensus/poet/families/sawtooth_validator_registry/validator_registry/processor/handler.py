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

from sawtooth_sdk.processor.handler import TransactionHandler
from sawtooth_sdk.messaging.future import FutureTimeoutError
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.protobuf.setting_pb2 import Setting

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


# Constants to be used when constructing config namespace addresses
_CONFIG_NAMESPACE = '000000'
_CONFIG_MAX_KEY_PARTS = 4
_CONFIG_ADDRESS_PART_SIZE = 16


def _config_short_hash(byte_str):
    # Computes the SHA 256 hash and truncates to be the length
    # of an address part (see _config_key_to_address for information on
    return hashlib.sha256(byte_str).hexdigest()[:_CONFIG_ADDRESS_PART_SIZE]


_CONFIG_ADDRESS_PADDING = _config_short_hash(byte_str=b'')


def _config_key_to_address(key):
    """Computes the address for the given setting key.

     Keys are broken into four parts, based on the dots in the string. For
     example, the key `a.b.c` address is computed based on `a`, `b`, `c` and
     padding. A longer key, for example `a.b.c.d.e`, is still
     broken into four parts, but the remaining pieces are in the last part:
     `a`, `b`, `c` and `d.e`.

     Each of these pieces has a short hash computed (the first
     _CONFIG_ADDRESS_PART_SIZE characters of its SHA256 hash in hex), and is
     joined into a single address, with the config namespace
     (_CONFIG_NAMESPACE) added at the beginning.

     Args:
         key (str): the setting key
     Returns:
         str: the computed address
     """
    # Split the key into _CONFIG_MAX_KEY_PARTS parts, maximum, compute the
    # short hash of each, and then pad if necessary
    key_parts = key.split('.', maxsplit=_CONFIG_MAX_KEY_PARTS - 1)
    addr_parts = [_config_short_hash(byte_str=x.encode()) for x in key_parts]
    addr_parts.extend(
        [_CONFIG_ADDRESS_PADDING] * (_CONFIG_MAX_KEY_PARTS - len(addr_parts)))
    return _CONFIG_NAMESPACE + ''.join(addr_parts)


def _get_state(context, address, value_type):
    try:
        entries_list = context.get_state([address], timeout=STATE_TIMEOUT_SEC)
    except FutureTimeoutError:
        LOGGER.warning('Timeout occurred on context.get_state([%s])', address)
        raise InternalError('Unable to get {}'.format(address))

    value = value_type()
    if entries_list:
        value.ParseFromString(entries_list[0].data)

    return value


def _get_address(key):
    address = VAL_REG_NAMESPACE + hashlib.sha256(key.encode()).hexdigest()
    return address


def _get_validator_map(context):
    address = _get_address('validator_map')
    return _get_state(
        context=context,
        address=address,
        value_type=ValidatorMap)


def _update_validator_state(context,
                            validator_id,
                            anti_sybil_id,
                            validator_info):

    validator_map = _get_validator_map(context)
    updated_map = ValidatorMap()
    # Clean out old entries in ValidatorInfo and ValidatorMap
    # Protobuf doesn't offer delete item for ValidatorMap so create a new list
    # Use the validator map to find all occurrences of an anti_sybil_id
    # Use any such entry to find the associated validator id.
    # Use that validator id as the key to remove the ValidatorInfo from the
    # registry
    for entry in validator_map.entries:
        if anti_sybil_id == entry.key:
            validator_info_address = _get_address(entry.value)
            _delete_address(context, validator_info_address)
        else:
            updated_map.entries.add(key=entry.key, value=entry.value)

    # Add new state entries to ValidatorMap and ValidatorInfo
    updated_map.entries.add(key=anti_sybil_id, value=validator_id)
    validator_map_address = _get_address('validator_map')
    _set_data(context, validator_map_address, updated_map.SerializeToString())

    validator_info_address = _get_address(validator_id)
    _set_data(context, validator_info_address, validator_info)
    LOGGER.info("Validator id %s was added to the validator_map and set.",
                validator_id)


def _delete_address(context, address):
    try:
        remove_addresses = list()
        remove_addresses.append(address)
        addresses = list(context.delete_state(
            remove_addresses,
            timeout=STATE_TIMEOUT_SEC))

    except FutureTimeoutError:
        LOGGER.warning(
            'Timeout occurred on state.delete_state([%s, <value>])', address)
        raise InternalError(
            'Failed to save value on address {}'.format(address))

    if len(addresses) != 1:
        LOGGER.warning(
            'Failed to save value on address %s', address)
        raise InternalError(
            'Failed to save value on address {}'.format(address))


def _set_data(context, address, data):
    try:
        addresses = list(context.set_state(
            {address: data},
            timeout=STATE_TIMEOUT_SEC)
        )

    except FutureTimeoutError:
        LOGGER.warning(
            'Timeout occurred on context.set_state([%s, <value>])', address)
        raise InternalError(
            'Failed to save value on address {}'.format(address))

    if len(addresses) != 1:
        LOGGER.warning(
            'Failed to save value on address %s', address)
        raise InternalError(
            'Failed to save value on address {}'.format(address))


def _get_config_setting(context, key):
    setting = \
        _get_state(
            context=context,
            address=_config_key_to_address(key),
            value_type=Setting)
    for setting_entry in setting.entries:
        if setting_entry.key == key:
            return setting_entry.value

    raise KeyError('Setting for {} not found'.format(key))


class ValidatorRegistryTransactionHandler(TransactionHandler):
    def __init__(self):
        pass

    @property
    def family_name(self):
        return 'sawtooth_validator_registry'

    @property
    def family_versions(self):
        return ['1.0']

    @property
    def namespaces(self):
        return [VAL_REG_NAMESPACE]

    def _verify_signup_info(self,
                            signup_info,
                            originator_public_key_hash,
                            val_reg_payload,
                            context):

        # Verify the attestation verification report signature
        proof_data_dict = json.loads(signup_info.proof_data)
        verification_report = proof_data_dict.get('verification_report')
        if verification_report is None:
            raise ValueError('Verification report is missing from proof data')

        signature = proof_data_dict.get('signature')
        if signature is None:
            raise ValueError('Signature is missing from proof data')

        # Try to get the report key from the configuration setting.  If it
        # is not there or we cannot parse it, fail verification.
        try:
            report_public_key_pem = \
                _get_config_setting(
                    context=context,
                    key='sawtooth.poet.report_public_key_pem')
            report_public_key = \
                serialization.load_pem_public_key(
                    report_public_key_pem.encode(),
                    backend=backends.default_backend())
        except KeyError:
            raise \
                ValueError(
                    'Report public key configuration setting '
                    '(sawtooth.poet.report_public_key_pem) not found.')
        except (TypeError, ValueError) as error:
            raise ValueError('Failed to parse public key: {}'.format(error))

        # Retrieve the valid enclave measurement values, converting the comma-
        # delimited list. If it is not there, or fails to parse correctly,
        # fail verification.
        try:
            valid_measurements = \
                _get_config_setting(
                    context=context,
                    key='sawtooth.poet.valid_enclave_measurements')
            valid_enclave_mesaurements = \
                [bytes.fromhex(m) for m in valid_measurements.split(',')]
        except KeyError:
            raise \
                ValueError(
                    'Valid enclave measurements configuration setting '
                    '(sawtooth.poet.valid_enclave_measurements) not found.')
        except ValueError as error:
            raise \
                ValueError(
                    'Failed to parse enclave measurement: {}'.format(
                        valid_measurements))

        # Retrieve the valid enclave basename value. If it is not there, or
        # fails to parse correctly, fail verification.
        try:
            valid_basenames = \
                _get_config_setting(
                    context=context,
                    key='sawtooth.poet.valid_enclave_basenames')
            valid_enclave_basenames = \
                [bytes.fromhex(b) for b in valid_basenames.split(',')]
        except KeyError:
            raise \
                ValueError(
                    'Valid enclave basenames configuration setting '
                    '(sawtooth.poet.valid_enclave_basenames) not found.')
        except ValueError:
            raise \
                ValueError(
                    'Failed to parse enclave basename: {}'.format(
                        valid_basenames))

        try:
            report_public_key.verify(
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
            if pse_manifest_status.upper() == 'OUT_OF_DATE':
                LOGGER.warning('Peer has out of date (but not revoked)'
                               ' hardware, pseManifestStatus: %s',
                               pse_manifest_status)
            else:
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
            hashlib.sha256(
                base64.b64decode(pse_manifest.encode())).hexdigest()
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
            if enclave_quote_status.upper() == 'GROUP_OUT_OF_DATE':
                LOGGER.warning('Peer has out of date (but not revoked)'
                               ' hardware, isvEnclaveQuoteStatus: %s',
                               str(enclave_quote_status))
            else:
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
                signup_info.poet_public_key.upper()).encode()
        hash_value = hashlib.sha256(hash_input).digest()
        expected_report_data = \
            hash_value + \
            (b'\x00'
             * (sgx_structs.SgxReportData.STRUCT_SIZE - len(hash_value)))

        if sgx_quote.report_body.report_data.d != expected_report_data:
            raise \
                ValueError(
                    'AVR report data [{0}] not equal to [{1}]'.format(
                        sgx_quote.report_body.report_data.d.hex(),
                        expected_report_data.hex()))

        # Verify that the enclave measurement is in the list of valid
        # enclave measurements.
        if sgx_quote.report_body.mr_enclave.m not in \
                valid_enclave_mesaurements:
            raise \
                ValueError(
                    'AVR enclave measurement [{}] not in list of valid '
                    'enclave measurements [{}]'.format(
                        sgx_quote.report_body.mr_enclave.m.hex(),
                        valid_measurements))

        # Verify that the enclave basename is in the list of valid
        # enclave basenames
        if sgx_quote.basename.name not in valid_enclave_basenames:
            raise \
                ValueError(
                    'AVR enclave basename [{}] not in list of valid '
                    'enclave basenames [{}]'.format(
                        sgx_quote.basename.name.hex(),
                        valid_basenames))

        # Verify that the nonce in the verification report matches the nonce
        # in the transaction payload submitted
        nonce = verification_report_dict.get('nonce', '')
        if nonce != val_reg_payload.signup_info.nonce:
            raise \
                ValueError(
                    'AVR nonce [{0}] does not match signup info nonce '
                    '[{1}]'.format(
                        nonce,
                        val_reg_payload.signup_info.nonce))

    def apply(self, transaction, context):
        txn_header = transaction.header
        public_key = txn_header.signer_public_key

        val_reg_payload = ValidatorRegistryPayload()
        val_reg_payload.ParseFromString(transaction.payload)

        # Check name
        validator_name = val_reg_payload.name
        if len(validator_name) > 64:
            raise InvalidTransaction(
                'Illegal validator name {}'.format(validator_name))

        # Check registering validator matches transaction signer.
        validator_id = val_reg_payload.id
        if validator_id != public_key:
            raise InvalidTransaction(
                'Signature mismatch on validator registration with validator'
                ' {} signed by {}'.format(validator_id, public_key))

        public_key_hash = hashlib.sha256(public_key.encode()).hexdigest()
        signup_info = val_reg_payload.signup_info

        try:
            self._verify_signup_info(
                signup_info=signup_info,
                originator_public_key_hash=public_key_hash,
                val_reg_payload=val_reg_payload,
                context=context)

        except ValueError as error:
            raise InvalidTransaction(
                'Invalid Signup Info: {0}, Reason: {1}'.format(
                    signup_info,
                    error))

        validator_info = ValidatorInfo(
            name=validator_name,
            id=validator_id,
            signup_info=val_reg_payload.signup_info,
            transaction_id=transaction.signature
        )

        _update_validator_state(context,
                                validator_id,
                                signup_info.anti_sybil_id,
                                validator_info.SerializeToString())
