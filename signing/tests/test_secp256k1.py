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
        """
        Test basic key gen, sign, verify
        """
        msg = "this is a message"
        priv = signer.generate_privkey()
        pub = signer.generate_pubkey(priv)
        sig = signer.sign(msg, priv)
        ver = signer.verify(msg, sig, pub)
        self.assertTrue(ver)

    def test_serialized_ops(self):
        msg = "this is a message"
        priv = signer.generate_privkey()
        priv_ser = signer.encode_privkey(priv)
        priv = signer.decode_privkey(priv_ser)

        pub = signer.generate_pubkey(priv)
        pub_ser = signer.encode_pubkey(pub)
        pub = signer.decode_pubkey(pub_ser)

        sig = signer.sign(msg, priv)
        ver = signer.verify(msg, sig, pub)
        self.assertTrue(ver)

if __name__ == '__main__':
    unittest.main()
