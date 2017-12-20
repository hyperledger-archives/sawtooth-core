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

from abc import ABCMeta
from abc import abstractmethod


class NoSuchAlgorithmError(Exception):
    """Thrown when trying to create an algorithm which does not exist.
    """
    pass


class SigningError(Exception):
    """Thrown when an error occurs during the signing process.
    """
    pass


class ParseError(Exception):
    """Thrown when an error occurs during deserialization of a Private or
    Public key from various formats.
    """
    pass


class PrivateKey(metaclass=ABCMeta):
    """A private key instance.

    The underlying content is dependent on implementation.
    """

    @abstractmethod
    def get_algorithm_name(self):
        """Returns the algorithm name used for this private key.
        """
        pass

    @abstractmethod
    def as_hex(self):
        """Return the private key encoded as a hex string.
        """
        pass

    @abstractmethod
    def as_bytes(self):
        """Return the private key bytes.
        """
        pass


class PublicKey(metaclass=ABCMeta):
    """A public key instance.

    The underlying content is dependent on implementation.
    """

    @abstractmethod
    def get_algorithm_name(self):
        """Returns the algorithm name used for this public key.
        """
        pass

    @abstractmethod
    def as_hex(self):
        """Return the public key encoded as a hex string.
        """
        pass

    @abstractmethod
    def as_bytes(self):
        """Return the public key bytes.
        """
        pass


class Context(metaclass=ABCMeta):
    """A context for a cryptographic signing algorithm.
    """

    @abstractmethod
    def get_algorithm_name(self):
        """Returns the algorithm name.
        """
        pass

    @abstractmethod
    def sign(self, message, private_key):
        """Sign a message

        Given a private key for this algorithm, sign the given message bytes
        and return a hex-encoded string of the resulting signature.

        Args:
            message (bytes): the message bytes
            private_key (:obj:`PrivateKey`): the private key

        Returns:
            The signature in a hex-encoded string

        Raises:
            SigningError: if any error occurs during the signing process
        """
        pass

    @abstractmethod
    def verify(self, signature, message, public_key):
        """Verifies that a signature of a message was produced with the
        associated public key.

        Args:
            signature (str): the hex-encoded signature
            message (bytes): the message bytes
            public_key (:obj:`PublicKey`): the public key to use for
                verification

        Returns:
            boolean: True if the public key is associated with the signature
            for that method, False otherwise
        """

    @abstractmethod
    def new_random_private_key(self):
        """Generates a new random PrivateKey using this context.

        Returns:
            (:obj:`PrivateKey`): a random private key
        """

    @abstractmethod
    def get_public_key(self, private_key):
        """Produce a public key for the given private key.

        Args:
            private_key (:obj:`PrivateKey`): a private key

        Returns:
            (:obj:`PublicKey`) the public key for the given private key
        """
        pass
