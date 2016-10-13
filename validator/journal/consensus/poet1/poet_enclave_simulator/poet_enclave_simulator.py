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

import pybitcointools

from gossip.common import json2dict
from gossip.common import dict2json
from journal.consensus.poet1.poet_enclave_simulator.enclave_signup_info \
    import EnclaveSignupInfo
from journal.consensus.poet1.poet_enclave_simulator.enclave_wait_timer \
    import EnclaveWaitTimer
from journal.consensus.poet1.poet_enclave_simulator.enclave_wait_certificate \
    import EnclaveWaitCertificate
from journal.consensus.poet1.signup_info import SignupInfoError
from journal.consensus.poet1.wait_timer import WaitTimerError
from journal.consensus.poet1.wait_certificate import WaitCertificateError

LOGGER = logging.getLogger(__name__)


MINIMUM_WAIT_TIME = 1.0


class _PoetEnclaveError(Exception):
    pass


class _PoetEnclaveSimulator(object):
    # A lock to protect threaded access
    _lock = threading.Lock()

    # The WIF-encoded enclave private seal key.  From it, we will create
    # private and public keys we can use for sealing and unsealing signup
    # info.
    __SEAL_PRIVATE_KEY_WIF = \
        '5KYsbooGBg51Gohakgq45enpXvCXmEBed1JivFfUZskmjLegHBG'

    _seal_private_key = \
        pybitcointools.decode_privkey(__SEAL_PRIVATE_KEY_WIF, 'wif')
    _seal_public_key = pybitcointools.privtopub(_seal_private_key)

    # The WIF-encoded private report key.  From it, we will create private
    # key we can use for signing attestation verification reports.
    __REPORT_PRIVATE_KEY_WIF = \
        '5Jz5Kaiy3kCiHE537uXcQnJuiNJshf2bZZn43CrALMGoCd3zRuo'

    _report_private_key = \
        pybitcointools.decode_privkey(__REPORT_PRIVATE_KEY_WIF, 'wif')
    _report_public_key = pybitcointools.privtopub(_report_private_key)

    # Minimum duration for PoET 1 simulator is 30 seconds
    __MINIMUM_DURATTION = 30.0

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
            pybitcointools.sha256(kwargs.get('NodeName', 'validator'))

    @classmethod
    def create_signup_info(cls,
                           originator_public_key,
                           validator_network_basename,
                           most_recent_wait_certificate_id):
        with cls._lock:
            # First we need to create a public/private key pair for the PoET
            # enclave to use.
            cls._poet_private_key = pybitcointools.random_key()
            cls._poet_public_key = \
                pybitcointools.privtopub(cls._poet_private_key)
            cls._active_wait_timer = None

            # We are going to fake out the sealing the signup data.
            signup_data = {
                'poet_public_key':
                    pybitcointools.encode_pubkey(cls._poet_public_key, 'hex'),
                'poet_private_key':
                    pybitcointools.encode_privkey(
                        cls._poet_private_key,
                        'hex')
            }
            sealed_signup_data = \
                pybitcointools.base64.b32encode(dict2json(signup_data))

            # Create a fake report
            report_data = {
                'originator_public_key_hash':
                    pybitcointools.sha256(
                        pybitcointools.encode_pubkey(
                            originator_public_key,
                            'hex')),
                'poet_public_key':
                    pybitcointools.encode_pubkey(cls._poet_public_key, 'hex')
            }
            report = {
                'report_data': pybitcointools.sha256(dict2json(report_data)),
                'validator_network_basename': validator_network_basename
            }

            # Fake our "proof" data.
            attestation_evidence_payload = {
                'enclave_quote':
                    pybitcointools.base64.b64encode(dict2json(report)),
                'pse_manifest':
                    pybitcointools.base64.b64encode(
                        pybitcointools.sha256(
                            'manifest destiny')),
                'nonce': most_recent_wait_certificate_id
            }

            attestation_verification_report = {
                'attestation_evidence_payload': attestation_evidence_payload,
                'anti_sybil_id': cls._anti_sybil_id
            }

            proof_data = {
                'attestation_verification_report':
                    attestation_verification_report,
                'signature':
                    pybitcointools.ecdsa_sign(
                        dict2json(attestation_verification_report),
                        cls._report_private_key)
            }

            return \
                EnclaveSignupInfo(
                    poet_public_key=signup_data['poet_public_key'],
                    proof_data=proof_data,
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
            json2dict(pybitcointools.base64.b32decode(sealed_signup_data))

        with cls._lock:
            cls._poet_public_key = \
                pybitcointools.decode_pubkey(
                    signup_data.get('poet_public_key'),
                    'hex')
            cls._poet_private_key = \
                pybitcointools.decode_privkey(
                    signup_data.get('poet_public_key'),
                    'hex')
            cls._active_wait_timer = None

            return signup_data.get('poet_public_key')

    @classmethod
    def verify_signup_info(cls,
                           signup_info,
                           originator_public_key,
                           validator_network_basename,
                           most_recent_wait_certificate_id):
        # Verify the attestation verification report signature
        attestation_verification_report = \
            signup_info.proof_data.get('attestation_verification_report')
        if attestation_verification_report is None:
            raise \
                SignupInfoError(
                    'Attestation verification report is missing from proof '
                    'data')

        if not pybitcointools.ecdsa_verify(
                dict2json(attestation_verification_report),
                signup_info.proof_data.get('signature'),
                cls._report_public_key):
            raise \
                SignupInfoError(
                    'Attestation verification report signature is invalid')

        # Verify the presence of the anti-Sybil ID
        anti_sybil_id = attestation_verification_report.get('anti_sybil_id')
        if anti_sybil_id is None:
            raise \
                SignupInfoError(
                    'Attestation verification report does not contain an '
                    'anti-Sybil ID')

        # Verify that the report data field in the report contains the SHA256
        # digest of the originator's public key SHA 256 digest and the PoET
        # public key.
        attestation_evidence_payload = \
            attestation_verification_report.get(
                'attestation_evidence_payload')
        if attestation_evidence_payload is None:
            raise \
                SignupInfoError(
                    'Attestation verification report does not contain '
                    'attestation evidence payload')

        enclave_quote = attestation_evidence_payload.get('enclave_quote')
        if enclave_quote is None:
            raise \
                SignupInfoError(
                    'Attestation evidence payload does not contain an '
                    'enclave quote')

        report = json2dict(pybitcointools.base64.b64decode(enclave_quote))
        report_data = report.get('report_data')
        if report_data is None:
            raise \
                SignupInfoError('Enclave quote does not contain report data')

        target_report_data = {
            'originator_public_key_hash':
                pybitcointools.sha256(
                    pybitcointools.encode_pubkey(
                        originator_public_key,
                        'hex')),
            'poet_public_key': signup_info.poet_public_key
        }
        target_report_data_digest = \
            pybitcointools.sha256(dict2json(target_report_data))

        if report_data != target_report_data_digest:
            raise SignupInfoError('Enclave quote report data is invalid')

        # Verify that the validator base name in the enclave quote report
        # matches the provided validator network basename
        validator_net_basename = report.get('validator_network_basename')
        if validator_net_basename is None:
            raise \
                SignupInfoError(
                    'Enclave quote report does not have a validator network '
                    'basename')

        if validator_net_basename != validator_network_basename:
            raise \
                SignupInfoError(
                    'Enclave quote report validator network basename [{0}] '
                    'does not match [{1}]'.format(
                        validator_net_basename,
                        validator_network_basename))

        # NOTE - this check is currently not performed as a transaction
        #        does not have a good way to obtaining the most recent
        #        wait certificate ID.
        #
        # Verify that the wait certificate ID in the attestation evidence
        # payload matches the provided wait certificate ID.  The wait
        # certificate ID is stored in the AEP nonce field.
        # nonce = attestation_evidence_payload.get('nonce')
        # if nonce is None:
        #     raise \
        #         SignupInfoError(
        #             'Attestation evidence payload does not have a nonce')
        #
        # if nonce != most_recent_wait_certificate_id:
        #     raise \
        #         SignupInfoError(
        #             'Attestation evidence payload nonce {0} does not match '
        #             'most-recently-committed wait certificate ID {1}'.format(
        #                 nonce,
        #                 most_recent_wait_certificate_id))

    @classmethod
    def create_wait_timer(cls, previous_certificate_id, local_mean):
        with cls._lock:
            # If we don't have a PoET private key, then the enclave has not
            # been properly initialized (either by calling create_signup_info
            # or unseal_signup_data)
            if cls._poet_private_key is None:
                raise \
                    WaitTimerError(
                        'Enclave must be initialized before attempting to '
                        'create a wait timer')

            # Create some value from the cert ID.  We are just going to use
            # the seal key to sign the cert ID.  We will then use the
            # low-order 64 bits to change that to a number [0, 1]
            tag = \
                pybitcointools.base64.b64decode(
                    pybitcointools.ecdsa_sign(
                        previous_certificate_id,
                        cls._seal_private_key))

            tagd = float(struct.unpack('L', tag[-8:])[0]) / (2**64 - 1)

            # Now compute the duration
            duration = cls.__MINIMUM_DURATTION - local_mean * math.log(tagd)

            # Create and sign the wait timer
            wait_timer = \
                EnclaveWaitTimer(
                    duration=duration,
                    previous_certificate_id=previous_certificate_id,
                    local_mean=local_mean)
            wait_timer.signature = \
                pybitcointools.ecdsa_sign(
                    wait_timer.serialize(),
                    cls._poet_private_key)

            # Keep track of the active wait timer
            cls._active_wait_timer = wait_timer

            return wait_timer

    @classmethod
    def deserialize_wait_timer(cls, serialized_timer, signature):
        with cls._lock:
            # Verify the signature before trying to deserialize
            if not pybitcointools.ecdsa_verify(
                    serialized_timer,
                    signature,
                    cls._poet_public_key):
                return None

        return \
            EnclaveWaitTimer.wait_timer_from_serialized(
                serialized_timer=serialized_timer,
                signature=signature)

    @classmethod
    def create_wait_certificate(cls, block_digest):
        with cls._lock:
            # If we don't have a PoET private key, then the enclave has not
            # been properly initialized (either by calling create_signup_info
            # or unseal_signup_data)
            if cls._poet_private_key is None:
                raise \
                    WaitCertificateError(
                        'Enclave must be initialized before attempting to '
                        'create a wait certificate')

            # Several criteria we need to be met before we can create a wait
            # certificate:
            # 1. We have an active timer
            # 2. The active timer has expired
            # 3. The active timer has not timed out
            if cls._active_wait_timer is None:
                raise \
                    WaitCertificateError(
                        'Enclave active wait timer has not been initialized')

            # HACK ALERT!!  HACK ALERT!!  HACK ALERT!!  HACK ALERT!!
            #
            # Today, without the genesis utility we cannot make these checks.
            # Once we have the genesis utility, this code needs to change to
            # Depend upon the timer not being expired or timed out.  The
            # Original specification requires this check.
            #
            # HACK ALERT!!  HACK ALERT!!  HACK ALERT!!  HACK ALERT!!
            #
            # if not cls._active_wait_timer.has_expired():
            #     raise \
            #         WaitCertificateError(
            #             'Cannot create wait certificate because timer has '
            #             'not expired')
            # if wait_timer.has_timed_out():
            #     raise \
            #         WaitCertificateError(
            #             'Cannot create wait certificate because timer '
            #             'has timed out')

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
            nonce = pybitcointools.sha256(random_string)

            # First create a new enclave wait certificate using the data
            # provided and then sign the certificate with the PoET private key
            wait_certificate = \
                EnclaveWaitCertificate.wait_certificate_with_wait_timer(
                    wait_timer=cls._active_wait_timer,
                    nonce=nonce,
                    block_digest=block_digest)
            wait_certificate.signature = \
                pybitcointools.ecdsa_sign(
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
        # poet_public_key = \
        #     pybitcointools.decode_pubkey(encoded_poet_public_key, 'hex')
        #
        # return \
        #     pybitcointools.ecdsa_verify(
        #         certificate.serialize(),
        #         certificate.signature,
        #         poet_public_key)

        return True


def initialize(**kwargs):
    _PoetEnclaveSimulator.initialize(**kwargs)


def create_signup_info(originator_public_key,
                       validator_network_basename,
                       most_recent_wait_certificate_id):
    return \
        _PoetEnclaveSimulator.create_signup_info(
            originator_public_key=originator_public_key,
            validator_network_basename=validator_network_basename,
            most_recent_wait_certificate_id=most_recent_wait_certificate_id)


def deserialize_signup_info(serialized_signup_info):
    return _PoetEnclaveSimulator.deserialize_signup_info(
        serialized_signup_info=serialized_signup_info)


def unseal_signup_data(sealed_signup_data):
    return _PoetEnclaveSimulator.unseal_signup_data(sealed_signup_data)


def verify_signup_info(signup_info,
                       originator_public_key,
                       validator_network_basename,
                       most_recent_wait_certificate_id):
    return \
        _PoetEnclaveSimulator.verify_signup_info(
            signup_info=signup_info,
            originator_public_key=originator_public_key,
            validator_network_basename=validator_network_basename,
            most_recent_wait_certificate_id=most_recent_wait_certificate_id)


def create_wait_timer(previous_certificate_id, local_mean):
    return \
        _PoetEnclaveSimulator.create_wait_timer(
            previous_certificate_id=previous_certificate_id,
            local_mean=local_mean)


def deserialize_wait_timer(serialized_timer, signature):
    return \
        _PoetEnclaveSimulator.deserialize_wait_timer(
            serialized_timer=serialized_timer,
            signature=signature)


def verify_wait_timer(timer):
    return timer.has_expired()


def create_wait_certificate(block_digest):
    return \
        _PoetEnclaveSimulator.create_wait_certificate(
            block_digest=block_digest)


def deserialize_wait_certificate(serialized_certificate, signature):
    return \
        _PoetEnclaveSimulator.deserialize_wait_certificate(
            serialized_certificate=serialized_certificate,
            signature=signature)


def verify_wait_certificate(certificate, poet_public_key):
    return \
        _PoetEnclaveSimulator.verify_wait_certificate(
            certificate=certificate,
            poet_public_key=poet_public_key)
