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

import unittest

from sawtooth_signing import secp256k1_signer as signing
from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator.\
    enclave_wait_timer import EnclaveWaitTimer
from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator.\
    enclave_wait_certificate import EnclaveWaitCertificate


class TestEnclaveSimulatorWaitCertificate(unittest.TestCase):
    @classmethod
    def _create_random_key(cls):
        return signing.generate_privkey()

    def test_create_wait_certificate(self):
        wait_timer = \
            EnclaveWaitTimer(
                validator_address='1600 Pennsylvania Avenue NW',
                duration=3.14159,
                previous_certificate_id='Smart, Maxwell Smart',
                local_mean=2.71828)

        wait_certificate = \
            EnclaveWaitCertificate.wait_certificate_with_wait_timer(
                wait_timer=wait_timer,
                nonce='Eeny, meeny, miny, moe.',
                block_digest='Indigestion. Pepto Bismol.')

        self.assertAlmostEqual(
            wait_timer.request_time,
            wait_certificate.request_time)
        self.assertAlmostEqual(
            wait_timer.duration,
            wait_certificate.duration)
        self.assertEqual(
            wait_timer.previous_certificate_id,
            wait_certificate.previous_certificate_id)
        self.assertAlmostEqual(
            wait_timer.local_mean,
            wait_certificate.local_mean)
        self.assertEqual(
            wait_timer.validator_address,
            wait_certificate.validator_address)
        self.assertEqual(wait_certificate.nonce, 'Eeny, meeny, miny, moe.')
        self.assertEqual(
            wait_certificate.block_digest,
            'Indigestion. Pepto Bismol.')
        self.assertIsNone(wait_certificate.signature)

        # You probably wonder why I bother assigning
        # wait_certificate.previous_certificate_id  to a local variable -
        # this is to simply get around PEP8.
        # If I don't, it complains about the line being too long.
        # If I do a line continuation, it complains about a space around the =.
        previous_certificate_id = wait_certificate.previous_certificate_id
        other_wait_certificate = \
            EnclaveWaitCertificate(
                duration=wait_certificate.duration,
                previous_certificate_id=previous_certificate_id,
                local_mean=wait_certificate.local_mean,
                request_time=wait_certificate.request_time,
                validator_address='1600 Pennsylvania Avenue NW',
                nonce='Eeny, meeny, miny, moe.',
                block_digest=wait_certificate.block_digest)

        self.assertAlmostEqual(
            wait_certificate.duration,
            other_wait_certificate.duration)
        self.assertEqual(
            wait_certificate.previous_certificate_id,
            other_wait_certificate.previous_certificate_id)
        self.assertAlmostEqual(
            wait_certificate.local_mean,
            other_wait_certificate.local_mean)
        self.assertAlmostEqual(
            wait_certificate.request_time,
            other_wait_certificate.request_time)
        self.assertEqual(
            wait_certificate.validator_address,
            other_wait_certificate.validator_address)
        self.assertEqual(wait_certificate.nonce, other_wait_certificate.nonce)
        self.assertEqual(
            wait_certificate.block_digest,
            other_wait_certificate.block_digest)
        self.assertIsNone(other_wait_certificate.signature)

    def test_serialize_wait_certificate(self):
        wait_timer = \
            EnclaveWaitTimer(
                validator_address='1600 Pennsylvania Avenue NW',
                duration=3.14159,
                previous_certificate_id='Smart, Maxwell Smart',
                local_mean=2.71828)

        wait_certificate = \
            EnclaveWaitCertificate.wait_certificate_with_wait_timer(
                wait_timer=wait_timer,
                nonce='Eeny, meeny, miny, moe.',
                block_digest='Indigestion. Pepto Bismol.')

        self.assertIsNotNone(wait_certificate.serialize())

    def test_deserialized_wait_certificate(self):
        wait_timer = \
            EnclaveWaitTimer(
                validator_address='1600 Pennsylvania Avenue NW',
                duration=3.14159,
                previous_certificate_id='Smart, Maxwell Smart',
                local_mean=2.71828)

        wait_certificate = \
            EnclaveWaitCertificate.wait_certificate_with_wait_timer(
                wait_timer=wait_timer,
                nonce='Eeny, meeny, miny, moe.',
                block_digest='Indigestion. Pepto Bismol.')

        serialized = wait_certificate.serialize()
        signing_key = self._create_random_key()
        wait_certificate.signature = \
            signing.sign(serialized, signing_key)

        copy_wait_certificate = \
            EnclaveWaitCertificate.wait_certificate_from_serialized(
                serialized,
                wait_certificate.signature)

        self.assertAlmostEqual(
            wait_certificate.request_time,
            copy_wait_certificate.request_time)
        self.assertAlmostEqual(
            wait_certificate.duration,
            copy_wait_certificate.duration)
        self.assertEqual(
            wait_certificate.previous_certificate_id,
            copy_wait_certificate.previous_certificate_id)
        self.assertAlmostEqual(
            wait_certificate.local_mean,
            copy_wait_certificate.local_mean)
        self.assertEqual(
            wait_certificate.validator_address,
            copy_wait_certificate.validator_address)
        self.assertEqual(
            wait_certificate.nonce,
            copy_wait_certificate.nonce)
        self.assertEqual(
            wait_certificate.block_digest,
            copy_wait_certificate.block_digest)
        self.assertEqual(
            wait_certificate.signature,
            copy_wait_certificate.signature)

        self.assertEqual(serialized, copy_wait_certificate.serialize())
