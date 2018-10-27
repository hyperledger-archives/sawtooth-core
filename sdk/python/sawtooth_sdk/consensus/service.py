# Copyright 2018 Intel Corporation
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
# -----------------------------------------------------------------------------

import abc


class Block:
    def __init__(self, block):
        self.block_id = block.block_id
        self.previous_id = block.previous_id
        self.signer_id = block.signer_id
        self.block_num = block.block_num
        self.payload = block.payload
        self.summary = block.summary


class Service(metaclass=abc.ABCMeta):
    '''Provides methods that allow the consensus engine to issue commands
    and requests.'''

    # -- P2P --

    @abc.abstractmethod
    def send_to(self, receiver_id, message_type, payload):
        '''Send a consensus message to a specific connected peer.

        Args:
            receiver_id (bytes)
            message_type (str)
            payload (bytes)
        '''

    @abc.abstractmethod
    def broadcast(self, message_type, payload):
        '''Broadcast a message to all connected peers.

        Args:
            message_type (str)
            payload (bytes)
        '''

    # -- Block Creation --

    @abc.abstractmethod
    def initialize_block(self, previous_id):
        '''Initialize a new block with PREVIOUS_ID and begin adding batches to
        it. If no PREVIOUS_ID is specified, the current head will be
        used.

        Args:
            previous_id (bytes or None)
        '''

    @abc.abstractmethod
    def summarize_block(self):
        '''Stop adding batches to the current block and return a summary of its
        contents.

        Return:
            bytes
        '''

    @abc.abstractmethod
    def finalize_block(self, data):
        '''Insert the given consensus data into the block and sign it. If this
        call is successful, the consensus engine will receive the block
        afterwards.

        Args:
            data (bytes)

        Return:
            bytes
        '''

    @abc.abstractmethod
    def cancel_block(self):
        '''Stop adding batches to the current block and abandon it.'''

    # -- Block Directives --

    @abc.abstractmethod
    def check_blocks(self, priority):
        '''Update the prioritization of blocks to check to PRIORITY.

        Args:
            priority (list[bytes])
        '''

    @abc.abstractmethod
    def commit_block(self, block_id):
        '''Update the block that should be committed.

        Args:
            block_id (bytes)
        '''

    @abc.abstractmethod
    def ignore_block(self, block_id):
        '''Signal that this block is no longer being committed.

        Args:
            block_id (bytes)
        '''

    @abc.abstractmethod
    def fail_block(self, block_id):
        '''Mark this block as invalid from the perspective of consensus.

        Args:
            block_id (bytes)
        '''

    # -- Queries --

    @abc.abstractmethod
    def get_blocks(self, block_ids):
        '''Retrive consensus-related information about blocks.

        Args:
            block_ids (list[bytes])

        Return:
            dict[bytes, block]
        '''

    @abc.abstractmethod
    def get_chain_head(self):
        '''Retrieve consensus-related information about the chain head.

        Return:
            block
        '''

    @abc.abstractmethod
    def get_settings(self, block_id, settings):
        '''Read the value of settings as of the given block.

        Args:
            block_id (bytes)
            settings (list[str])

        Return:
            dict[str, str]
        '''

    @abc.abstractmethod
    def get_state(self, block_id, addresses):
        '''Read values in state as of the given block.

        Args:
            block_id (bytes)
            addresses (list[str])

        Return:
            dict[str, bytes]
        '''
