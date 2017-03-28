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

import collections
import json
import logging

from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER

from sawtooth_poet_common.validator_registry_view.validator_registry_view \
    import ValidatorRegistryView

from sawtooth_poet.poet_consensus.wait_certificate import WaitCertificate
from sawtooth_poet.poet_consensus.consensus_state import ConsensusState
from sawtooth_poet.poet_consensus.consensus_state import ValidatorState

LOGGER = logging.getLogger(__name__)


def block_id_is_genesis(block_id):
    """Determines if the block ID represents the genesis block.

    Args:
        block_id (str): The block ID to check

    Returns:
        True if this ID represents the block ID, or False otherwise.
    """
    return block_id == NULL_BLOCK_IDENTIFIER


def deserialize_wait_certificate(block, poet_enclave_module):
    """Deserializes the wait certificate associated with the block.

    Args:
        block (Block or BlockWrapper): The block that has the wait certificate
        poet_enclave_module (module): The PoET enclave module

    Returns:
        WaitCertificate: The reconstituted wait certificate associated
            with the block or None if cannot deserialize
    """
    # The wait certificate is a JSON string placed in the consensus
    # field/property of the block header.  Parse the JSON and then use the
    # serialized wait certificate and signature to create a
    # WaitCertificate object.
    wait_certificate = None
    try:
        wait_certificate_dict = json.loads(block.header.consensus.decode())
        wait_certificate = \
            WaitCertificate.wait_certificate_from_serialized(
                poet_enclave_module=poet_enclave_module,
                serialized=wait_certificate_dict['SerializedCertificate'],
                signature=wait_certificate_dict['Signature'])
    except (json.decoder.JSONDecodeError, KeyError):
        pass

    return wait_certificate


def build_certificate_list(block_header,
                           block_cache,
                           poet_enclave_module,
                           maximum_number):
    """Builds a list of up to maximum_length wait certificates for the blocks
    immediately preceding the block represented by block_header.

    Args:
        block_header (BlockHeader): The header for the block
        block_cache (BlockCache): The cache of blocks that are predecessors
            to the block represented by block_header
        poet_enclave_module (module): The PoET enclave module
        maximum_number (int): The maximum number of certificates to return

    Returns:
        A list of wait certificates
    """

    # Create a list of certificates starting with the immediate predecessor
    # to the block represented by block_header.  We will use a deque because
    # we are walking the blocks in reverse order.
    certificates = collections.deque()
    block_id = block_header.previous_block_id

    try:
        while not block_id_is_genesis(block_id) and \
                len(certificates) < maximum_number:
            # Grab the block from the block store, use the consensus
            # property to reconstitute the wait certificate, and add
            # the wait certificate to the list.  If we get to a block
            # that does not have a wait certificate, we stop.
            block = block_cache[block_id]
            wait_certificate = \
                deserialize_wait_certificate(
                    block=block,
                    poet_enclave_module=poet_enclave_module)

            if wait_certificate is None:
                break

            certificates.appendleft(wait_certificate)

            # Move to the previous block
            block_id = block.header.previous_block_id
    except KeyError as ke:
        LOGGER.error('Error getting block: %s', ke)

    return list(certificates)


def create_validator_state(validator_info, current_validator_state):
    """Starting with the current validator state (or None), create validator
     validator state for the validator.

    Args:
        validator_info (ValidatorInfo): Information about the validator
        current_validator_state (ValidatorState): The current validator
            state we are going to update or None if there isn't any and
            we are to create default validator state

    Returns:
        ValidatorState object
    """

    # Start with the default validator state (i.e., assuming that none existed
    # to start with) and update accordingly.  If it does exist and the PoET
    # public key is the same, then we are just going to update counts.  If it
    # does exist but the PoET public key has changed, we need to update
    # statistics and take note of the new key.
    key_block_claim_count = 1
    poet_public_key = validator_info.signup_info.poet_public_key
    total_block_claim_count = 1

    if current_validator_state is not None:
        total_block_claim_count = \
            current_validator_state.total_block_claim_count + 1

        if validator_info.signup_info.poet_public_key == \
                current_validator_state.poet_public_key:
            key_block_claim_count = \
                current_validator_state.key_block_claim_count + 1

    LOGGER.debug(
        'Create validator state for %s: PPK=%s...%s, KBCC=%d, TBCC=%d',
        validator_info.name,
        poet_public_key[:8],
        poet_public_key[-8:],
        key_block_claim_count,
        total_block_claim_count)

    return \
        ValidatorState(
            key_block_claim_count=key_block_claim_count,
            poet_public_key=poet_public_key,
            total_block_claim_count=total_block_claim_count)


