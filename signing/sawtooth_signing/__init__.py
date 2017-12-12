# Copyright 2016, 2017 Intel Corporation
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
from sawtooth_signing.core import NoSuchAlgorithmError
from sawtooth_signing.core import ParseError
from sawtooth_signing.core import SigningError

from sawtooth_signing.secp256k1 import Secp256k1Context


class Signer:
    """A convenient wrapper of Context and PrivateKey
    """

    def __init__(self, context, private_key):
        """
        """
        self._context = context
        self._private_key = private_key
        self._public_key = None

    def sign(self, message):
        """Signs the given message

        Args:
            message (bytes): the message bytes

        Returns:
            The signature in a hex-encoded string

        Raises:
            SigningError: if any error occurs during the signing process
        """
        return self._context.sign(message, self._private_key)

    def get_public_key(self):
        """Return the public key for this Signer instance.
        """
        # Lazy-eval the public key
        if self._public_key is None:
            self._public_key = self._context.get_public_key(self._private_key)
        return self._public_key


class CryptoFactory:
    """Factory for generating Signers.
    """

    def __init__(self, context):
        self._context = context

    @property
    def context(self):
        """Return the context that backs this factory instance
        """
        return self._context

    def new_signer(self, private_key):
        """Create a new signer for the given private key.

        Args:
            private_key (:obj:`PrivateKey`): a private key

        Returns:
            (:obj:`Signer`): a signer instance
        """
        return Signer(self._context, private_key)


def create_context(algorithm_name):
    """Returns an algorithm instance by name.

    Args:
        algorithm_name (str): the algorithm name

    Returns:
        (:obj:`Context`): a context instance for the given algorithm

    Raises:
        NoSuchAlgorithmError if the algorithm is unknown
    """
    if algorithm_name == 'secp256k1':
        return Secp256k1Context()

    raise NoSuchAlgorithmError("no such algorithm: {}".format(algorithm_name))
