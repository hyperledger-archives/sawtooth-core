# Copyright 2016, 2017 Intel Corporation
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
import os

import toml

from cryptography.hazmat import backends
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from sawtooth_signing import create_context
from sawtooth_signing import ParseError
from sawtooth_signing.secp256k1 import Secp256k1PrivateKey
from sawtooth_signing.secp256k1 import Secp256k1PublicKey

from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER

from sawtooth_poet_common import sgx_structs

from sawtooth_poet_simulator.poet_enclave_simulator.utils import json2dict
from sawtooth_poet_simulator.poet_enclave_simulator.utils import dict2json

from sawtooth_poet_simulator.poet_enclave_simulator.enclave_signup_info \
    import EnclaveSignupInfo
from sawtooth_poet_simulator.poet_enclave_simulator.enclave_wait_timer \
    import EnclaveWaitTimer
from sawtooth_poet_simulator.poet_enclave_simulator.enclave_wait_certificate \
    import EnclaveWaitCertificate

LOGGER = logging.getLogger(__name__)

TIMER_TIMEOUT_PERIOD = 30.0


class _PoetEnclaveSimulator(object):
    # A lock to protect threaded access
    _lock = threading.Lock()

    # The private key we generate to sign the certificate ID when creating
    # the random wait timeout value
    _context = create_context('secp256k1')
    _seal_private_key = Secp256k1PrivateKey.new_random()

    # The basename and enclave measurement values we will put into and verify
    # are in the enclave quote in the attestation verification report.
    __VALID_BASENAME__ = \
        bytes.fromhex(
            'b785c58b77152cbe7fd55ee3851c4990'
            '00000000000000000000000000000000')
    __VALID_ENCLAVE_MEASUREMENT__ = \
        bytes.fromhex(
            'c99f21955e38dbb03d2ca838d3af6e43'
            'ef438926ed02db4cc729380c8c7a174e')

    # We use the report private key PEM to create the private key used to
    # sign attestation verification reports.  On the flip side, the report
    # public key PEM is used to create the public key used to verify the
    # signature on the attestation verification reports.
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

    _report_private_key = \
        serialization.load_pem_private_key(
            __REPORT_PRIVATE_KEY_PEM__.encode(),
            password=None,
            backend=backends.default_backend())

    # The anti-sybil ID for this particular validator.  This will get set when
    # the enclave is initialized
    _anti_sybil_id = None

    MINIMUM_WAIT_TIME = 1.0

    @classmethod
    def initialize(cls, config_dir, data_dir):
        # See if our configuration file exists.  If so, then we are going to
        # see if there is a configuration value for the validator ID.  If so,
        # then we'll use that when constructing the simulated anti-Sybil ID.
        # Otherwise, we are going to fall back on trying to create one that is
        # unique.
        validator_id = datetime.datetime.now().isoformat()

        config_file = os.path.join(config_dir, 'poet_enclave_simulator.toml')
        if os.path.exists(config_file):
            LOGGER.info(
                'Loading PoET enclave simulator config from : %s',
                config_file)

            try:
                with open(config_file) as fd:
                    toml_config = toml.loads(fd.read())
            except IOError as e:
                LOGGER.info(
                    'Error loading PoET enclave simulator configuration: %s',
                    e)
                LOGGER.info('Continuing with default configuration')

            invalid_keys = set(toml_config.keys()).difference(['validator_id'])
            if invalid_keys:
                LOGGER.warning(
                    'Ignoring invalid keys in PoET enclave simulator config: '
                    '%s',
                    ', '.join(sorted(list(invalid_keys))))

            validator_id = toml_config.get('validator_id', validator_id)

        LOGGER.debug(
            'PoET enclave simulator creating anti-Sybil ID from: %s',
            validator_id)

        # Create an anti-Sybil ID that is unique for this validator
        cls._anti_sybil_id = hashlib.sha256(validator_id.encode()).hexdigest()

    @classmethod
    def shutdown(cls):
        pass

    @classmethod
    def get_enclave_measurement(cls):
        return cls.__VALID_ENCLAVE_MEASUREMENT__.hex()

    @classmethod
    def get_enclave_basename(cls):
        return cls.__VALID_BASENAME__.hex()

    @classmethod
    def create_signup_info(cls,
                           originator_public_key_hash,
                           nonce):
        with cls._lock:
            # First we need to create a public/private key pair for the PoET
            # enclave to use.
            # Counter ID is a placeholder for a hardware counter in a TEE.
            poet_private_key = Secp256k1PrivateKey.new_random()
            poet_public_key = \
                cls._context.get_public_key(poet_private_key)
            counter_id = None

            # Simulate sealing (encrypting) the signup data.
            signup_data = {
                'poet_private_key': poet_private_key.as_hex(),
                'poet_public_key': poet_public_key.as_hex(),
                'counter_id': counter_id
            }
            sealed_signup_data = \
                base64.b64encode(
                    dict2json(signup_data).encode()).decode('utf-8')

            # Build up a fake SGX quote containing:
            # 1. The basename
            # 2. The report body that contains:
            #    a. The enclave measurement
            #    b. The report data SHA256(SHA256(OPK)|PPK)
            sgx_basename = \
                sgx_structs.SgxBasename(name=cls.__VALID_BASENAME__)
            sgx_measurement = \
                sgx_structs.SgxMeasurement(
                    m=cls.__VALID_ENCLAVE_MEASUREMENT__)

            hash_input = \
                '{0}{1}'.format(
                    originator_public_key_hash.upper(),
                    poet_public_key.as_hex().upper()).encode()
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

            timestamp = datetime.datetime.now().isoformat()

            # Fake our "proof" data.
            verification_report = {
                'epidPseudonym': cls._anti_sybil_id,
                'id': base64.b64encode(
                    hashlib.sha256(
                        timestamp.encode()).hexdigest().encode()).decode(),
                'isvEnclaveQuoteStatus': 'OK',
                'isvEnclaveQuoteBody':
                    base64.b64encode(sgx_quote.serialize_to_bytes()).decode(),
                'pseManifestStatus': 'OK',
                'pseManifestHash':
                    hashlib.sha256(base64.b64decode(pse_manifest)).hexdigest(),
                'nonce': nonce,
                'timestamp': timestamp
            }

            # Serialize the verification report, sign it, and then put
            # in the proof data
            verification_report_json = dict2json(verification_report)
            signature = \
                cls._report_private_key.sign(
                    verification_report_json.encode(),
                    padding.PKCS1v15(),
                    hashes.SHA256())

            proof_data_dict = {
                'evidence_payload': {
                    'pse_manifest': pse_manifest.decode()
                },
                'verification_report': verification_report_json,
                'signature': base64.b64encode(signature).decode()
            }
            proof_data = dict2json(proof_data_dict)

            return \
                EnclaveSignupInfo(
                    poet_public_key=signup_data['poet_public_key'],
                    proof_data=proof_data,
                    anti_sybil_id=cls._anti_sybil_id,
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
        # Specifically, we will do a base 64 decode, which gives us JSON
        # we can convert back to a dictionary we can use to get the
        # data we need
        signup_data = \
            json2dict(base64.b64decode(sealed_signup_data.encode()).decode())
        return signup_data.get('poet_public_key')

    @classmethod
    def release_signup_data(cls, sealed_signup_data):
        """

        Args:
            sealed_signup_data: Sealed signup data that was returned
                previously in a EnclaveSignupInfo object from a call to
                create_signup_info
        """
        # This is a standin method to release enclave resources associated
        # with this signup. This is not currently relevant to the simulator
        # but it must match the interface with the HW enclave.
        pass

    @classmethod
    def create_wait_timer(cls,
                          sealed_signup_data,
                          validator_address,
                          previous_certificate_id,
                          local_mean):
        with cls._lock:
            # Extract keys from the 'sealed' signup data
            signup_data = \
                json2dict(
                    base64.b64decode(sealed_signup_data.encode()).decode())
            poet_private_key = signup_data['poet_private_key']

            if poet_private_key is None:
                raise \
                    ValueError(
                        'Invalid signup data. No poet private key.')

            try:
                poet_private_key = Secp256k1PrivateKey.from_hex(
                    poet_private_key)
            except ParseError:
                raise \
                    ValueError(
                        'Invalid signup data. Badly formatted poet key(s).')

            # In a TEE implementation we would increment the HW counter here.
            # We can't usefully simulate a HW counter though.

            # Create some value from the cert ID.  We are just going to use
            # the seal key to sign the cert ID.  We will then use the
            # low-order 64 bits to change that to a number [0, 1]
            tag = \
                base64.b64decode(
                    cls._context.sign(
                        previous_certificate_id.encode(),
                        cls._seal_private_key))

            tagd = float(struct.unpack('Q', tag[-8:])[0]) / (2**64 - 1)

            # Now compute the duration with a minimum wait time guaranteed
            duration = \
                _PoetEnclaveSimulator.MINIMUM_WAIT_TIME \
                - local_mean * math.log(tagd)

            # Create and sign the wait timer
            wait_timer = \
                EnclaveWaitTimer(
                    validator_address=validator_address,
                    duration=duration,
                    previous_certificate_id=previous_certificate_id,
                    local_mean=local_mean)
            wait_timer.signature = \
                cls._context.sign(
                    wait_timer.serialize().encode(),
                    poet_private_key)

            return wait_timer

    @classmethod
    def deserialize_wait_timer(cls, serialized_timer, signature):
        return \
            EnclaveWaitTimer.wait_timer_from_serialized(
                serialized_timer=serialized_timer,
                signature=signature)

    @classmethod
    def create_wait_certificate(cls,
                                sealed_signup_data,
                                wait_timer,
                                block_hash):
        with cls._lock:
            # Extract keys from the 'sealed' signup data
            if sealed_signup_data is None:
                raise ValueError('Sealed Signup Data is None')
            signup_data = \
                json2dict(
                    base64.b64decode(sealed_signup_data.encode()).decode())
            poet_private_key = signup_data['poet_private_key']
            poet_public_key = signup_data['poet_public_key']

            if poet_private_key is None or poet_public_key is None:
                raise \
                    ValueError(
                        'Invalid signup data. No poet key(s).')

            try:
                poet_public_key = Secp256k1PublicKey.from_hex(poet_public_key)
                poet_private_key = Secp256k1PrivateKey.from_hex(
                    poet_private_key)
            except ParseError:
                raise \
                    ValueError(
                        'Invalid signup data. Badly formatted poet key(s).')

            # Several criteria need to be met before we can create a wait
            # certificate:
            # 1. This signup data was used to sign this timer.
            #    i.e. the key sealed / unsealed by the TEE signed this
            #    wait timer.
            # 2. This timer has expired
            # 3. This timer has not timed out
            #
            # In a TEE implementation we would check HW counter agreement.
            # We can't usefully simulate a HW counter though.
            # i.e. wait_timer.counter_value == signup_data.counter.value

            #
            # Note - we make a concession for the genesis block (i.e., a wait
            # timer for which the previous certificate ID is the Null
            # identifier) in that we don't require the timer to have expired
            # and we don't worry about the timer having timed out.

            if wait_timer is None or \
                    not cls._context.verify(
                        wait_timer.signature,
                        wait_timer.serialize().encode(),
                        poet_public_key):
                raise \
                    ValueError(
                        'Validator is not using the current wait timer')

            is_not_genesis_block = \
                (wait_timer.previous_certificate_id != NULL_BLOCK_IDENTIFIER)

            now = time.time()
            expire_time = \
                wait_timer.request_time + \
                wait_timer.duration

            if is_not_genesis_block and now < expire_time:
                raise \
                    ValueError(
                        'Cannot create wait certificate because timer has '
                        'not expired')

            time_out_time = \
                wait_timer.request_time + \
                wait_timer.duration + \
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
                    'wait_timer_signature': wait_timer.signature,
                    'now': datetime.datetime.utcnow().isoformat()
                })
            nonce = hashlib.sha256(random_string.encode()).hexdigest()

            # First create a new enclave wait certificate using the data
            # provided and then sign the certificate with the PoET private key
            wait_certificate = \
                EnclaveWaitCertificate.wait_certificate_with_wait_timer(
                    wait_timer=wait_timer,
                    nonce=nonce,
                    block_hash=block_hash)
            wait_certificate.signature = \
                cls._context.sign(
                    wait_certificate.serialize().encode(),
                    poet_private_key)

            # In a TEE implementation we would increment the HW counter here
            # to prevent replay.
            # We can't usefully simulate a HW counter though.

            return wait_certificate

    @classmethod
    def deserialize_wait_certificate(cls, serialized_certificate, signature):
        return \
            EnclaveWaitCertificate.wait_certificate_from_serialized(
                serialized_certificate=serialized_certificate,
                signature=signature)

    @classmethod
    def verify_wait_certificate(cls, certificate, poet_public_key):
        # Since the signing module uses a hex-encoded string as the canonical
        # format for public keys and we should be handed a public key that was
        # part of signup information created by us, don't bother decoding
        # the public key.
        try:
            poet_public_key = Secp256k1PublicKey.from_hex(poet_public_key)
        except ParseError:
            raise \
                ValueError(
                    'Invalid signup data. Badly formatted poet key(s).')

        if not \
            cls._context.verify(
                certificate.signature,
                certificate.serialize().encode(),
                poet_public_key):
            raise ValueError('Wait certificate signature does not match')


