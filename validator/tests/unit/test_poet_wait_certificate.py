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
import unittest

from utils import generate_certs, generate_txn_ids, random_name
from sawtooth_validator.consensus.poet0.wait_timer import WaitTimer
from sawtooth_validator.consensus.poet0.wait_certificate import WaitCertificate

from sawtooth_validator.consensus.poet0.poet_enclave_simulator \
    import poet0_enclave_simulator as pe_sim


class TestPoetWaitCertificate(unittest.TestCase):
    """ These are tests for the WaitCertificate class.
    This class mostly provides wrappers for the underlying
    enclave WaitCertificate, so we are just exercising all the
    functions not doing any in depth testing of class.
    """
    @classmethod
    def setUpClass(cls):
        args = {}
        pe_sim.initialize(**args)
        cls.default_target_wait_time = WaitTimer.target_wait_time
        WaitTimer.target_wait_time = 1  # change default
        WaitTimer.poet_enclave = pe_sim
        WaitCertificate.poet_enclave = pe_sim

    @classmethod
    def tearDownClass(cls):
        WaitTimer.target_wait_time = cls.default_target_wait_time

    def test_wait_certificate(self):
        addr = random_name(20)
        certs = generate_certs(WaitTimer.fixed_duration_blocks)
        txn_ids, block_hash = generate_txn_ids(10)

        wait_timer = WaitTimer.create_wait_timer(addr, certs)
        self.assertIsNotNone(wait_timer)
        while not wait_timer.is_expired(time.time()):
            time.sleep(1)

        wait_cert = WaitCertificate.create_wait_certificate(
            wait_timer,
            block_hash)
        self.assertIsNotNone(wait_cert)

        ewc = wait_cert.enclave_wait_certificate
        r = wait_cert.is_valid_wait_certificate(addr, certs, txn_ids)
        self.assertTrue(r)
        str(wait_cert)

        swc = WaitCertificate.deserialize_wait_certificate(
            wait_cert.serialized_cert,
            wait_cert.signature
        )
        self.assertEqual(wait_cert.previous_certificate_id,
                         swc.previous_certificate_id)
        self.assertEqual(wait_cert.local_mean, swc.local_mean)
        self.assertEqual(wait_cert.request_time, swc.request_time)
        self.assertEqual(wait_cert.duration, swc.duration)
        self.assertEqual(wait_cert.signature, swc.signature)
        self.assertEqual(wait_cert.identifier, swc.identifier)
        self.assertEqual(wait_cert.validator_address, swc.validator_address)
        self.assertEqual(wait_cert.block_hash, swc.block_hash)

        swc.is_valid_wait_certificate(addr, certs, txn_ids)
        dwc = wait_cert.dump()
        swc = WaitCertificate.deserialize_wait_certificate(
            dwc["SerializedCert"],
            dwc["Signature"]
        )
        swc.is_valid_wait_certificate(addr, certs, txn_ids)

        self.assertEqual(wait_cert.previous_certificate_id,
                         swc.previous_certificate_id)
        self.assertEqual(wait_cert.local_mean, swc.local_mean)
        self.assertEqual(wait_cert.request_time, swc.request_time)
        self.assertEqual(wait_cert.duration, swc.duration)
        self.assertEqual(wait_cert.signature, swc.signature)
        self.assertEqual(wait_cert.identifier, swc.identifier)
        self.assertEqual(wait_cert.validator_address, swc.validator_address)
        self.assertEqual(wait_cert.block_hash, swc.block_hash)

    def check_enclave_timer_tampering(self, wait_cert, oid, certs, txn_ids):
        # now we are going to tamper with the members of the enclave wait
        # timer object
        swc = wait_cert.serialized_cert
        ewt = wait_cert.enclave_wait_certificate

        d = ewt.duration
        ewt.duration = 0
        wait_cert.serialized_cert = ewt.serialize()
        r = wait_cert.is_valid_wait_certificate(oid, certs, txn_ids)
        self.assertFalse(r)
        ewt.duration = d

        lm = ewt.local_mean
        ewt.local_mean = wait_cert.local_mean - 1
        wait_cert.serialized_cert = ewt.serialize()
        r = wait_cert.is_valid_wait_certificate(oid, certs, txn_ids)
        self.assertFalse(r)
        ewt.local_mean = lm

        pc = wait_cert.previous_certificate_id
        ewt.previous_certificate_id = random_name(pe_sim.IDENTIFIER_LENGTH)
        ewt.serialized_cert = ewt.serialize()
        r = wait_cert.is_valid_wait_certificate(oid, certs, txn_ids)
        self.assertFalse(r)
        ewt.previous_certificate_id = pc

        # start up case, no previous certs and NULL_IDENTIFIER
        addr = random_name(20)
        block_hash = random_name(32)
        wait_timer = WaitTimer.create_wait_timer(addr, [])
        self.assertIsNotNone(wait_timer)
        wait_cert = WaitCertificate.create_wait_certificate(
            wait_timer,
            block_hash)
        self.assertIsNotNone(wait_cert)
        r = wait_cert.is_valid_wait_certificate(oid, [], txn_ids)
        self.assertTrue(r)

    def test_is_valid_wait_certificate(self):
        addr = random_name(20)
        certs = generate_certs(WaitTimer.fixed_duration_blocks)
        txn_ids, block_hash = generate_txn_ids(10)
        wait_timer = WaitTimer.create_wait_timer(addr, certs)
        self.assertIsNotNone(wait_timer)
        while not wait_timer.is_expired(time.time()):
            time.sleep(1)

        wait_cert = WaitCertificate.create_wait_certificate(
            wait_timer,
            block_hash)
        self.assertIsNotNone(wait_cert)
        r = wait_cert.is_valid_wait_certificate(addr, certs, txn_ids)
        self.assertTrue(r)

        # invalid list
        with self.assertRaises(TypeError) as context:
            wait_cert.is_valid_wait_certificate(None, certs, txn_ids)
        with self.assertRaises(TypeError) as context:
            wait_cert.is_valid_wait_certificate({}, certs, txn_ids)
        with self.assertRaises(TypeError) as context:
            wait_cert.is_valid_wait_certificate([], certs, txn_ids)
        with self.assertRaises(TypeError) as context:
            wait_cert.is_valid_wait_certificate(555, certs, txn_ids)

        with self.assertRaises(TypeError) as context:
            wait_cert.is_valid_wait_certificate(addr, None, txn_ids)
        with self.assertRaises(TypeError) as context:
            wait_cert.is_valid_wait_certificate(addr, "test", txn_ids)
        with self.assertRaises(TypeError) as context:
            wait_cert.is_valid_wait_certificate(addr, {}, txn_ids)
        with self.assertRaises(TypeError) as context:
            wait_cert.is_valid_wait_certificate(addr, 545, txn_ids)

        with self.assertRaises(TypeError) as context:
            wait_cert.is_valid_wait_certificate(addr, certs, None)
        with self.assertRaises(TypeError) as context:
            wait_cert.is_valid_wait_certificate(addr, certs, {})
        with self.assertRaises(TypeError) as context:
            wait_cert.is_valid_wait_certificate(addr, certs, "test")
        with self.assertRaises(TypeError) as context:
            wait_cert.is_valid_wait_certificate(addr, certs, 333)

    def test_is_valid_wait_certificate_2(self):
        addr = random_name(20)
        certs = generate_certs(WaitTimer.fixed_duration_blocks)
        txn_ids, block_hash = generate_txn_ids(10)
        wait_timer = WaitTimer.create_wait_timer(addr, certs)
        self.assertIsNotNone(wait_timer)
        while not wait_timer.is_expired(time.time()):
            time.sleep(1)

        wait_cert = WaitCertificate.create_wait_certificate(
            wait_timer,
            block_hash)
        self.assertIsNotNone(wait_cert)

        # Verify class changes don't affect validity
        d = wait_cert.duration
        wait_cert.duration = 0
        r = wait_cert.is_valid_wait_certificate(addr, certs, txn_ids)
        self.assertTrue(r)
        wait_cert.duration = d

        lm = wait_cert.local_mean
        wait_cert.local_mean = wait_cert.local_mean - 1
        r = wait_cert.is_valid_wait_certificate(addr, certs, txn_ids)
        self.assertTrue(r)
        wait_cert.local_mean = lm

        pc = wait_cert.previous_certificate_id
        wait_cert.previous_certificate_id = random_name(
            pe_sim.IDENTIFIER_LENGTH)
        r = wait_cert.is_valid_wait_certificate(addr, certs, txn_ids)
        self.assertTrue(r)
        wait_cert.previous_certificate_id = pc

        self.check_enclave_timer_tampering(wait_cert, addr, certs, txn_ids)

if __name__ == '__main__':
    unittest.main()
