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

"""
This module defines the SignedObject class which processes and validates
objects signed by a signing key.
"""

import hashlib
import logging

import pybitcointools

from gossip.ECDSA import ECDSARecoverModule as nativeECDSA
from gossip.common import dict2cbor

logger = logging.getLogger(__name__)


def generate_identifier(signingkey):
    """Generates encoded version of the public key associated with
    signingkey.

    Args:
        signingkey (str): A private key.

    Returns:
        str: An encoded 'address' associated with the public key.
    """
    return pybitcointools.pubtoaddr(pybitcointools.privtopub(signingkey))


def generate_signing_key(wifstr=None):
    """Returns a decoded signing key associated with wifstr or generates
    a random signing key.

    Args:
        wifstr (str): A private key in wif format.

    Returns:
        str: a signing key.
    """
    if wifstr:
        return pybitcointools.decode_privkey(wifstr, 'wif')

    return pybitcointools.random_key()


def get_verifying_key(serialized_msg, serialized_sig):
    """Attempts to recover a public key from a message and a signature.

    Args:
        serialized_msg (str): A serialized message.
        serialized_sig (str): A serialized signature.

    Returns:
        str: a public key.
    """
    v, r, s = pybitcointools.decode_sig(serialized_sig)
    msghash = pybitcointools.electrum_sig_hash(serialized_msg)
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
    pubkey = pubkey.translate(None,
                              'h')  # strip out hex indicators from opencpp
    pubkey = '04' + pubkey      # indicate uncompressed pubkey
    if compress:
        pubkey = pybitcointools.compress(pubkey)

    return pubkey


class SignedObject(object):
    """Implements a base class for processing & validating signed objects.

    Attributes:
        Signature (str): The signature used to sign the object.
        SignatureKey (str): The name of the key related to the signature.
            Used to build dict return types.

    """

    def __init__(self, minfo={}, signkey='Signature'):
        """Constructor for the SignedObject class.

        Args:
            minfo (dict): object data
            signkey (str): the field name for the signature within the
                object data
        """
        self.Signature = minfo.get(signkey)
        self.SignatureKey = signkey

        self._identifier = hashlib.sha256(self.Signature).hexdigest(
        ) if self.Signature else None
        self._originatorid = None
        self._verifyingkey = None

        self._data = None

    def __repr__(self):
        if not self._data:
            self._data = self.serialize()
        return self._data

    @property
    def Identifier(self):
        """Returns a unique identifier for the transaction.

        Note that the signature is really the only unique identifier,
        but the first 16 bytes should be sufficient for testing purposes.

        Returns:
            str: The first 16 characters of a sha256 hexdigest.
        """
        assert self.Signature

        if not self._identifier:
            self._identifier = hashlib.sha256(self.Signature).hexdigest()

        return self._identifier[:16]

    @property
    def OriginatorID(self):
        """Return the address of the object originator based on the
        verifying key derived from the object's signature.

        Returns:
            str: The address of the signer of the object.
        """
        assert self.Signature

        if not self._verifyingkey:
            serialized = self.serialize(signable=True)
            self._verifyingkey = get_verifying_key(serialized, self.Signature)
            self._originatorid = pybitcointools.pubtoaddr(self._verifyingkey)

        return self._originatorid

    def is_valid(self, store):
        """Determines if the signature on the object is valid.

        Args:
            store: Unused argument.

        Returns:
            bool: True if the signature on the object is valid, False
                otherwise.

        """
        return self.verify_signature()

    def verify_signature(self, originatorid=None):
        """Uses the signature to verify that a message came from an
        originator.

        Often this is simply used to initialize the originatorid field
        for the message.

        Args:
            originatorid (str): The address of the originator of the
                object.

        Returns:
            bool: True if the passed in originatorid is equal to the
                originator of the object OR if the originatorid passed
                in is None. False otherwise.
        """

        try:
            assert self.Signature

            if not self._verifyingkey:
                serialized = self.serialize(signable=True)
                self._verifyingkey = get_verifying_key(serialized,
                                                       self.Signature)
                self._originatorid = pybitcointools.pubtoaddr(
                    self._verifyingkey)

            return originatorid is None or self._originatorid == originatorid

        except:
            logger.exception('unable to verify transaction signature')
            return False

    def sign_from_node(self, node):
        """Generates the signature from the signing key stored in a node.

        Args:
            node (Node): The node providing the signing key.
        """
        assert node.SigningKey
        return self.sign_object(node.SigningKey)

    def sign_object(self, signingkey):
        """Generates a string signature for the object using the signing
        key.

        Args:
            signingkey (str): hex encoded private key
        """

        serialized = self.serialize(signable=True)
        self.Signature = pybitcointools.ecdsa_sign(serialized, signingkey)

        if not self._verifyingkey:
            self._verifyingkey = get_verifying_key(serialized, self.Signature)
            self._originatorid = pybitcointools.pubtoaddr(self._verifyingkey)

        self._identifier = hashlib.sha256(self.Signature).hexdigest()

    def serialize(self, signable=False):
        """Generates a CBOR serialized dict containing the a SignatureKey
        to Signature mapping.

        Args:
            signable (bool): if signable is True, self.SignatureKey is
                removed from the dict prior to serialization to CBOR.

        Returns:
            bytes: a CBOR representation of a SignatureKey to Signature
                mapping.
        """
        dump = self.dump()

        if signable and self.SignatureKey in dump:
            del dump[self.SignatureKey]

        return dict2cbor(dump)

    def dump(self):
        """Builds a dict containing a mapping of SignatureKey to Signature.

        Returns:
            dict: a map containing SignatureKey:Signature.
        """
        result = {self.SignatureKey: self.Signature}
        return result
