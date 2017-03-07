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
    import BlockVerifierInterface
from sawtooth_validator.journal.consensus.poet.poet_consensus \
    import poet_enclave_factory as factory

LOGGER = logging.getLogger(__name__)


class PoetBlockVerifier(BlockVerifierInterface):
    """BlockVerifier provides services for the Journal(ChainController) to
    determine if a block is valid (for the consensus rules) to be
    considered as part of the fork being evaluated. BlockVerifier must be
    independent of block publishing activities.
    """
    def __init__(self, block_cache, state_view):
        """Initialize the object, is passed (read-only) state access objects.
            Args:
                block_cache: Dict interface to the block cache. Any predecessor
                block to blocks handed to this object will be present in this
                dict.
                state_view: A read only view of state for the last committed
                block in the chain. For the BlockVerifier this is the previous
                block in the chain.
            Returns:
                none.
        """
        super().__init__(block_cache, state_view)

        self._block_cache = block_cache
        self._state_view = state_view
        self._poet_enclave_module = \
            factory.PoetEnclaveFactory.get_poet_enclave_module(state_view)

    def verify_block(self, block):
        """Check that the block received conforms to the consensus rules.

        Args:
            block (Block): The block to validate.
        Returns:
            Boolean: True if the Block is valid, False if the block is invalid.
        """
        LOGGER.debug("PoetBlockPublisher.verify_block()")
        return True
