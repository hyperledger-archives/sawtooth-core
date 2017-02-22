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
from abc import ABCMeta
from abc import abstractmethod


class BlockPublisherInterface(metaclass=ABCMeta):
    """The BlockPublisher provides consensus services to the BlockPublisher.
    1) Block initialization or error if it is not time to create a block.
    2) Check if it is time to claim the candidate blocks.
    3) Sign the block prior to publishing. Provide an opaque block of data
    that will allow the BlockVerifier implementation of this consensus
    algorithm to verify that this is a valid block.
    """

    @abstractmethod
    def __init__(self, block_cache, state_view):
        """Initialize the object, is passed (read-only) state access objects.
            Args:
                block_cache: Dict interface to the block cache. Any predecessor
                block to blocks handed to this object will be present in this
                dict.
                state_view: A read only view of state for the last committed
                block in the chain. For the block publisher this is the block
                we are building on top of.
            Returns:
                none.
        """
        pass

    @abstractmethod
    def initialize_block(self, block):
        """Do initialization necessary for the consensus to claim a block,
        this may include initiating voting activities, starting proof of work
        hash generation, or create a PoET wait timer.

        Args:
            block (Block): the block to initialize.
        Returns:
            consensus: the serialized consensus data for the block header, this
            can be temporary state data or None.
        """
        pass

    @abstractmethod
    def check_publish_block(self, block):
        """Check if a candidate block is ready to be claimed.

        Args:
            block (Block): the block to be checked if it should be claimed
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
            block (Block): The candidate block that needs to be finalized
             by the consensus
        Returns:
            consensus: The consensus data to store on the block.
        """
        pass


class BlockVerifierInterface(metaclass=ABCMeta):
    # BlockVerifier provides services for the Journal(ChainController) to
    # determine if a block is valid (for the consensus rules) to be
    # considered as part of the fork being  evaluate. BlockVerifier must be
    # independent of block publishing activities.
    @abstractmethod
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
        pass

    @abstractmethod
    def verify_block(self, block):
        """Check that the block received conforms to the consensus rules.

        Args:
            block (Block): The block to validate.
        Returns:
            None
        """
        pass

    def compute_block_weight(self, block):
        """
        Args:
            block (Block): The block to compute weight of.
        Returns:
            An opaque weight object.
        """
        pass


class ForkResolverInterface(metaclass=ABCMeta):
    # Provides the fork resolution interface for the BlockValidator to use
    # when deciding between two forks.
    @abstractmethod
    def __init__(self, block_cache):
        """Initialize the object, is passed (read-only) state access objects.
        StateView is not passed to this object as it is ambiguous as to which
        state it is and all state dependent calculations should have been
        done during compute_block_weight and stored in the weight object
        accessible from the block.
            Args:
                block_cache: Dict interface to the block cache. Any predecessor
                block to blocks handed to this object will be present in this
                dict.
            Returns:
                none.
        """
        pass

    @abstractmethod
    def compare_forks(self, cur_fork_head, new_fork_head):
        """Given the head of two forks return which should be the fork that
        the validator chooses.  When this is called both forks consist of
         only valid blocks.

        Args:
            cur_fork_head (Block): The current head of the block chain.
            new_fork_head (Block): The head of the fork that is being
                evaluated.
        Returns:
            bool: True if the new chain should replace the current chain.
            False if the new chain should be discarded.
        """
        pass