def get_consensus_state_for_block_id(
        block_id,
        block_cache,
        state_view_factory,
        consensus_state_store,
        poet_enclave_module):
    """Returns the consensus state for the block referenced by block ID,
        creating it from the consensus state history if necessary.

    Args:
        block_id (str): The ID of the block for which consensus state will
            be returned.
        block_cache (BlockCache): The block store cache
        state_view_factory (StateViewFactory): A factory that can be used
            to create state view object corresponding to blocks
        consensus_state_store (ConsensusStateStore): The consensus state
            store
        poet_enclave_module (module): The PoET enclave module

    Returns:
        ConsensusState object representing the consensus state for the block
            referenced by block_id
    """

    # Starting at the chain head, walk the block store backwards until we
    # either get to the root or we get a block for which we have already
    # created consensus state
    block = \
        block_cache[block_id] if block_id != NULL_BLOCK_IDENTIFIER else None
    consensus_state = None
    block_ids = collections.deque()

    while block is not None:
        # Try to fetch the consensus state.  If that succeeds, we can
        # stop walking back as we can now build on that consensus
        # state.
        consensus_state = consensus_state_store.get(block.identifier)
        if consensus_state is not None:
            break

        # If this is a PoET block, then we want to create consensus state
        # for it when we are done
        if deserialize_wait_certificate(block, poet_enclave_module):
            LOGGER.debug(
                'We need to build consensus state for block ID %s...%s',
                block.identifier[:8],
                block.identifier[-8:])
            block_ids.appendleft(block.identifier)

        # Move to the previous block
        block = \
            block_cache[block.previous_block_id] \
            if block.previous_block_id != NULL_BLOCK_IDENTIFIER else None

    # If didn't find any consensus state, see if there is any "before" any
    # blocks were created (this might be because we are the first validator
    # and PoET signup information was created, including sealed signup data
    # that was saved in the consensus state store).
    if consensus_state is None:
        consensus_state = consensus_state_store.get(NULL_BLOCK_IDENTIFIER)

    # At this point, if we have not found any consensus state, we need to
    # create default state from which we can build upon
    if consensus_state is None:
        consensus_state = ConsensusState()

    # Now, walking forward through the blocks for which we were supposed to
    # create consensus state, we are going to create and store state for each
    # one so that the next time we don't have to walk so far back through the
    # block chain.
    for identifier in block_ids:
        block = block_cache[identifier]

        # Get the validator registry view for this block's state view and
        # then fetch the validator info for the validator that signed this
        # block.
        state_view = state_view_factory.create_view(block.state_root_hash)
        validator_registry_view = ValidatorRegistryView(state_view)

        validator_id = block.header.signer_pubkey
        validator_info = \
            validator_registry_view.get_validator_info(
                validator_id=validator_id)

        # Fetch the current validator state, set/update the validator state
        # in the consensus state object, and then create the consensus state
        # in the consensus state store and associate it with this block
        validator_state = \
            consensus_state.get_validator_state(validator_id=validator_id)
        consensus_state.set_validator_state(
            validator_id=validator_id,
            validator_state=create_validator_state(
                validator_info=validator_info,
                current_validator_state=validator_state))

        LOGGER.debug(
            'Store consensus state for block ID %s...%s',
            identifier[:8],
            identifier[-8:])

        consensus_state_store[identifier] = consensus_state

    return consensus_state
