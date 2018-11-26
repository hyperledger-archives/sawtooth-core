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
    def __init__(self,
                 block_cache,
                 state_view_factory,
                 batch_publisher,
                 data_dir,
                 config_dir,
                 validator_id):
        """Initialize the object, is passed (read-only) state access objects.
            Args:
                block_cache: Dict interface to the block cache. Any predecessor
                block to blocks handed to this object will be present in this
                dict.
                state_view_factory: A factory that can be used to create read-
                only views of state for a particular merkle root, in
                particular the state as it existed when a particular block
                was the chain head.
                batch_publisher: An interface implementing send(txn_list)
                which wrap the transactions in a batch and broadcast that
                batch to the network.
                data_dir: path to location where persistent data for the
                consensus module can be stored.
                config_dir (str): path to location where configuration for the
                consensus module can be found.
                validator_id: A unique ID for this validator
            Returns:
                none.
        """

    @abstractmethod
    def initialize_block(self, block_header):
        """Do initialization necessary for the consensus to claim a block,
        this may include initiating voting activities, starting proof of work
        hash generation, or create a PoET wait timer. The block
        is represented by a block_header since the full block will not be
        built until the block is finalized.

        Args:
            block_header (BlockHeader): the BlockHeader to initialize.
        Returns:
            Boolean: True if the candidate block should be built. False if
            no candidate should be built.
        """

    @abstractmethod
    def check_publish_block(self, block_header):
        """Check if a candidate block is ready to be claimed. The block
        is represented by a block_header since the full block will not be
        built until the block is finalized.

        Args:
            block_header (BlockHeader): the block_header to be checked if it
            should be claimed
        Returns:
            Boolean: True if the candidate block should be claimed. False if
            the block is not ready to be claimed.
        """

    @abstractmethod
    def finalize_block(self, block_header):
        """Finalize a block to be claimed. Update the
        Block.block_header.consensus field with any data this consensus's
        BlockVerifier needs to establish the validity of the block.

        Args:
            block_header (BlockHeader): The candidate block that needs to be
            finalized.
        Returns:
            Boolean: True if the candidate block good and should be generated.
            False if the block should be abandoned.
        """


class BlockVerifierInterface(metaclass=ABCMeta):
    # BlockVerifier provides services for the Journal(ChainController) to
    # determine if a block is valid (for the consensus rules) to be
    # considered as part of the fork being  evaluate. BlockVerifier must be
    # independent of block publishing activities.
    @abstractmethod
    def __init__(self,
                 block_cache,
                 state_view_factory,
                 data_dir,
                 config_dir,
                 validator_id):
        """Initialize the object, is passed (read-only) state access objects.
            Args:
                block_cache: Dict interface to the block cache. Any predecessor
                block to blocks handed to this object will be present in this
                dict.
                state_view_factory: A factory that can be used to create read-
                only views of state for a particular merkle root, in
                particular the state as it existed when a particular block
                was the chain head.
                data_dir: path to location where persistent data for the
                consensus module can be stored.
                config_dir (str): path to location where configuration for the
                consensus module can be found.
                validator_id: A unique ID for this validator
            Returns:
                none.
        """

    @abstractmethod
    def verify_block(self, block_wrapper):
        """Check that the block received conforms to the consensus rules.

        Args:
            block_wrapper (BlockWrapper): The block to validate.
        Returns:
            Boolean: True if the Block is valid, False if the block is invalid.
        """


class ForkResolverInterface(metaclass=ABCMeta):
    # Provides the fork resolution interface for the BlockValidator to use
    # when deciding between two forks.
    @abstractmethod
    def __init__(self,
                 block_cache,
                 state_view_factory,
                 data_dir,
                 config_dir,
                 validator_id):
        """Initialize the object, is passed (read-only) state access objects.
        StateView is not passed to this object as it is ambiguous as to which
        state it is and all state dependent calculations should have been
        done during compute_block_weight and stored in the weight object
        accessible from the block.
            Args:
                block_cache: Dict interface to the block cache. Any predecessor
                block to blocks handed to this object will be present in this
                dict.
                state_view_factory: A factory that can be used to create read-
                only views of state for a particular merkle root, in
                particular the state as it existed when a particular block
                was the chain head.
                data_dir: path to location where persistent data for the
                consensus module can be stored.
                data_dir: path to location where config data for the
                consensus module can be found.
                validator_id: A unique ID for this validator
            Returns:
                none.
        """

    @abstractmethod
    def compare_forks(self, cur_fork_head, new_fork_head):
        """Given the head of two forks return which should be the fork that
        the validator chooses.  When this is called both forks consist of
         only valid blocks.

        Args:
            cur_fork_head (BlockWrapper): The current head of the block
            chain.
            new_fork_head (BlockWrapper): The head of the fork that is being
            evaluated.
        Returns:
            bool: True if the new chain should replace the current chain.
            False if the new chain should be discarded.
        """
