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

import logging
import binascii
import warnings
import hashlib
import secp256k1

try:
    # Python 2
    import pybitcointools
except ImportError:
    # Python 3
    import bitcoin as pybitcointools


LOGGER = logging.getLogger(__name__)


def generate_privkey():
    return secp256k1.PrivateKey()


def encode_privkey(privkey, encoding_format='wif'):
    try:  # check python3
        priv = int.from_bytes(privkey.private_key, byteorder='big')
    except AttributeError:
        priv = binascii.hexlify(privkey.private_key)
    return pybitcointools.encode_privkey(priv, encoding_format)


def decode_privkey(encoded_privkey, encoding_format='wif'):
    """
    Args:
        encoded_privkey: an encoded private key string
        encoding_format: string indicating format such as 'wif'

    Returns:
        private key object useable with this module
    """
    if encoding_format == 'wif':
        # base58 to int
        priv = pybitcointools.decode_privkey(encoded_privkey, encoding_format)
        # int to hex string
        priv = pybitcointools.encode_privkey(priv, 'hex')
        # hex string to bytes
        try:  # check python 3
            priv = priv.to_bytes(32, byteorder='big')
        except AttributeError:
            priv = binascii.unhexlify(priv)
    else:
        raise TypeError("unsupported private key format")

    return secp256k1.PrivateKey(priv)


def generate_pubkey(privkey):
    """ Expects a private key object created by this module """
    return privkey.pubkey


def encode_pubkey(pubkey, encoding_format=''):
    with warnings.catch_warnings() as enc:  # squelch secp256k1 warning
        warnings.simplefilter('ignore')
        enc = pubkey.serialize()
    if encoding_format == 'hex':
        enc = binascii.hexlify(enc).decode()
    elif encoding_format != '':
        raise ValueError("Unrecognized pubkey encoding format")
    return enc


def decode_pubkey(serialized_pubkey, encoding_format=''):
    if encoding_format == 'hex':
        serialized_pubkey = bytes.fromhex(serialized_pubkey)
    elif encoding_format != '':
        raise ValueError("Unrecognized pubkey encoding format")
    pub = secp256k1.PrivateKey().pubkey.deserialize(serialized_pubkey)
    return secp256k1.PublicKey(pub)


def generate_identifier(pubkey):
    """
    Args:
        pubkey: a public key object produced by this module

    Returns:
        Returns a 32 byte identifier
    """
    s = ''
    for i in range(len(pubkey.public_key.data)):
        s += pubkey.public_key.data[i]
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def sign(message, privkey):
    """
    Args:
        message: Message string
        privkey: a private key object created by this module

    Returns:
        A DER encoded compact signature
    """
    sig = privkey.ecdsa_sign(message.encode('utf-8'))
    sig = privkey.ecdsa_serialize_compact(sig)
    try:  # check python3
        sig = sig.hex()
    except AttributeError:
        sig = binascii.hexlify(sig)
    return sig


def verify(message, signature, pubkey):
    """
    Args:
        message: Message string
        signature: DER encoded compact signature
        pubkey: Public Key object

    Returns:
        boolean True / False
    """

    try:  # check python3
        signature = bytes.fromhex(signature)
    except (ValueError, AttributeError):
        signature = binascii.unhexlify(signature)
    sig = secp256k1.PrivateKey().ecdsa_deserialize_compact(signature)
    return pubkey.ecdsa_verify(message.encode('utf-8'), sig)


def recover_pubkey(message, signature):
    """
    No support yet for recoverable signatures.
    """

    raise NotImplementedError("Public key recovery is not yet supported.")
    # return pubkey
