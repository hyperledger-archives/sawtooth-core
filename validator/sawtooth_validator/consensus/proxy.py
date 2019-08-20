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
import logging

from sawtooth_validator.consensus.registry import EngineAlreadyActive
from sawtooth_validator.consensus.registry import EngineNotRegistered
from sawtooth_validator.journal.chain import ChainObserver
from sawtooth_validator.journal.event_extractors import \
    ReceiptEventExtractor
from sawtooth_validator.server.events.subscription import EventSubscription
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.consensus_pb2 import ConsensusPeerMessage
from sawtooth_validator.protobuf.consensus_pb2 import \
    ConsensusPeerMessageHeader


LOGGER = logging.getLogger(__name__)


class UnknownBlock(Exception):
    """The given block could not be found."""


class ConsensusActivationObserver(ChainObserver):
    """Observes chain updates and activates new engines, when the settings
    have been updated in state, as of the commit."""

    def __init__(self, consensus_registry, consensus_notifier,
                 settings_view_factory):
        self._registry = consensus_registry
        self._notifier = consensus_notifier
        self._settings_view_factory = settings_view_factory

    def chain_update(self, block, receipts):
        # Check to see if there is an active engine at all:
        if not self._registry.has_active_engine():
            self._update_active_engine(block)
            return

        # Otherwise, check to see if the settings changed, before updating
        # the active engine.
        receipt_events = ReceiptEventExtractor(receipts).extract([
            EventSubscription(event_type="setting/update")])

        for event in receipt_events:
            if self._is_consensus_algorithm_setting(event):
                self._update_active_engine(block)
                break

    def _update_active_engine(self, block):
        conf_name, conf_version = get_configured_engine(
            block, self._settings_view_factory)

        # Deactivate the old engine, if necessary
        old_engine_info = None
        if self._registry.has_active_engine():
            old_engine_info = self._registry.get_active_engine_info()

        try:
            self._registry.activate_engine(conf_name, conf_version)
        except EngineAlreadyActive:
            return
        except EngineNotRegistered:
            # We can ignore this, as the registration process will attempt
            # to activate the engine
            return

        if old_engine_info is not None:
            self._notifier.notify_engine_deactivated(
                old_engine_info.connection_id)
        self._notifier.notify_engine_activated(block)

        LOGGER.info(
            "Consensus engine %s %s activated as of block %s",
            conf_name,
            conf_version,
            block.header_signature)

    def _is_consensus_algorithm_setting(self, event):
        if event.event_type != 'setting/update':
            return False

        key = event.attributes[0].value
        return key in ('sawtooth.consensus.algorithm.name',
                       'sawtooth.consensus.algorithm.version')


