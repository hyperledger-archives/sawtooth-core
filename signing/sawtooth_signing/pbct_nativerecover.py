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

import pybitcointools
import random
import string
import logging
from ECDSA import ECDSARecoverModule as nativeECDSA

logger = logging.getLogger(__name__)


def wif_to_privkey(wifstr):
    return pybitcointools.decode_privkey(wifstr, 'wif')


def generate_privkey():
    return pybitcointools.random_key()


def encode_privkey(privkey, format='wif'):
    return pybitcointools.encode_privkey(privkey, format)


def decode_privkey(privkey, format='wif'):
    return pybitcointools.decode_privkey(privkey, format)


def generate_pubkey(privkey):
    return pybitcointools.privtopub(privkey)


def encode_pubkey(pubkey, format):
    return pybitcointools.encode_pubkey(pubkey, format)


def decode_pubkey(pubkey, format):
    return pybitcointools.decode_pubkey(pubkey, format)


def generate_identifier(pubkey):
    return pybitcointools.pubtoaddr(pubkey)


def sign(message, privkey):
    return pybitcointools.ecdsa_sign(message, privkey)


def verify(message, signature, pubkey):
    return pybitcointools.ecdsa_verify(message, signature, pubkey)


def recover_pubkey(message, signature):
    v, r, s = pybitcointools.decode_sig(signature)
    msghash = pybitcointools.electrum_sig_hash(message)
    z = pybitcointools.hash_to_int(msghash)

    compress = True if v >= 31 else False

    if compress:
        rec = v - 31
    else:
        rec = v - 27

    try:
        pubkey = nativeECDSA.recover_pubkey(
            str(z), str(r), str(s), int(rec))
    except Exception as ex:
        logger.warn('Unable to extract public key from signature' + ex.args[0])
        return ""

    pubkey = pubkey.translate(None, 'h')
    pubkey = '04' + pubkey

    if compress:
        pubkey = pybitcointools.compress(pubkey)

    return pubkey
