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

from sawtooth_poet.poet_consensus.wait_certificate import WaitCertificate

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
    if block is not None:
        try:
            wait_certificate_dict = \
                json.loads(block.header.consensus.decode())
            wait_certificate = \
                WaitCertificate.wait_certificate_from_serialized(
                    poet_enclave_module=poet_enclave_module,
                    serialized=wait_certificate_dict['SerializedCertificate'],
                    signature=wait_certificate_dict['Signature'])
        except (json.decoder.JSONDecodeError, KeyError):
            pass

    return wait_certificate


def get_previous_certificate_id(block_header,
                                block_cache,
                                poet_enclave_module):
    """Returns the wait certificate ID for the block immediately preceding the
    block represented by block_header.

    Args:
        block_header (BlockHeader): The header for the block
        block_cache (BlockCache): The cache of blocks that are predecessors
            to the block represented by block_header
        poet_enclave_module (module): The PoET enclave module

    Returns:
        str: The ID of the wait certificate for the block immediately
        preceding the block represented by block_header
    """
    wait_certificate = None

    if not block_id_is_genesis(block_header.previous_block_id):
        wait_certificate = \
            deserialize_wait_certificate(
                block=block_cache[block_header.previous_block_id],
                poet_enclave_module=poet_enclave_module)

    return \
        NULL_BLOCK_IDENTIFIER if wait_certificate is None \
        else wait_certificate.identifier


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