def initialize(config_dir, data_dir):
    _PoetEnclaveSimulator.initialize(config_dir=config_dir, data_dir=data_dir)


def shutdown():
    _PoetEnclaveSimulator.shutdown()


def get_enclave_measurement():
    return _PoetEnclaveSimulator.get_enclave_measurement()


def get_enclave_basename():
    return _PoetEnclaveSimulator.get_enclave_basename()


def create_signup_info(originator_public_key_hash,
                       nonce):
    return \
        _PoetEnclaveSimulator.create_signup_info(
            originator_public_key_hash=originator_public_key_hash,
            nonce=nonce)


def deserialize_signup_info(serialized_signup_info):
    return _PoetEnclaveSimulator.deserialize_signup_info(
        serialized_signup_info=serialized_signup_info)


def unseal_signup_data(sealed_signup_data):
    return _PoetEnclaveSimulator.unseal_signup_data(sealed_signup_data)


def release_signup_data(sealed_signup_data):
    return _PoetEnclaveSimulator.release_signup_data(sealed_signup_data)


def create_wait_timer(sealed_signup_data,
                      validator_address,
                      previous_certificate_id,
                      local_mean):
    return \
        _PoetEnclaveSimulator.create_wait_timer(
            sealed_signup_data=sealed_signup_data,
            validator_address=validator_address,
            previous_certificate_id=previous_certificate_id,
            local_mean=local_mean)


def deserialize_wait_timer(serialized_timer, signature):
    return \
        _PoetEnclaveSimulator.deserialize_wait_timer(
            serialized_timer=serialized_timer,
            signature=signature)


def create_wait_certificate(sealed_signup_data, wait_timer, block_hash):
    return \
        _PoetEnclaveSimulator.create_wait_certificate(
            sealed_signup_data=sealed_signup_data,
            wait_timer=wait_timer,
            block_hash=block_hash)


def deserialize_wait_certificate(serialized_certificate, signature):
    return \
        _PoetEnclaveSimulator.deserialize_wait_certificate(
            serialized_certificate=serialized_certificate,
            signature=signature)


def verify_wait_certificate(certificate, poet_public_key):
    _PoetEnclaveSimulator.verify_wait_certificate(
        certificate=certificate,
        poet_public_key=poet_public_key)
