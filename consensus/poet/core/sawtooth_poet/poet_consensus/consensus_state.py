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

import math
import logging

from collections import namedtuple

import cbor

LOGGER = logging.getLogger(__name__)

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
        aggregate_local_mean (float): The sum of the local means for the PoET
            blocks since the last non-PoET block
        total_block_claim_count (int): The number of blocks that have been
            claimed by all validators
    """
    def __init__(self):
        """Initialize a ConsensusState object

        Returns:
            None
        """
        self.aggregate_local_mean = 0.0
        self.total_block_claim_count = 0
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

    def get_validator_state(self, validator_info):
        """Return the validator state for a particular validator
        Args:
            validator_info (ValidatorInfo): The validator information for the
                validator for which validator or state information is being
                requested
        Returns:
            ValidatorState: The validator state if it exists or the default
                initial state if it does not
        """

        # Fetch the validator state.  If it doesn't exist, then create a
        # default validator state object and store it for further requests
        validator_state = self._validators.get(validator_info.id)

        if validator_state is None:
            validator_state = \
                ValidatorState(
                    key_block_claim_count=0,
                    poet_public_key=validator_info.signup_info.
                    poet_public_key,
                    total_block_claim_count=0)
            self._validators[validator_info.id] = validator_state

        return validator_state

    def validator_did_claim_block(self,
                                  validator_info,
                                  wait_certificate):
        """For the validator that is referenced by the validator information
        object, update its state based upon it claiming a block.

        Args:
            validator_info (ValidatorInfo): Information about the validator
            wait_certificate (WaitCertificate): The wait certificate
                associated with the block being claimed

        Returns:
            None
        """
        # Update the consensus state statistics.
        self.aggregate_local_mean += wait_certificate.local_mean
        self.total_block_claim_count += 1

        # We need to fetch the current state for the validator
        validator_state = \
            self.get_validator_state(validator_info=validator_info)

        total_block_claim_count = \
            validator_state.total_block_claim_count + 1

        # If the PoET public keys match, then we are doing a simple statistics
        # update
        if validator_info.signup_info.poet_public_key == \
                validator_state.poet_public_key:
            key_block_claim_count = \
                validator_state.key_block_claim_count + 1

        # Otherwise, we are resetting statistics for the validator.  This
        # includes using the validator info's transaction ID to get the block
        # number of the block that committed the validator registry
        # transaction.
        else:
            key_block_claim_count = 1

        LOGGER.debug(
            'Update state for %s (ID=%s...%s): PPK=%s...%s, KBCC=%d, TBCC=%d',
            validator_info.name,
            validator_info.id[:8],
            validator_info.id[-8:],
            validator_info.signup_info.poet_public_key[:8],
            validator_info.signup_info.poet_public_key[-8:],
            key_block_claim_count,
            total_block_claim_count)

        # Update our copy of the validator state
        self._validators[validator_info.id] = \
            ValidatorState(
                key_block_claim_count=key_block_claim_count,
                poet_public_key=validator_info.signup_info.poet_public_key,
                total_block_claim_count=total_block_claim_count)

    def validator_has_claimed_block_limit(self,
                                          validator_info,
                                          poet_config_view):
        """Determines if a validator has already claimed the maximum number of
        blocks allowed with its PoET key pair.
        Args:
            validator_info (ValidatorInfo): The current validator information
            poet_config_view (PoetConfigView): The limit of number of blocks
             that can be claimed with a PoET key pair
        Returns:
            Boolean: True if the validator has already claimed the maximum
                number of blocks with its current PoET key pair, False
                otherwise
        """
        key_block_claim_limit = poet_config_view.key_block_claim_limit
        validator_state = \
            self.get_validator_state(validator_info=validator_info)

        if validator_state.poet_public_key == \
                validator_info.signup_info.poet_public_key:
            if validator_state.key_block_claim_count >= key_block_claim_limit:
                LOGGER.error(
                    'Validator %s (ID=%s...%s): Reached block claim limit '
                    'for PoET keys %d >= %d',
                    validator_info.name,
                    validator_info.id[:8],
                    validator_info.id[-8:],
                    validator_state.key_block_claim_count,
                    key_block_claim_limit)
                return True
            else:
                LOGGER.debug(
                    'Validator %s (ID=%s...%s): Claimed %d block(s) out of %d',
                    validator_info.name,
                    validator_info.id[:8],
                    validator_info.id[-8:],
                    validator_state.key_block_claim_count,
                    key_block_claim_limit)
        else:
            LOGGER.debug(
                'Validator %s (ID=%s...%s): Claimed 0 block(s) out of %d',
                validator_info.name,
                validator_info.id[:8],
                validator_info.id[-8:],
                key_block_claim_limit)

        return False

    def validator_is_claiming_too_early(self,
                                        validator_info,
                                        block_number,
                                        validator_registry_view,
                                        poet_config_view,
                                        block_store):
        """Determines if a validator has tried to claim a block too early
        (i.e, has not waited the required number of blocks between when the
        block containing its validator registry transaction was committed to
        the chain and trying to claim a block).
        Args:
            validator_info (ValidatorInfo): The current validator information
            block_number (int): The block number of the block that the
                validator is attempting to claim
            validator_registry_view (ValidatorRegistry): The current validator
                registry view
            poet_config_view (PoetConfigView): The current PoET configuration
                view
            block_store (BlockStore): The block store
        Returns:
            Boolean: True if the validator has not waited the required number
                of blocks before attempting to claim a block, False otherwise
        """

        # While having a block claim delay is nice, it turns out that in
        # practice the claim delay should not be more than one less than
        # the number of validators.  It helps to imagine the scenario
        # where each validator hits their block claim limit in sequential
        # blocks and their new validator registry information is updated
        # in the following block by another validator, assuming that there
        # were no forks.  If there are N validators, once all N validators
        # have updated their validator registry information, there will
        # have been N-1 block commits and the Nth validator will only be
        # able to get its updated validator registry information updated
        # if the first validator that kicked this off is now able to claim
        # a block.  If the block claim delay was greater than or equal to
        # the number of validators, at this point no validators would be
        # able to claim a block.
        number_of_validators = len(validator_registry_view.get_validators())
        block_claim_delay = \
            min(poet_config_view.block_claim_delay, number_of_validators - 1)

        # While a validator network is starting up, we need to be careful
        # about applying the block claim delay because if we are too
        # aggressive we will get ourselves into a situation where the
        # block claim delay will prevent any validators from claiming
        # blocks.  So, until we get at least block_claim_delay blocks
        # we are going to choose not to enforce the delay.
        if self.total_block_claim_count <= block_claim_delay:
            LOGGER.debug(
                'Skipping block claim delay check.  Only %d block(s) in '
                'the chain.  Claim delay is %d block(s). %d validator(s) '
                'registered.',
                self.total_block_claim_count,
                block_claim_delay,
                number_of_validators)
            return False

        # Figure out the block in which the current validator information
        # was committed.
        commit_block = \
            block_store.get_block_by_transaction_id(
                validator_info.transaction_id)
        blocks_claimed_since_registration = \
            block_number - commit_block.block_num - 1

        if block_claim_delay > blocks_claimed_since_registration:
            LOGGER.error(
                'Validator %s (ID=%s...%s): Committed in block %d, trying to '
                'claim block %d, must wait until block %d',
                validator_info.name,
                validator_info.id[:8],
                validator_info.id[-8:],
                commit_block.block_num,
                block_number,
                commit_block.block_num + block_claim_delay + 1)
            return True

        LOGGER.debug(
            'Validator %s (ID=%s...%s): Committed in block %d, trying to '
            'claim block %d',
            validator_info.name,
            validator_info.id[:8],
            validator_info.id[-8:],
            commit_block.block_num,
            block_number)

        return False

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

            self.aggregate_local_mean = \
                float(self_dict['aggregate_local_mean'])
            self.total_block_claim_count = \
                int(self_dict['total_block_claim_count'])
            validators = self_dict['_validators']

            if not math.isfinite(self.aggregate_local_mean) or \
                    self.aggregate_local_mean < 0:
                raise \
                    ValueError(
                        'aggregate_local_mean ({}) is invalid'.format(
                            self.aggregate_local_mean))
            if self.total_block_claim_count < 0:
                raise \
                    ValueError(
                        'total_block_claim_count ({}) is invalid'.format(
                            self.total_block_claim_count))

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
        validators = \
            ['{}: {{KBCC={}, PPK={}, TBCC={}, }}'.format(
                key[:8],
                value.key_block_claim_count,
                value.poet_public_key[:8],
                value.total_block_claim_count) for
             key, value in self._validators.items()]

        return \
            'ALM={:.4f}, TBCC={}, V={}'.format(
                self.aggregate_local_mean,
                self.total_block_claim_count,
                validators)