class ConsensusProxy:
    """Receives requests from the consensus engine handlers and delegates them
    to the appropriate components."""

    def __init__(self, block_manager, block_publisher,
                 chain_controller, gossip, identity_signer,
                 settings_view_factory, state_view_factory,
                 consensus_registry, consensus_notifier):
        self._block_manager = block_manager
        self._chain_controller = chain_controller
        self._block_publisher = block_publisher
        self._gossip = gossip
        self._identity_signer = identity_signer
        self._public_key = self._identity_signer.get_public_key().as_bytes()
        self._settings_view_factory = settings_view_factory
        self._state_view_factory = state_view_factory
        self._consensus_registry = consensus_registry
        self._consensus_notifier = consensus_notifier

    def register(self, engine_name, engine_version,
                 additional_protocols, connection_id):
        self._consensus_registry.register_engine(
            connection_id, engine_name, engine_version, additional_protocols)

    def activate_if_configured(self, engine_name, engine_version,
                               additional_protocols):
        try:
            chain_head = self.chain_head_get()
        except UnknownBlock:
            LOGGER.debug(
                "Unable to determine if engine %s %s is configured until "
                "chain head received",
                engine_name,
                engine_version)
            return

        conf_name, conf_version = get_configured_engine(
            chain_head, self._settings_view_factory)

        if ((conf_name, conf_version) == (engine_name, engine_version)
                or (conf_name, conf_version) in additional_protocols):
            try:
                self._consensus_registry.activate_engine(
                    conf_name, conf_version)
            except EngineAlreadyActive:
                return
            except EngineNotRegistered:
                # The expectation is that this engine should have been
                # registered before calling this function
                LOGGER.error(
                    "Attempting to activate engine %s %s before it has been "
                    "registered with the validator",
                    engine_name,
                    engine_version)
                return

            self._consensus_notifier.notify_engine_activated(chain_head)

            LOGGER.info(
                "Consensus engine activated: %s %s",
                engine_name,
                engine_version)

    def is_active_engine_id(self, connection_id):
        return self._consensus_registry.is_active_engine_id(connection_id)

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
                previous_block = next(
                    self._block_manager.get([previous_id.hex()]))
            except StopIteration:
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
            if block_id.hex() not in self._block_manager:
                raise UnknownBlock(block_id.hex())

    def get_block_statuses(self, block_ids):
        """Returns a list of tuples of (block id, BlockStatus) pairs.
        """
        try:
            return [
                (block_id.hex(),
                 self._chain_controller.block_validation_result(
                     block_id.hex()))
                for block_id in block_ids
            ]
        except KeyError as key_error:
            raise UnknownBlock(key_error.args[0])

    def validate_block(self, block_id):
        """Instruct the chain controller to validate the given block."""
        try:
            block = next(self._block_manager.get([block_id]))
        except StopIteration as stop_iteration:
            raise UnknownBlock(stop_iteration.args[0])
        self._chain_controller.validate_block(block)

    def commit_block(self, block_id):
        try:
            block = next(self._block_manager.get([block_id.hex()]))
        except StopIteration as stop_iteration:
            raise UnknownBlock(stop_iteration.args[0])
        self._chain_controller.commit_block(block)

    def ignore_block(self, block_id):
        try:
            block = next(self._block_manager.get([block_id.hex()]))
        except StopIteration:
            raise UnknownBlock()
        self._chain_controller.ignore_block(block)

    def fail_block(self, block_id):
        try:
            block = next(self._block_manager.get([block_id.hex()]))
        except StopIteration:
            raise UnknownBlock()
        self._chain_controller.fail_block(block)

    # Using blockstore and state database
    def blocks_get(self, block_ids):
        '''Returns a list of blocks.'''
        return self._get_blocks([block_id.hex() for block_id in block_ids])

    def chain_head_get(self):
        '''Returns the chain head.'''

        chain_head = self._chain_controller.chain_head

        if chain_head is None:
            raise UnknownBlock()

        return chain_head

    def settings_get(self, block_id, settings):
        '''Returns a list of key/value pairs (str, str).'''

        block = self._get_blocks([block_id.hex()])[0]

        block_header = BlockHeader()
        block_header.ParseFromString(block.header)

        try:
            settings_view = self._settings_view_factory.create_settings_view(
                block_header.state_root_hash)
        except KeyError:
            LOGGER.error(
                'Settings from block %s requested, but root hash %s was '
                'missing. Returning no setting values.',
                block_id.hex(),
                block_header.state_root_hash)
            # The state root does not exist, which may indicate a pruned root
            # from a dropped fork or an invalid state.
            return []

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
        block = self._get_blocks([block_id.hex()])[0]
        block_header = BlockHeader()
        block_header.ParseFromString(block.header)

        try:
            state_view = self._state_view_factory.create_view(
                block_header.state_root_hash)
        except KeyError:
            LOGGER.error(
                'State from block %s requested, but root hash %s was missing. '
                'Returning empty state.',
                block_id.hex(),
                block_header.state_root_hash)
            # The state root does not exist, which may indicate a pruned root
            # from a dropped fork or an invalid state.
            return []

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
        block_iter = self._block_manager.get(block_ids)
        blocks = [b for b in block_iter]
        if len(blocks) != len(block_ids):
            raise UnknownBlock()

        return blocks

    def _wrap_consensus_message(self, content, message_type, connection_id):
        _, name, version, _ = self._consensus_registry.get_active_engine_info()
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


def get_configured_engine(block, settings_view_factory):
    header = BlockHeader()
    header.ParseFromString(block.header)
    settings_view = settings_view_factory.create_settings_view(
        header.state_root_hash)

    conf_name = settings_view.get_setting('sawtooth.consensus.algorithm.name')
    conf_version = settings_view.get_setting(
        'sawtooth.consensus.algorithm.version')

    # For backwards compatibility with 1.0:
    # - Use version "0.1" if sawtooth.consensus.algorithm.version is unset
    # - Use sawtooth.consensus.algorithm if sawtooth.consensus.algorithm.name
    #   is unset
    # - Use "Devmode" if sawtooth.consensus.algorithm is unset
    if conf_version is not None:
        version = conf_version
    else:
        version = "0.1"

    if conf_name is not None:
        name = conf_name
    else:
        algorithm = settings_view.get_setting('sawtooth.consensus.algorithm')
        if algorithm is not None:
            name = algorithm
        else:
            name = "Devmode"

    return name, version
