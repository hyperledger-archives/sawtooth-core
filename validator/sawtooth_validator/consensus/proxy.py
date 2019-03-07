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
# ------------------------------------------------------------------------------

import hashlib

from collections import namedtuple

from sawtooth_validator.protobuf.consensus_pb2 import ConsensusPeerMessage
from sawtooth_validator.protobuf.consensus_pb2 import \
    ConsensusPeerMessageHeader


class UnknownBlock(Exception):
    """The given block could not be found."""


StartupInfo = namedtuple(
    'SignupInfo',
    ['chain_head', 'peers', 'local_peer_info'])


class ConsensusProxy:
    """Receives requests from the consensus engine handlers and delegates them
    to the appropriate components."""

    def __init__(self, block_cache, block_publisher,
                 chain_controller, gossip, identity_signer,
                 settings_view_factory, state_view_factory,
                 consensus_registry):
        self._block_cache = block_cache
        self._chain_controller = chain_controller
        self._block_publisher = block_publisher
        self._gossip = gossip
        self._identity_signer = identity_signer
        self._public_key = self._identity_signer.get_public_key().as_bytes()
        self._settings_view_factory = settings_view_factory
        self._state_view_factory = state_view_factory
        self._consensus_registry = consensus_registry

    def register(self, engine_name, engine_version, connection_id):
        chain_head = self._chain_controller.chain_head
        if chain_head is None:
            return None

        self._consensus_registry.register_engine(
            connection_id, engine_name, engine_version)

        return StartupInfo(
            chain_head=chain_head,
            peers=[
                self._gossip.peer_to_public_key(peer)
                for peer in self._gossip.get_peers()
                if peer is not None
            ],
            local_peer_info=self._public_key)

    # Using network service
    def send_to(self, peer_id, message_type, content, connection_id):
        message = self._wrap_consensus_message(
            content, message_type, connection_id)
        self._gossip.send_consensus_message(
            peer_id=peer_id.hex(),
            message=message)

    def broadcast(self, message_type, content, connection_id):
        message = self._wrap_consensus_message(
            content, message_type, connection_id)
        self._gossip.broadcast_consensus_message(message=message)

    # Using block publisher
    def initialize_block(self, previous_id):
        if previous_id:
            try:
                previous_block = self._block_cache[previous_id.hex()]
            except KeyError:
                raise UnknownBlock()
            self._block_publisher.initialize_block(previous_block)
        else:
            self._block_publisher.initialize_block(
                self._chain_controller.chain_head)

    def summarize_block(self):
        return self._block_publisher.summarize_block()

    def finalize_block(self, consensus_data):
        return bytes.fromhex(self._block_publisher.finalize_block(
            consensus=consensus_data))

    def cancel_block(self):
        self._block_publisher.cancel_block()

    def check_blocks(self, block_ids):
        for block_id in block_ids:
            if block_id.hex() not in self._block_cache:
                raise UnknownBlock(block_id.hex())

    def get_block_statuses(self, block_ids):
        """Returns a list of tuples of (block id, BlockStatus) pairs.
        """
        try:
            return [
                (block_id.hex(), self._block_cache[block_id.hex()].status)
                for block_id in block_ids
            ]
        except KeyError as key_error:
            raise UnknownBlock(key_error.args[0])

    def commit_block(self, block_id):
        try:
            block = self._block_cache[block_id.hex()]
        except KeyError as key_error:
            raise UnknownBlock(key_error.args[0])
        self._chain_controller.commit_block(block)

    def ignore_block(self, block_id):
        try:
            block = self._block_cache[block_id.hex()]
        except KeyError:
            raise UnknownBlock()
        self._chain_controller.ignore_block(block)

    def fail_block(self, block_id):
        try:
            block = self._block_cache[block_id.hex()]
        except KeyError:
            raise UnknownBlock()
        self._chain_controller.fail_block(block)

    def forks(self):
        chain_head = self._chain_controller.chain_head
        if chain_head is None:
            return None

        return self._chain_controller.forks(chain_head.header_signature)

    # Using blockstore and state database
    def blocks_get(self, block_ids):
        '''Returns a list of blocks.'''
        return self._get_blocks(block_ids)

    def chain_head_get(self):
        '''Returns the chain head.'''

        chain_head = self._chain_controller.chain_head

        if chain_head is None:
            raise UnknownBlock()

        return chain_head

    def settings_get(self, block_id, settings):
        '''Returns a list of key/value pairs (str, str).'''
        settings_view = \
            self._get_blocks([block_id])[0].get_settings_view(
                self._settings_view_factory)

        result = []
        for setting in settings:
            try:
                value = settings_view.get_setting(setting)
            except KeyError:
                # if the key is missing, leave it out of the response
                continue

            result.append((setting, value))

        return result

    def state_get(self, block_id, addresses):
        '''Returns a list of address/data pairs (str, bytes)'''
        state_view = \
            self._get_blocks([block_id])[0].get_state_view(
                self._state_view_factory)

        result = []

        for address in addresses:
            # a fully specified address
            if len(address) == 70:
                try:
                    value = state_view.get(address)
                except KeyError:
                    # if the key is missing, leave it out of the response
                    continue

                result.append((address, value))
                continue

            # an address prefix
            leaves = state_view.leaves(address)

            for leaf in leaves:
                result.append(leaf)

        return result

    def _get_blocks(self, block_ids):
        try:
            return [
                self._block_cache[block_id.hex()]
                for block_id in block_ids
            ]
        except KeyError:
            raise UnknownBlock()

    def _wrap_consensus_message(self, content, message_type, connection_id):
        _, name, version = self._consensus_registry.get_engine_info()
        header = ConsensusPeerMessageHeader(
            signer_id=self._public_key,
            content_sha512=hashlib.sha512(content).digest(),
            message_type=message_type,
            name=name,
            version=version,
        ).SerializeToString()

        signature = bytes.fromhex(self._identity_signer.sign(header))
        message = ConsensusPeerMessage(
            header=header,
            content=content,
            header_signature=signature)

        return message
