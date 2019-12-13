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
from enum import IntEnum

from sawtooth_validator.protobuf.block_pb2 import BlockHeader

NULL_BLOCK_IDENTIFIER = "0000000000000000"


class BlockStatus(IntEnum):
    """
        The status of a block as the journal is concerned.
    """
    # Block is present but not yet validated
    Unknown = 0
    # Block failed block validation.
    Invalid = 1
    # Block has been validated and id valid to appear in a chain.
    Valid = 2
    # We know about the block, possibly by a successor, but we do not have it.
    Missing = 3
    # The block is currently being validated
    InValidation = 4


class BlockWrapper:
    """
    Utility class to make accessing block members more convenient.
    This also add storage of the weight and status used by the Journal
    components to track the state of a block. This is the object type
    stored in the Block Cache.
    """

    def __init__(self, block):
        self.block = block
        self._block_header = None

    @staticmethod
    def wrap(block):
        if isinstance(block, BlockWrapper):
            return block

        return BlockWrapper(block)

    @property
    def batches(self):
        """
        Returns the consensus object of the block.
        """
        return self.block.batches

    @property
    def consensus(self):
        """
        Returns the consensus object of the block.
        """
        return self.header.consensus

    def get_block(self):
        """
            Return the wrapped block object.
        """
        return self.block

    @property
    def header(self):
        """
        Returns the header of the block
        """
        if self._block_header is None:
            self._block_header = BlockHeader()
            self._block_header.ParseFromString(self.block.header)
        return self._block_header

    @property
    def header_signature(self):
        """
        Returns the header signature of the block
        """
        return self.block.header_signature

    @property
    def identifier(self):
        """
        Returns the identifier of the block, currently the
        header signature
        """
        return self.block.header_signature

    @property
    def block_num(self):
        """
        Returns the depth or block_number
        """
        return self.header.block_num

    @property
    def state_root_hash(self):
        """
        Returns the state root hash
        """
        return self.header.state_root_hash

    @property
    def previous_block_id(self):
        """
        Returns the identifier of the previous block.
        """
        return self.header.previous_block_id

    @property
    def signer_public_key(self):
        return self.header.signer_public_key

    @staticmethod
    def state_view_for_block(block_wrapper, state_view_factory):
        """
        Returns the state view for an arbitrary block.

        Args:
            block_wrapper (BlockWrapper): The block for which a state
                view is to be returned
            state_view_factory (StateViewFactory): The state view factory
                used to create the StateView object

        Returns:
            StateView object associated with the block
        """
        state_root_hash = \
            block_wrapper.state_root_hash \
            if block_wrapper is not None else None

        return state_view_factory.create_view(state_root_hash)

    def get_state_view(self, state_view_factory):
        """
        Returns the state view associated with this block

        Args:
            state_view_factory (StateViewFactory): The state view factory
                used to create the StateView object

        Returns:
            StateView object
        """
        return BlockWrapper.state_view_for_block(self, state_view_factory)

    @staticmethod
    def settings_view_for_block(block_wrapper, settings_view_factory):
        """
        Returns the settings view for an arbitrary block.

        Args:
            block_wrapper (BlockWrapper): The block for which a settings
                view is to be returned
            settings_view_factory (SettingsViewFactory): The settings
                view factory used to create the SettingsView object

        Returns:
            SettingsView object associated with the block
        """
        state_root_hash = \
            block_wrapper.state_root_hash \
            if block_wrapper is not None else None

        return settings_view_factory.create_settings_view(state_root_hash)

    def get_settings_view(self, settings_view_factory):
        """
        Returns the settings view associated with this block

        Args:
            settings_view_factory (SettingsViewFactory): The settings
                view factory used to create the SettingsView object

        Returns:
            SettingsView object
        """
        return BlockWrapper.settings_view_for_block(
            self, settings_view_factory)

    def __repr__(self):
        return "{}({}, S:{}, P:{})". \
            format(self.identifier, self.block_num,
                   self.state_root_hash, self.previous_block_id)

    def __str__(self):
        return "{} (block_num:{}, state:{}, previous_block_id:{})".format(
            self.identifier,
            self.block_num,
            self.state_root_hash,
            self.previous_block_id,
        )
