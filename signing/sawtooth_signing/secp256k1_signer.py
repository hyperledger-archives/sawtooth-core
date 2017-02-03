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
    return _encode_privkey(secp256k1.PrivateKey())


def _encode_privkey(privkey, encoding_format='wif'):
    try:  # check python3
        priv = int.from_bytes(privkey.private_key, byteorder='big')
    except AttributeError:
        priv = binascii.hexlify(privkey.private_key)
    return pybitcointools.encode_privkey(priv, encoding_format)


def _decode_privkey(encoded_privkey, encoding_format='wif'):
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
    """
    Args:
        privkey: a serialized private key string
    Returns:
        pubkey: a serialized public key string
     """
    return _encode_pubkey(_decode_privkey(privkey).pubkey, 'hex')


def _encode_pubkey(pubkey, encoding_format='hex'):
    with warnings.catch_warnings() as enc:  # squelch secp256k1 warning
        warnings.simplefilter('ignore')
        enc = pubkey.serialize()
    if encoding_format == 'hex':
        enc = binascii.hexlify(enc).decode()
    elif encoding_format != 'bytes':
        raise ValueError("Unrecognized pubkey encoding format")
    return enc


def _decode_pubkey(serialized_pubkey, encoding_format='hex'):
    if encoding_format == 'hex':
        serialized_pubkey = binascii.unhexlify(serialized_pubkey)
    elif encoding_format != 'bytes':
        raise ValueError("Unrecognized pubkey encoding format")
    pub = secp256k1.PrivateKey().pubkey.deserialize(serialized_pubkey)
    return secp256k1.PublicKey(pub)


def generate_identifier(pubkey):
    """
    Args:
        pubkey: a serialized public key string

    Returns:
        Returns a 32 byte identifier
    """
    return hashlib.sha256(pubkey.encode('utf-8')).hexdigest()


def sign(message, privkey):
    """
    Args:
        message: Message string
        privkey: A serialized private key string

    Returns:
        A DER encoded compact signature
    """
    privkey = _decode_privkey(privkey)
    if isinstance(message, str):
        message = message.encode('utf-8')
    sig = privkey.ecdsa_sign(message)
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
        pubkey: A serialized Public Key string

    Returns:
        boolean True / False
    """
    pubkey = _decode_pubkey(pubkey, 'hex')
    if isinstance(message, str):
        message = message.encode('utf-8')
    try:  # check python3
        signature = bytes.fromhex(signature)
    except (ValueError, AttributeError):
        signature = binascii.unhexlify(signature)
    sig = secp256k1.PrivateKey().ecdsa_deserialize_compact(signature)
    return pubkey.ecdsa_verify(message, sig)


def recover_pubkey(message, signature):
    """
    No support yet for recoverable signatures.
    """

    raise NotImplementedError("Public key recovery is not yet supported.")
    # return pubkey
