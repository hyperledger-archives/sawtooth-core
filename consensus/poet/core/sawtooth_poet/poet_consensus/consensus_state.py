# Copyright 2017 Intel Corporation
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

from collections import namedtuple

import cbor

ValidatorState = \
    namedtuple(
        'ValidatorState',
        ['key_block_claim_count',
         'poet_public_key',
         'total_block_claim_count'
         ])
""" Instead of creating a full-fledged class, let's use a named tuple for
the validator state.  The validator state represents the state for a single
validator at a point in time.  A validator state object contains:

key_block_claim_count (int): The number of blocks that the validator has
claimed using the current PoET public key
poet_public_key (str): The current PoET public key for the validator
total_block_claim_count (int): The total number of the blocks that the
    validator has claimed
"""


class ConsensusState(object):
    """Represents the consensus state at a particular point in time (i.e.,
    when the block that this consensus state corresponds to was committed to
    the block chain).

    Attributes:
        sealed_signup_data (str): The encoded sealed signup data that was
            received from the most recent creation of signup information
            for the validator
        expected_block_claim_count (float): The number of blocks that a
            validator, based upon the population estimate, would be expected
            to have claimed
    """
    def __init__(self):
        """Initialize a ConsensusState object

        Returns:
            None
        """
        self.sealed_signup_data = None
        self.expected_block_claim_count = 0.0
        self._validators = {}

    @staticmethod
    def _check_validator_state(validator_state):
        if not isinstance(
                validator_state.key_block_claim_count, int) \
                or validator_state.key_block_claim_count < 0:
            raise \
                ValueError(
                    'key_block_claim_count ({}) is invalid'.format(
                        validator_state.key_block_claim_count))

        if not isinstance(
                validator_state.poet_public_key, str) \
                or len(validator_state.poet_public_key) < 1:
            raise \
                ValueError(
                    'poet_public_key ({}) is invalid'.format(
                        validator_state.poet_public_key))
        if not isinstance(
                validator_state.total_block_claim_count, int) \
                or validator_state.total_block_claim_count < 0:
            raise \
                ValueError(
                    'total_block_claim_count ({}) is invalid'.format(
                        validator_state.total_block_claim_count))

        if validator_state.key_block_claim_count > \
                validator_state.total_block_claim_count:
            raise \
                ValueError(
                    'total_block_claim_count ({}) is less than '
                    'key_block_claim_count ({})'.format(
                        validator_state.total_block_claim_count,
                        validator_state.key_block_claim_count))

    def get_validator_state(self, validator_id, default=None):
        """Return the consensus state for a particular validator

        Args:
            validator_id (str): The ID of the validator for which consensus
                state information is being requested
            default (ValidatorState): The default state to return if the
                validator ID is not in the list of known validators

        Returns:
            ValidatorState: object corresponding to the validator or the
                value provided in the default parameter if there is no
                validator state information for the ID provided
        """

        assert default is None or isinstance(default, ValidatorState)

        return self._validators.get(validator_id, default)

    def set_validator_state(self, validator_id, validator_state):
        """Sets the consensus state for a particular validator.

        Args:
            validator_id (str): The ID of the validator for which consensus
                state information is being set
            validator_state (ValidatorState): The validator state information
                for the validator

        Returns:
            None

        Raises:
            ValueError: Validator state is invalid
        """

        assert isinstance(validator_state, ValidatorState)

        self._check_validator_state(validator_state)
        self._validators[validator_id] = validator_state

    def serialize_to_bytes(self):
        """Serialized the consensus state object to a byte string suitable
        for storage

        Returns:
            bytes: serialized version of the consensus state object
        """
        # For serialization, the easiest thing to do is to convert ourself to
        # a dictionary and convert to CBOR.
        return cbor.dumps(self.__dict__)

    def parse_from_bytes(self, buffer):
        """Returns a consensus state object re-created from the serialized
        consensus state provided.

        Args:
            buffer (bytes): A byte string representing the serialized
                version of a consensus state to re-create.  This was created
                by a previous call to serialize_to_bytes

        Returns:
            ConsensusState: object representing the serialized byte string
                provided

        Raises:
            ValueError: failure to parse into a valid ConsensusState object
        """
        try:
            # Deserialize the CBOR back into a dictionary and set the simple
            # fields, doing our best to check validity
            self_dict = cbor.loads(buffer)

            if not isinstance(self_dict, dict):
                raise \
                    ValueError(
                        'buffer is not a valid serialization of a '
                        'ConsensusState object')

            self.sealed_signup_data = \
                self_dict.get('sealed_signup_data', None)
            self.expected_block_claim_count = \
                float(self_dict['expected_block_claim_count'])
            validators = self_dict['_validators']

            if self.expected_block_claim_count < 0:
                raise \
                    ValueError(
                        'expected_block_claim_count ({}) is invalid'.format(
                            self.expected_block_claim_count))

            if not isinstance(validators, dict):
                raise ValueError('_validators is not a dict')

            # Now walk through all of the key/value pairs in the the
            # validators dictionary and reconstitute the validator state from
            # them, again trying to validate the data the best we can.  The
            # only catch is that because the validator state objects are named
            # tuples, cbor.dumps() treated them as such and so we lost the
            # named part.  When re-creating the validator state, are going to
            # leverage the namedtuple's _make method.

            self._validators = {}
            for key, value in validators.items():
                validator_state = ValidatorState._make(value)

                self._check_validator_state(validator_state)
                self._validators[str(key)] = validator_state

        except (LookupError, ValueError, KeyError, TypeError) as error:
            raise \
                ValueError(
                    'Error parsing ConsensusState buffer: {}'.format(error))

    def __str__(self):
        sealed_signup_data = \
            '0' * 16 if self.sealed_signup_data is None \
            else self.sealed_signup_data
        validators = \
            ['{}...{}: {{KBCC: {}, PPK: {}...{}, TBCC: {}}}'.format(
                key[:8],
                key[-8:],
                value.key_block_claim_count,
                value.poet_public_key[:8],
                value.poet_public_key[-8:],
                value.total_block_claim_count) for
             key, value in self._validators.items()]

        return \
            'SSD: {}...{}, EBCC: {}, V: {}'.format(
                sealed_signup_data[:8],
                sealed_signup_data[-8:],
                self.expected_block_claim_count,
                validators)
