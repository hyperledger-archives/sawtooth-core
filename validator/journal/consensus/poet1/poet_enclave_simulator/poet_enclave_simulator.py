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

import time
import struct
import math
import logging

from datetime import datetime

import pybitcointools

from gossip.common import json2dict
from gossip.common import dict2json
from journal.consensus.poet1.poet_enclave_simulator.signup_info \
    import EnclaveSignupInfo
from journal.consensus.poet1.poet_enclave_simulator.wait_timer \
    import EnclaveWaitTimer
from journal.consensus.poet1.poet_enclave_simulator.wait_certificate \
    import EnclaveWaitCertificate


LOGGER = logging.getLogger(__name__)


class _MonotonicCounter(object):
    def __init__(self, id=None):
        self._id = id
        # If there is no ID provided, we are going to manufacture one
        # by getting the current UTC time, converting it to ISO format,
        # and then using the first 16 hex digits of the SHA 256 hash.
        if self._id is None:
            self._id = \
                pybitcointools.sha256(datetime.utcnow().isoformat())[:16]

        # We are going to initialize the counter's value to the GM time
        # in seconds since epoch
        self._current_value = int(time.mktime(time.gmtime()))

    @property
    def id(self):
        return self._id

    @property
    def current_value(self):
        return self._current_value

    def increment_counter(self):
        self._current_value += 1
        return self._current_value


MINIMUM_WAIT_TIME = 1.0


class _PoetEnclaveSimulator(object):

    # The WIF-encoded SGX enclave private seal key.  From it, we will create
    # private and public keys we can use for sealing and unsealing signup
    # info.
    __SEAL_PRIVATE_KEY_WIF = \
        '5KYsbooGBg51Gohakgq45enpXvCXmEBed1JivFfUZskmjLegHBG'

    _sgx_seal_private_key = \
        pybitcointools.decode_privkey(__SEAL_PRIVATE_KEY_WIF, 'wif')
    _sgx_seal_public_key = pybitcointools.privtopub(_sgx_seal_private_key)

    # Minimum duration for PoET 1 simulator is 30 seconds
    __MINIMUM_DURATTION = 30.0

    # The PoET keys and monotonic counter ID will remain unset until
    # signup info is either created or unsealed
    _poet_public_key = None
    _poet_private_key = None
    _monotonic_counter = None
    _active_wait_timer = None
    _current_counter_value = None

    @classmethod
    def create_signup_info(cls, originator_id):
        # First we need to create a public/private key pair for the PoET
        # enclave to use.
        cls._poet_private_key = pybitcointools.random_key()
        cls._poet_public_key = pybitcointools.privtopub(cls._poet_private_key)
        cls._monotonic_counter = _MonotonicCounter()
        cls._active_wait_timer = None

        # We are going to fake out the using of SGX to seal the signup info.
        signup_data = {
            'ppk':
                pybitcointools.encode_pubkey(cls._poet_public_key, 'hex'),
            'psk':
                pybitcointools.encode_privkey(cls._poet_private_key, 'hex'),
            'mcid': cls._monotonic_counter.id
        }
        sealed_signup_data = \
            pybitcointools.base64.b32encode(dict2json(signup_data))

        # Create a fake SGX enclave report
        report_data = {
            'oid_hash': pybitcointools.sha256(originator_id),
            'ppk': pybitcointools.encode_pubkey(cls._poet_public_key, 'hex')
        }
        report = {
            'report_data': pybitcointools.sha256(dict2json(report_data))
        }
        report = pybitcointools.base64.b32encode(dict2json(report))

        # Our "proof" data is going to be the faked SGX enclave report and
        # a fake SGX PSE (platform services enclave) manifest
        proof_data = {
            'report': report,
            'manifest': 'These are not the droids you are looking for'
        }

        return \
            EnclaveSignupInfo(
                anti_sybil_id='Sally Field',
                poet_public_key=signup_data['ppk'],
                proof_data=proof_data,
                sealed_signup_data=sealed_signup_data)

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

        cls._poet_public_key = \
            pybitcointools.decode_pubkey(signup_data.get('ppk'), 'hex')
        cls._poet_private_key = \
            pybitcointools.decode_privkey(signup_data.get('psk'), 'hex')
        cls._monotonic_counter_id = \
            _MonotonicCounter(id=signup_data.get('mcid'))
        cls._active_wait_timer = None

        return pybitcointools.encode_pubkey(cls._poet_public_key, 'hex')

    @classmethod
    def verify_signup_info(cls, serialized_signup_info):
        # For now, we are going to always indicate that the signup information
        # is valid
        return True

    @classmethod
    def create_wait_timer(cls, previous_certificate_id, local_mean):
        # Increment the monotonic counter and store its value in the enclave.
        # Since we don't really implement the monotonic counter the way the
        # SGX enclave does, this is really superflous.
        # assert cls._monotonic_counter
        cls._current_counter_value = \
            cls._monotonic_counter.increment_counter()

        # Create some value from the cert ID.  We are just going to use
        # the seal key to sign the cert ID.  We will then use the low-order
        # 64 bits to change that to a number [0, 1]
        tag = \
            pybitcointools.base64.b64decode(
                pybitcointools.ecdsa_sign(
                    previous_certificate_id,
                    cls._sgx_seal_private_key))

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
        return \
            EnclaveWaitTimer.wait_timer_from_serialized(
                serialized_timer=serialized_timer,
                signature=signature)

    @classmethod
    def create_wait_certificate(cls, timer, block_digest):
        # TODO - implement PoET 1 create certificate logic

        # First create a new enclave wait certificate using the data provided
        # and then sign the certificate with the PoET private key
        wait_certificate = \
            EnclaveWaitCertificate.wait_certificate_with_timer(
                timer=timer,
                block_digest=block_digest)
        wait_certificate.signature = \
            pybitcointools.ecdsa_sign(
                wait_certificate.serialize(),
                cls._poet_private_key)

        return wait_certificate

    @classmethod
    def deserialize_wait_certificate(cls, serialized_certificate, signature):
        return \
            EnclaveWaitCertificate.wait_certificate_from_serialized(
                serialized_certificate=serialized_certificate,
                signature=signature)

    @classmethod
    def verify_wait_certificate(cls, certificate, poet_public_key):
        # TODO - implement PoET 1 create certificate logic
        # return \
        #     pybitcointools.ecdsa_verify(
        #         certificate.serialize(),
        #         certificate.signature,
        #         poet_public_key)

        return True


def initialize(**kwargs):
    pass


def create_signup_info(originator_id):
    return _PoetEnclaveSimulator.create_signup_info(originator_id)


def unseal_signup_data(sealed_signup_data):
    return _PoetEnclaveSimulator.unseal_signup_data(sealed_signup_data)


def verify_signup_info(serialized_signup_info):
    return _PoetEnclaveSimulator.verify_signup_info(serialized_signup_info)


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
    return timer.is_expired()


def create_wait_certificate(timer, block_digest):
    return \
        _PoetEnclaveSimulator.create_wait_certificate(
            timer=timer,
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
