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

try:
    # Python 2
    import pybitcointools as pbt
except ImportError:
    # Python 3
    import bitcoin as pbt

import sawtooth_signing.ECDSA.ECDSARecoverModule as ecnative
from sawtooth_signing import pbct_nativerecover


class TestPKRecover(unittest.TestCase):
    def test_pbt_match(self):
        """
        Tests matching results between pybitcointools and native
        ECDSA key recovery
        """
        # This key has a small public key value which tests padding
        wifstr = '5JtMb6tmM9vT6QHyM7RR8pjMViqccukgMFNCPvG5xhLVf6CMoGx'
        priv = pbt.encode_privkey(pbt.decode_privkey(wifstr, 'wif'), 'hex')
        msg = 'foo'
        sig = pbt.ecdsa_sign(msg, priv)
        native_recovered = pbct_nativerecover.recover_pubkey(msg, sig)
        py_recovered = pbt.ecdsa_recover(msg, sig)
        self.assertEquals(native_recovered, py_recovered)

    def test_bulk_keymatch(self):
        """
        Tests key recovery over several keys
        """
        msg = 'foo'
        for _ in range(0, 20):
            priv = pbt.random_key()
            sig = pbt.ecdsa_sign(msg, priv)
            native_recovered = pbct_nativerecover.recover_pubkey(msg, sig)
            py_recovered = pbt.ecdsa_recover(msg, sig)
            self.assertEquals(native_recovered, py_recovered,
                              "Priv Key that failed: {}".format(priv))

    def test_compressed_keys(self):
        """
        Tests compressed key
        """
        msg = 'foo'
        priv = pbt.encode_privkey(pbt.random_key(), 'hex_compressed')
        sig = pbt.ecdsa_sign(msg, priv)
        # Force old pybitcointools to behave
        v, r, s = pbt.decode_sig(sig)
        if v < 31:
            v += 4
        sig = pbt.encode_sig(v, r, s)
        pub = pbt.compress(pbt.privtopub(priv))
        native_recovered = pbct_nativerecover.recover_pubkey(msg, sig)
        self.assertEquals(native_recovered, pub,
                          "Priv Key that failed: {}".format(priv))

    def test_exception_on_empty_param(self):
        """
        Tests Exception Handling
        Passes an empty string as an invalid argument to the native method
        """
        d = pbt.sha256('private key')
        msghash = pbt.electrum_sig_hash('test message')
        z = pbt.hash_to_int(msghash)
        v, _, s = pbt.ecdsa_raw_sign(msghash, d)
        y_bit = v - 27
        with self.assertRaises(ValueError) as context:
            _ = ecnative.recover_pubkey(
                str(z), str(""), str(s),
                int(y_bit))

        self.assertTrue('Empty string' in str(context.exception))

    def test_exception_on_bad_sig(self):
        """
        Tests Exception Handling
        Inputs an invalid number to the native method
        """
        d = pbt.sha256('private key')
        msghash = pbt.electrum_sig_hash('test message')
        z = pbt.hash_to_int(msghash)
        v, _, s = pbt.ecdsa_raw_sign(msghash, d)
        y_bit = v - 27
        badval = "58995174607243353628346858794753620798088291196940745194" \
            "58148184192713284575299999999999999h"
        with self.assertRaises(ValueError) as context:
            _ = ecnative.recover_pubkey(
                str(z), str(badval), str(s),
                int(y_bit))

        self.assertTrue('Invalid signature' in str(context.exception))

    def test_exception_on_bad_hash(self):
        """
        Tests Exception Handling
        Inputs an invalid (negative) hash value to the native method
        """
        d = pbt.sha256('private key')
        msghash = pbt.electrum_sig_hash('test message')
        z = -pbt.hash_to_int(msghash)
        v, r, s = pbt.ecdsa_raw_sign(msghash, d)
        y_bit = v - 27
        with self.assertRaises(ValueError) as context:
            _ = ecnative.recover_pubkey(
                str(z), str(r), str(s),
                int(y_bit))

        self.assertTrue('hash' in str(context.exception))

if __name__ == '__main__':
    unittest.main()
