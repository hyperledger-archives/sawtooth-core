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

""" Sawtooth Signing API

    This module provides an interface to signing operations that insulates
    the caller from decisions on the underlying crypto system.
    All keys are returned as serialized strings.
    All methods expect that serialized format.

    Basic Usage:
        import sawtooth_signing as signing

        msg = 'this is a message'
        priv = signing.generate_privkey()
        pub = signing.generate_pubkey(priv)
        sig = signing.sign(msg, priv)
        ver = signing.verify(msg, sig, pub)

        # Store Private Key
        keyfile = open(filename, 'w')
        keyfile.write(priv)
        keyfile.close()

        # Retrieve Private Key
        keyfile = open(filename, 'r')
        priv = keyfile.readline()

    As new crypto packages are implemented this package serves as a build
    time switch to select the crypto package for that sawtooth network.

    For example 'from ed25519_signer import *' would change sawtooth's
    crypto selection without requiring changes to the API consumers.
"""
# pylint: disable=wildcard-import
from sawtooth_signing.secp256k1_signer import *
