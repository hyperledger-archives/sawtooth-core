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
__CONTEXTBASE__ = secp256k1.Base(ctx=None, flags=secp256k1.ALL_FLAGS)
__CTX__ = __CONTEXTBASE__.ctx


def generate_privkey():
    return _encode_privkey(secp256k1.PrivateKey(ctx=__CTX__))


def encode_privkey(privkey, encoding_format='wif'):
    """Encodes a provided wif encoded privkey in the requested
    encoding format.

    Args:
        privkey (str): A wif-encoded private key string
        encoding_format (str): One of the pybitcointools supported
            encoding formats

    Returns:
        str: An encoded private key in the requested format
    """
    return _encode_privkey(_decode_privkey(privkey, 'wif'),
                           encoding_format)


def _encode_privkey(privkey, encoding_format='wif'):
    try:  # check python3
        priv = int.from_bytes(privkey.private_key, byteorder='big')
    except AttributeError:
        priv = binascii.hexlify(privkey.private_key)

    encoded = pybitcointools.encode_privkey(priv, encoding_format)

    return encoded


def _decode_privkey_to_bytes(encoded_privkey, encoding_format='wif'):
    """
    Args:
        encoded_privkey: an encoded private key string
        encoding_format: string indicating format such as 'wif'

    Returns:
        priv (bytes): bytes representation of the private key
    """
    if encoding_format == 'wif':
        # int to hex string
        priv = pybitcointools.encode_privkey(encoded_privkey, 'hex')
        # hex string to bytes
        try:  # check python 3
            priv = priv.to_bytes(32, byteorder='big')
        except AttributeError:
            priv = binascii.unhexlify(priv)
    elif encoding_format == 'hex':
        try:
            priv = encoded_privkey.to_bytes(32, byteorder='big')
        except AttributeError:
            priv = binascii.unhexlify(encoded_privkey)
    else:
        raise TypeError("unsupported private key format")

    return priv


def decode_privkey(encoded_privkey, encoding_format='wif'):
    """Decodes a provided encoded privkey to a secp256k1 bytes representation

    Args:
        encoded_privkey (str): An encoded private key string
        encoding_format (str): The encoded format of the provided
            private key. Must be either 'wif' or 'hex'.

    Returns:
        bytes: A private key in native bytes format
    """
    return _decode_privkey_to_bytes(encoded_privkey, encoding_format)


def _decode_privkey(encoded_privkey, encoding_format='wif'):
    """
    Args:
        encoded_privkey: an encoded private key string
        encoding_format: string indicating format such as 'wif'

    Returns:
        private key object useable with this module
    """
    priv = _decode_privkey_to_bytes(encoded_privkey, encoding_format)
    return secp256k1.PrivateKey(priv, ctx=__CTX__)


def generate_pubkey(privkey):
    """
    Args:
        privkey: a serialized private key string
    Returns:
        pubkey: a serialized public key string
     """
    return _encode_pubkey(_decode_privkey(privkey).pubkey, 'hex')


def encode_pubkey(pubkey, encoding_format='hex'):
    """Encodes a provided encoded pubkey to a supported encoding_format

    Args:
        pubkey (str): An encoded public key string
        encoding_format (str): The encoded format of the provided
            private key. Must be 'hex'.

    Returns:
        str: A public key in the requested format
    """
    return _encode_pubkey(_decode_pubkey(pubkey, encoding_format),
                          encoding_format)


def _encode_pubkey(pubkey, encoding_format='hex'):
    with warnings.catch_warnings() as enc:  # squelch secp256k1 warning
        warnings.simplefilter('ignore')
        enc = pubkey.serialize()
    if encoding_format == 'hex':
        enc = binascii.hexlify(enc).decode()
    elif encoding_format != 'bytes':
        raise ValueError("Unrecognized pubkey encoding format")
    return enc


def decode_pubkey(serialized_pubkey, encoding_format='hex'):
    """Decodes a provided public key into the requested format

    Args:
        serialized_pubkey (str): The encoded public key
        encoding_format (str): The format of the provided encoded
            public key. Must be 'hex'.

    Returns:
        bytes: The native bytes representation of the public key
    """
    if encoding_format == 'hex':
        serialized_pubkey = binascii.unhexlify(serialized_pubkey)
    else:
        raise ValueError("Unrecognized pubkey encoding format")

    return serialized_pubkey


def _decode_pubkey(serialized_pubkey, encoding_format='hex'):
    if encoding_format == 'hex':
        serialized_pubkey = binascii.unhexlify(serialized_pubkey)
    elif encoding_format != 'bytes':
        raise ValueError("Unrecognized pubkey encoding format")
    pub = secp256k1.PrivateKey(
        ctx=__CTX__).pubkey.deserialize(serialized_pubkey)
    return secp256k1.PublicKey(pub, ctx=__CTX__)


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
    verified = False
    try:
        pubkey = _decode_pubkey(pubkey, 'hex')
        if isinstance(message, str):
            message = message.encode('utf-8')
        try:  # check python3
            signature = bytes.fromhex(signature)
        except (ValueError, AttributeError):
            signature = binascii.unhexlify(signature)

        sig = pubkey.ecdsa_deserialize_compact(signature)
        verified = pubkey.ecdsa_verify(message, sig)

    # Fail Securely (even if it's not pythonic)
    # pylint: disable=broad-except
    except Exception:
        return False
    return verified


def recover_pubkey(message, signature):
    """
    No support yet for recoverable signatures.
    """

    raise NotImplementedError("Public key recovery is not yet supported.")
    # return pubkey
