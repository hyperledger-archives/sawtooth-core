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

import struct
import math
import logging
import threading
import datetime
import hashlib
import base64
import time

from sawtooth_signing import secp256k1_signer as signing

from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER

from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator.common\
    import json2dict
from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator.common\
    import dict2json

from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator\
    .enclave_signup_info import EnclaveSignupInfo
from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator\
    .enclave_wait_timer import EnclaveWaitTimer
from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator\
    .enclave_wait_certificate import EnclaveWaitCertificate


LOGGER = logging.getLogger(__name__)

TIMER_TIMEOUT_PERIOD = 3.0


class _PoetEnclaveSimulator(object):
    # A lock to protect threaded access
    _lock = threading.Lock()

    # The private key we generate to sign the certificate ID when creating
    # the random wait timeout value
    _seal_private_key = signing.generate_privkey()
    _seal_public_key = signing.generate_pubkey(_seal_private_key)

    # The WIF-encoded private report key.  From it, we will create private
    # key we can use for signing attestation verification reports.
    __REPORT_PRIVATE_KEY_WIF = \
        '5Jz5Kaiy3kCiHE537uXcQnJuiNJshf2bZZn43CrALMGoCd3zRuo'

    _report_private_key = \
        signing.encode_privkey(
            signing.decode_privkey(__REPORT_PRIVATE_KEY_WIF, 'wif'), 'hex')
    _report_public_key = signing.generate_pubkey(_report_private_key)

    # The anti-sybil ID for this particular validator.  This will get set when
    # the enclave is initialized
    _anti_sybil_id = None

    # The PoET keys will remain unset until signup info is either created or
    # unsealed
    _poet_public_key = None
    _poet_private_key = None
    _active_wait_timer = None

    @classmethod
    def initialize(cls, **kwargs):
        # Create an anti-Sybil ID that is unique for this validator
        cls._anti_sybil_id = \
            hashlib.sha256(
                kwargs.get('NodeName', 'validator').encode()).hexdigest()

    @classmethod
    def create_signup_info(cls,
                           originator_public_key_hash,
                           most_recent_wait_certificate_id):
        with cls._lock:
            # First we need to create a public/private key pair for the PoET
            # enclave to use.
            cls._poet_private_key = signing.generate_privkey()
            cls._poet_public_key = \
                signing.generate_pubkey(cls._poet_private_key)
            cls._active_wait_timer = None

            # We are going to fake out the sealing the signup data.
            signup_data = {
                'poet_public_key':
                    signing.encode_pubkey(cls._poet_public_key, 'hex'),
                'poet_private_key':
                    signing.encode_privkey(
                        cls._poet_private_key,
                        'hex')
            }
            sealed_signup_data = \
                base64.b64encode(bytes(dict2json(signup_data).encode()))

            # Create a fake report
            report_data = '{0}{1}'.format(
                originator_public_key_hash.upper(),
                signing.encode_pubkey(
                    cls._poet_public_key,
                    'hex').upper()
            )
            quote = {
                'report_body': hashlib.sha256(
                    dict2json(report_data).encode()).hexdigest()
            }

            # Fake our "proof" data.
            verification_report = {
                'id': base64.b64encode(
                    bytes(hashlib.sha256(
                        datetime.datetime.now().isoformat().encode())
                        .hexdigest().encode())).decode(),
                'isvEnclaveQuoteStatus': 'OK',
                'isvEnclaveQuoteBody':
                    base64.b64encode(
                        dict2json(quote).encode()).decode(),
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
                'verification_report': dict2json(verification_report),
                'signature':
                    signing.sign(
                        dict2json(verification_report),
                        cls._report_private_key)
            }
            proof_data = dict2json(proof_data_dict)

            return \
                EnclaveSignupInfo(
                    poet_public_key=signup_data['poet_public_key'],
                    proof_data=proof_data,
                    anti_sybil_id=originator_public_key_hash,
                    sealed_signup_data=sealed_signup_data)

    @classmethod
    def deserialize_signup_info(cls, serialized_signup_info):
        return \
            EnclaveSignupInfo.signup_info_from_serialized(
                serialized_signup_info=serialized_signup_info)

    @classmethod
    def unseal_signup_data(cls, sealed_signup_data):
        """

        Args:
            sealed_signup_data: Sealed signup data that was returned
                previously in a EnclaveSignupInfo object from a call to
                create_signup_info

        Returns:
            A string The hex encoded PoET public key that was extracted from
            the sealed data
        """

        # Reverse the process we used in creating "sealed" signup info.
        # Specifically, we will do a base 32 decode, which gives us json
        # we can convert back to a dictionary we can use to get the
        # data we need
        signup_data = \
            json2dict(base64.b64decode(sealed_signup_data).decode())

        with cls._lock:
            cls._poet_public_key = \
                signing.decode_pubkey(
                    signup_data.get('poet_public_key'),
                    'hex')
            cls._poet_private_key = \
                signing.decode_privkey(
                    signup_data.get('poet_private_key'),
                    'hex')
            cls._active_wait_timer = None

            return signup_data.get('poet_public_key')

    @classmethod
    def verify_signup_info(cls,
                           signup_info,
                           originator_public_key_hash,
                           most_recent_wait_certificate_id):
        # Verify the attestation verification report signature
        proof_data_dict = json2dict(signup_info.proof_data)
        verification_report = proof_data_dict.get('verification_report')
        if verification_report is None:
            raise ValueError('Verification report is missing from proof data')

        signature = proof_data_dict.get('signature')
        if signature is None:
            raise ValueError('Signature is missing from proof data')

        if not signing.verify(
                verification_report,
                signature,
                cls._report_public_key):
            raise ValueError('Verification report signature is invalid')

        verification_report_dict = json2dict(verification_report)

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

        # Verify that the enclave quote contains a report body with the value
        # we expect (i.e., SHA256(SHA256(OPK)|PPK)
        report_data = '{0}{1}'.format(
            originator_public_key_hash.upper(),
            signup_info.poet_public_key.upper()
        )
        expected_report_body = hashlib.sha256(
            dict2json(report_data).encode()).hexdigest()

        enclave_quote_dict = \
            json2dict(base64.b64decode(enclave_quote).decode())
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

    @classmethod
    def create_wait_timer(cls,
                          validator_address,
                          previous_certificate_id,
                          local_mean,
                          minimum_wait_time):
        with cls._lock:
            # If we don't have a PoET private key, then the enclave has not
            # been properly initialized (either by calling create_signup_info
            # or unseal_signup_data)
            if cls._poet_private_key is None:
                raise \
                    ValueError(
                        'Enclave must be initialized before attempting to '
                        'create a wait timer')

            # Create some value from the cert ID.  We are just going to use
            # the seal key to sign the cert ID.  We will then use the
            # low-order 64 bits to change that to a number [0, 1]
            tag = \
                base64.b64decode(
                    signing.sign(
                        previous_certificate_id,
                        cls._seal_private_key))

            tagd = float(struct.unpack('Q', tag[-8:])[0]) / (2**64 - 1)

            # Now compute the duration with a minimum wait time guaranteed
            duration = minimum_wait_time - local_mean * math.log(tagd)

            # Create and sign the wait timer
            wait_timer = \
                EnclaveWaitTimer(
                    validator_address=validator_address,
                    duration=duration,
                    previous_certificate_id=previous_certificate_id,
                    local_mean=local_mean)
            wait_timer.signature = \
                signing.sign(
                    wait_timer.serialize(),
                    cls._poet_private_key)

            # Keep track of the active wait timer
            cls._active_wait_timer = wait_timer

            return wait_timer

    @classmethod
    def deserialize_wait_timer(cls, serialized_timer, signature):
        with cls._lock:
            # Verify the signature before trying to deserialize
            if not signing.verify(
                    serialized_timer,
                    signature,
                    cls._poet_public_key):
                return None

        return \
            EnclaveWaitTimer.wait_timer_from_serialized(
                serialized_timer=serialized_timer,
                signature=signature)

    @classmethod
    def create_wait_certificate(cls,
                                wait_timer,
                                block_digest):
        with cls._lock:
            # If we don't have a PoET private key, then the enclave has not
            # been properly initialized (either by calling create_signup_info
            # or unseal_signup_data)
            if cls._poet_private_key is None:
                raise \
                    ValueError(
                        'Enclave must be initialized before attempting to '
                        'create a wait certificate')

            # Several criteria need to be met before we can create a wait
            # certificate:
            # 1. We have an active timer
            # 2. The caller's wait timer is the active wait timer.  We are not
            #    going to rely the objects, being the same, but will compute
            #    a signature over the object and verify that the signatures
            #    are the same.
            # 3. The active timer has expired
            # 4. The active timer has not timed out
            #
            # Note - we make a concession for the genesis block (i.e., a wait
            # timer for which the previous certificate ID is the Null
            # identifier) in that we don't require the timer to have expired
            # and we don't worry about the timer having timed out.
            if cls._active_wait_timer is None:
                raise \
                    ValueError(
                        'There is not a current enclave active wait timer')

            if wait_timer is None or \
                    cls._active_wait_timer.signature != \
                    signing.sign(
                        wait_timer.serialize(),
                        cls._poet_private_key):
                raise \
                    ValueError(
                        'Validator is not using the current wait timer')

            is_not_genesis_block = \
                (cls._active_wait_timer.previous_certificate_id !=
                 NULL_BLOCK_IDENTIFIER)

            now = time.time()
            expire_time = \
                cls._active_wait_timer.request_time + \
                cls._active_wait_timer.duration

            if is_not_genesis_block and now < expire_time:
                raise \
                    ValueError(
                        'Cannot create wait certificate because timer has '
                        'not expired')

            time_out_time = \
                cls._active_wait_timer.request_time + \
                cls._active_wait_timer.duration + \
                TIMER_TIMEOUT_PERIOD

            if is_not_genesis_block and time_out_time < now:
                raise \
                    ValueError(
                        'Cannot create wait certificate because timer '
                        'has timed out')

            # Create a random nonce for the certificate.  For our "random"
            # nonce we will take the timer signature, concat that with the
            # current time, JSON-ize it and create a SHA-256 hash over it.
            # Probably not considered random by security professional
            # standards, but it is good enough for the simulator.
            random_string = \
                dict2json({
                    'wait_timer_signature': cls._active_wait_timer.signature,
                    'now': datetime.datetime.utcnow().isoformat()
                })
            nonce = hashlib.sha256(random_string.encode()).hexdigest()

            # First create a new enclave wait certificate using the data
            # provided and then sign the certificate with the PoET private key
            wait_certificate = \
                EnclaveWaitCertificate.wait_certificate_with_wait_timer(
                    wait_timer=cls._active_wait_timer,
                    nonce=nonce,
                    block_digest=block_digest)
            wait_certificate.signature = \
                signing.sign(
                    wait_certificate.serialize(),
                    cls._poet_private_key)

            # Now that we have created the certificate, we no longer have an
            # active timer
            cls._active_wait_timer = None

            return wait_certificate

    @classmethod
    def deserialize_wait_certificate(cls, serialized_certificate, signature):
        return \
            EnclaveWaitCertificate.wait_certificate_from_serialized(
                serialized_certificate=serialized_certificate,
                signature=signature)

    @classmethod
    def verify_wait_certificate(cls, certificate, poet_public_key):
        # Reconstitute the PoET public key and check the signature over the
        # serialized wait certificate.
        decoded_poet_public_key = \
            signing.decode_pubkey(poet_public_key, 'hex')

        if not \
            signing.verify(
                certificate.serialize(),
                certificate.signature,
                decoded_poet_public_key):
            raise ValueError('Wait certificate signature does not match')


