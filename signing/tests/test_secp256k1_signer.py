# Copyright 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import unittest

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_signing import ParseError
from sawtooth_signing.secp256k1 import Secp256k1PrivateKey
from sawtooth_signing.secp256k1 import Secp256k1PublicKey


KEY1_PRIV_HEX = \
    "2f1e7b7a130d7ba9da0068b3bb0ba1d79e7e77110302c9f746c3c2a63fe40088"
KEY1_PUB_HEX = \
    "026a2c795a9776f75464aa3bda3534c3154a6e91b357b1181d3f515110f84b67c5"

KEY2_PRIV_HEX = \
    "51b845c2cdde22fe646148f0b51eaf5feec8c82ee921d5e0cbe7619f3bb9c62d"
KEY2_PUB_HEX = \
    "039c20a66b4ec7995391dbec1d8bb0e2c6e6fd63cd259ed5b877cb4ea98858cf6d"

MSG1 = "test"
MSG1_KEY1_SIG = ("5195115d9be2547b720ee74c23dd841842875db6eae1f5da8605b050a49e"
                 "702b4aa83be72ab7e3cb20f17c657011b49f4c8632be2745ba4de79e6aa0"
                 "5da57b35")

MSG2 = "test2"
MSG2_KEY2_SIG = ("d589c7b1fa5f8a4c5a389de80ae9582c2f7f2a5e21bab5450b670214e5b1"
                 "c1235e9eb8102fd0ca690a8b42e2c406a682bd57f6daf6e142e5fa4b2c26"
                 "ef40a490")


class Secp256k1SigningTest(unittest.TestCase):
    def test_hex_key(self):
        priv_key = Secp256k1PrivateKey.from_hex(KEY1_PRIV_HEX)
        self.assertEqual(priv_key.get_algorithm_name(), "secp256k1")
        self.assertEqual(priv_key.as_hex(), KEY1_PRIV_HEX)

        pub_key = Secp256k1PublicKey.from_hex(KEY1_PUB_HEX)
        self.assertEqual(pub_key.get_algorithm_name(), "secp256k1")
        self.assertEqual(pub_key.as_hex(), KEY1_PUB_HEX)

    def test_priv_to_public_key(self):
        context = create_context("secp256k1")
        self.assertEqual(context.get_algorithm_name(), "secp256k1")

        priv_key1 = Secp256k1PrivateKey.from_hex(KEY1_PRIV_HEX)
        self.assertEqual(priv_key1.get_algorithm_name(), "secp256k1")
        self.assertEqual(priv_key1.as_hex(), KEY1_PRIV_HEX)

        public_key1 = context.get_public_key(priv_key1)
        self.assertEqual(public_key1.as_hex(), KEY1_PUB_HEX)

        priv_key2 = Secp256k1PrivateKey.from_hex(KEY2_PRIV_HEX)
        self.assertEqual(priv_key2.get_algorithm_name(), "secp256k1")
        self.assertEqual(priv_key2.as_hex(), KEY2_PRIV_HEX)

        public_key2 = context.get_public_key(priv_key2)
        self.assertEqual(public_key2.as_hex(), KEY2_PUB_HEX)

    def test_check_invalid_digit(self):
        priv_chars = list(KEY1_PRIV_HEX)
        priv_chars[3] = 'i'
        with self.assertRaises(ParseError):
            Secp256k1PrivateKey.from_hex(''.join(priv_chars))

        pub_chars = list(KEY1_PUB_HEX)
        pub_chars[3] = 'i'
        with self.assertRaises(ParseError):
            Secp256k1PublicKey.from_hex(''.join(pub_chars))

    def test_single_key_signing(self):
        context = create_context("secp256k1")
        self.assertEqual(context.get_algorithm_name(), "secp256k1")

        factory = CryptoFactory(context)
        self.assertEqual(factory.context.get_algorithm_name(),
                         "secp256k1")

        priv_key = Secp256k1PrivateKey.from_hex(KEY1_PRIV_HEX)
        self.assertEqual(priv_key.get_algorithm_name(), "secp256k1")
        self.assertEqual(priv_key.as_hex(), KEY1_PRIV_HEX)

        signer = factory.new_signer(priv_key)
        signature = signer.sign(MSG1.encode())
        self.assertEqual(signature, MSG1_KEY1_SIG)

    def test_many_key_signing(self):
        context = create_context("secp256k1")
        self.assertEqual(context.get_algorithm_name(), "secp256k1")

        priv_key1 = Secp256k1PrivateKey.from_hex(KEY1_PRIV_HEX)
        self.assertEqual(priv_key1.get_algorithm_name(), "secp256k1")
        self.assertEqual(priv_key1.as_hex(), KEY1_PRIV_HEX)

        priv_key2 = Secp256k1PrivateKey.from_hex(KEY2_PRIV_HEX)
        self.assertEqual(priv_key2.get_algorithm_name(), "secp256k1")
        self.assertEqual(priv_key2.as_hex(), KEY2_PRIV_HEX)

        signature = context.sign(
            MSG1.encode(),
            priv_key1)
        self.assertEqual(signature, MSG1_KEY1_SIG)

        signature = context.sign(
            MSG2.encode(),
            priv_key2)
        self.assertEqual(signature, MSG2_KEY2_SIG)

    def test_verification(self):
        context = create_context("secp256k1")
        self.assertEqual(context.get_algorithm_name(), "secp256k1")

        pub_key1 = Secp256k1PublicKey.from_hex(KEY1_PUB_HEX)
        self.assertEqual(pub_key1.get_algorithm_name(), "secp256k1")
        self.assertEqual(pub_key1.as_hex(), KEY1_PUB_HEX)

        result = context.verify(MSG1_KEY1_SIG, MSG1.encode(), pub_key1)
        self.assertEqual(result, True)

    def test_verification_error(self):
        context = create_context("secp256k1")
        self.assertEqual(context.get_algorithm_name(), "secp256k1")

        pub_key1 = Secp256k1PublicKey.from_hex(KEY1_PUB_HEX)
        self.assertEqual(pub_key1.get_algorithm_name(), "secp256k1")
        self.assertEqual(pub_key1.as_hex(), KEY1_PUB_HEX)

        # This signature doesn't match for MSG1/KEY1
        result = context.verify(MSG2_KEY2_SIG, MSG1.encode(), pub_key1)
        self.assertEqual(result, False)
