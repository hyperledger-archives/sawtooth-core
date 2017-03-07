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

import logging

from sawtooth_validator.journal.consensus.consensus \
    import BlockPublisherInterface
from sawtooth_validator.journal.consensus.poet.poet_consensus \
    import poet_enclave_factory as factory

LOGGER = logging.getLogger(__name__)


class PoetBlockPublisher(BlockPublisherInterface):
    """Consensus objects provide the following services to the Journal:
    1) Build candidate blocks ( this temporary until the block types are
    combined into a single block type)
    2) Check if it is time to claim the current candidate blocks.
    3) Provide the data a signatures required for a block to be validated by
    other consensus algorithms
    """
    def __init__(self, block_cache, state_view, batch_publisher):
        """Initialize the object, is passed (read-only) state access objects.
            Args:
                block_cache (BlockCache): Dict interface to the block cache.
                    Any predecessor block to blocks handed to this object will
                    be present in this dict.
                state_view (StateView): A read only view of state for the last
                    committed block in the chain. For the block publisher this
                    is the block we are building on top of.
                batch_publisher (BatchPublisher): An interface implementing
                    send(txn_list) which wrap the transactions in a batch and
                    broadcast that batch to the network.
            Returns:
                none.
        """
        super().__init__(block_cache, state_view, batch_publisher)

        self._block_cache = block_cache
        self._state_view = state_view
        self._batch_publisher = batch_publisher
        self._poet_enclave_module = \
            factory.PoetEnclaveFactory.get_poet_enclave_module(state_view)

    def initialize_block(self, block_header):
        """Do initialization necessary for the consensus to claim a block,
        this may include initiating voting activities, starting proof of work
        hash generation, or create a PoET wait timer.

        Args:
            block_header (BlockHeader): The BlockHeader to initialize.
        Returns:
            Boolean: True if the candidate block should be built. False if
            no candidate should be built.
        """
        LOGGER.debug("PoetBlockPublisher.initialize_block()")
        block_header.consensus = b"PoetConsensus"

        return True

    def check_publish_block(self, block_header):
        """Check if a candidate block is ready to be claimed.

        Args:
            block_header (BlockHeader): The block header for the candidate
                block that is checked for readiness for publishing.
        Returns:
            Boolean: True if the candidate block should be claimed. False if
            the block is not ready to be claimed.
        """
        LOGGER.debug("PoetBlockPublisher.check_publish_block()")
        return True

    def finalize_block(self, block_header):
        """Finalize a block to be claimed. Provide any signatures and
        data updates that need to be applied to the block before it is
        signed and broadcast to the network.

        Args:
            block_header (BlockHeader): The block header for the candidate
                block that needs to be finalized.
        Returns:
            Boolean: True if the candidate block good and should be generated.
            False if the block should be abandoned.
        """
        LOGGER.debug("PoetBlockPublisher.finalize_block()")

        return True