def initialize(**kwargs):
    _PoetEnclaveSimulator.initialize(**kwargs)


def create_signup_info(validator_address,
                       originator_public_key_hash,
                       most_recent_wait_certificate_id):
    return \
        _PoetEnclaveSimulator.create_signup_info(
            originator_public_key_hash=originator_public_key_hash,
            most_recent_wait_certificate_id=most_recent_wait_certificate_id)


def deserialize_signup_info(serialized_signup_info):
    return _PoetEnclaveSimulator.deserialize_signup_info(
        serialized_signup_info=serialized_signup_info)


def unseal_signup_data(validator_address, sealed_signup_data):
    return _PoetEnclaveSimulator.unseal_signup_data(sealed_signup_data)


def verify_signup_info(signup_info,
                       originator_public_key_hash,
                       most_recent_wait_certificate_id):
    return \
        _PoetEnclaveSimulator.verify_signup_info(
            signup_info=signup_info,
            originator_public_key_hash=originator_public_key_hash,
            most_recent_wait_certificate_id=most_recent_wait_certificate_id)


def create_wait_timer(validator_address,
                      previous_certificate_id,
                      local_mean,
                      minimum_wait_time=1.0):
    return \
        _PoetEnclaveSimulator.create_wait_timer(
            validator_address=validator_address,
            previous_certificate_id=previous_certificate_id,
            local_mean=local_mean,
            minimum_wait_time=minimum_wait_time)


def deserialize_wait_timer(serialized_timer, signature):
    return \
        _PoetEnclaveSimulator.deserialize_wait_timer(
            serialized_timer=serialized_timer,
            signature=signature)


def create_wait_certificate(wait_timer, block_digest):
    return \
        _PoetEnclaveSimulator.create_wait_certificate(
            wait_timer=wait_timer,
            block_digest=block_digest)


def deserialize_wait_certificate(serialized_certificate, signature):
    return \
        _PoetEnclaveSimulator.deserialize_wait_certificate(
            serialized_certificate=serialized_certificate,
            signature=signature)


def verify_wait_certificate(certificate, poet_public_key):
    _PoetEnclaveSimulator.verify_wait_certificate(
        certificate=certificate,
        poet_public_key=poet_public_key)
