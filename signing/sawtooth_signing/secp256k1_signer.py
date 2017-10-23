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
__PK__ = secp256k1.PublicKey(ctx=__CTX__)  # Cache object to use as factory


def generate_private_key(private_key_format='wif'):
    """ Create a random private key
    Args:
        private_key_format: the format to export the key ('wif', 'hex', or
        'bytes')
    Returns:
        Serialized private key suitable for subsequent calls to e.g. sign().
    """
    return _encode_private_key(
        secp256k1.PrivateKey(ctx=__CTX__), private_key_format)


def _encode_private_key(private_key, encoding_format='wif'):
    if encoding_format == 'bytes':
        return private_key.private_key

    try:  # check python3
        priv = int.from_bytes(private_key.private_key, byteorder='big')
    except AttributeError:
        priv = binascii.hexlify(private_key.private_key)

    encoded = pybitcointools.encode_privkey(priv, encoding_format)

    return encoded


def _decode_private_key(encoded_private_key, encoding_format='wif'):
    """
    Args:
        encoded_private_key: an encoded private key string
        encoding_format: string indicating format such as 'wif'

    Returns:
        priv (bytes): bytes representation of the private key
    """
    if encoding_format == 'wif':
        # int to hex string
        priv = pybitcointools.encode_privkey(encoded_private_key, 'hex')
        # hex string to bytes
        try:  # check python 3
            priv = priv.to_bytes(32, byteorder='big')
        except AttributeError:
            priv = binascii.unhexlify(priv)
    elif encoding_format == 'hex':
        try:
            priv = encoded_private_key.to_bytes(32, byteorder='big')
        except AttributeError:
            priv = binascii.unhexlify(encoded_private_key)
    elif encoding_format == 'bytes':
        priv = encoded_private_key
    else:
        raise TypeError("unsupported private key format")

    return secp256k1.PrivateKey(priv, ctx=__CTX__)


def generate_public_key(private_key, private_key_format='wif'):
    """ Generate the public key based on a given private key
    Args:
        private_key: a serialized private key string
        private_key_format: the format of the private_key ('wif', 'hex', or
            'bytes')
    Returns:
        public_key: a serialized public key string
     """
    return _encode_public_key(
        _decode_private_key(private_key, private_key_format).pubkey, 'hex')


def _encode_public_key(public_key, encoding_format='hex'):
    with warnings.catch_warnings() as enc:  # squelch secp256k1 warning
        warnings.simplefilter('ignore')
        enc = public_key.serialize()
    if encoding_format == 'hex':
        enc = binascii.hexlify(enc).decode()
    elif encoding_format != 'bytes':
        raise ValueError("Unrecognized public_key encoding format")
    return enc


def _decode_public_key(serialized_public_key, encoding_format='hex'):
    if encoding_format == 'hex':
        serialized_public_key = binascii.unhexlify(serialized_public_key)
    elif encoding_format != 'bytes':
        raise ValueError("Unrecognized public_key encoding format")
    pub = __PK__.deserialize(serialized_public_key)
    return secp256k1.PublicKey(pub, ctx=__CTX__)


def generate_identifier(public_key):
    """ Generate an identifier based on the public key
    Args:
        public_key: a serialized public key string

    Returns:
        Returns a 32 byte identifier
    """
    return hashlib.sha256(public_key.encode('utf-8')).hexdigest()


def sign(message, private_key, private_key_format='wif'):
    """ Signs a message using the specified private key
    Args:
        message: Message string
        private_key: A serialized private key string
        private_key_format: the format of the private_key ('wif', 'hex', or
            'bytes')

    Returns:
        A compact signature (64 byte concatenation of R and S)
    """
    private_key = _decode_private_key(private_key, private_key_format)
    if isinstance(message, str):
        message = message.encode('utf-8')
    sig = private_key.ecdsa_sign(message)
    sig = private_key.ecdsa_serialize_compact(sig)
    try:  # check python3
        sig = sig.hex()
    except AttributeError:
        sig = binascii.hexlify(sig)
    return sig


def verify(message, signature, public_key):
    """ Verification of signature based on message and public_key
    Args:
        message: Message string
        signature: A 64 byte compact signature
        public_key: A serialized Public Key string

    Returns:
        boolean True / False
    """
    verified = False
    try:
        public_key = _decode_public_key(public_key, 'hex')
        if isinstance(message, str):
            message = message.encode('utf-8')
        try:  # check python3
            signature = bytes.fromhex(signature)
        except (ValueError, AttributeError):
            signature = binascii.unhexlify(signature)

        sig = public_key.ecdsa_deserialize_compact(signature)
        verified = public_key.ecdsa_verify(message, sig)

    # Fail Securely (even if it's not pythonic)
    # pylint: disable=broad-except
    except Exception:
        return False
    return verified


def recover_public_key(message, signature):
    """
    No support yet for recoverable signatures.
    """

    raise NotImplementedError("Public key recovery is not yet supported.")
    # return public_key
