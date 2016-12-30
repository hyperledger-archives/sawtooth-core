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
from abc import abstractmethod


class BlockPublisherInterface(object):
    """Consensus objects provide the following services to the Journal:
    1) Build candidate blocks ( this temporary until the block types are
    combined into a single block type)
    2) Check if it is time to claim the current candidate blocks.
    3) Provide the data a signatures required for a block to be validated by
    other consensus algorithms

    """
    # TDB - read only access the block store
    # TBD - Early or late transaction binding -- voting needs to be early????

    @abstractmethod
    def initialize_block(self, block):
        """Do initialization necessary for the consensus to claim a block,
        this may include initiating voting activates, starting proof of work
        hash generation, or create a PoET wait timer.

        Args:
            block (Block): the block to initialize.
        Returns:
            none
        """
        pass

    @abstractmethod
    def check_publish_block(self, block):
        """Check if a candidate block is ready to be claimed.

        Args:
            block: the block to be checked if it should be claimed
            now: the current time
        Returns:
            Boolean: True if the candidate block should be claimed.
        """
        pass

    @abstractmethod
    def finalize_block(self, block):
        """Finalize a block to be claimed. Provide any signatures and
        data updates that need to be applied to the block before it is
        signed and broadcast to the network.

        Args:
            block: The candidate block that needs to be finalized
             by the consensus
        Returns:
            None
        """
        pass


class BlockVerifierInterface(object):
    # Block Validator Activites - must be stateless and indpendent of the
    # of the publishing activites

    @abstractmethod
    def verify_block(self, block):
        """Check that the block received meets the consensus rules for validity

        Args:
            block: The block to validate
        Returns:
            None
        """
        pass

    def compute_block_weight(self, block):

        """Check that the block received meets the consensus rules for validity

        Args:
            block: The block to validate
        Returns:
            None
        """
        pass
