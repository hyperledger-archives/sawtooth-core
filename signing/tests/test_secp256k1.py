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


from sawtooth_signing import secp256k1_signer as signer


class TestSecp256kSigner(unittest.TestCase):
    def test_basic_ops(self):
        msg = 'this is a message'
        priv = signer.generate_privkey()
        pub = signer.generate_public_key(priv)
        sig = signer.sign(msg, priv)
        ver = signer.verify(msg, sig, pub)
        self.assertTrue(ver)

    def test_privkey_serialization(self):
        # pylint: disable=protected-access
        priv = signer.generate_privkey()
        priv2 = signer._encode_privkey(signer._decode_privkey(priv))
        self.assertTrue(priv == priv2)

    def test_privkey_deserialization(self):
        # pylint: disable=protected-access
        priv = '5KZeUdoHCRXxT3srGfkeXRNWCdn1XjzpJqFdNoehZ9gEEkLMKVD'
        priv2 = signer._encode_privkey(signer._decode_privkey(priv))
        self.assertTrue(priv == priv2)

    def test_public_key_serialization(self):
        # pylint: disable=protected-access
        priv = signer.generate_privkey()
        pub = signer.generate_public_key(priv)
        raw_pub = signer._decode_public_key(pub, 'hex')
        pub2 = signer._encode_public_key(raw_pub, 'hex')
        self.assertTrue(str(pub) == str(pub2))

    def test_invalid_signature(self):
        msg = "This is a message"
        priv = signer.generate_privkey()
        priv2 = signer.generate_privkey()
        sig = signer.sign(msg, priv)
        pub = signer.generate_public_key(priv2)
        ver = signer.verify(msg, sig, pub)
        self.assertFalse(ver)

if __name__ == '__main__':
    unittest.main()
