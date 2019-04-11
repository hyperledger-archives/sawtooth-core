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

from collections import deque
import ctypes
from enum import IntEnum
import logging


from sawtooth_validator import ffi
from sawtooth_validator.ffi import PY_LIBRARY
from sawtooth_validator.ffi import LIBRARY
from sawtooth_validator.ffi import CommonErrorCode
from sawtooth_validator.networking.future import FutureTimeoutError
from sawtooth_validator.networking.interconnect import get_enum_name
from sawtooth_validator.protobuf.validator_pb2 import Message

LOGGER = logging.getLogger(__name__)

NOTIFICATION_TIMEOUT = 10


class _NotifierService:
    def __init__(self, consensus_service, consensus_registry, public_key):
        self._service = consensus_service
        self._consensus_registry = consensus_registry
        self._public_key = public_key
        self._gossip = None
        self._message_backlog = deque()

    def notify(self, message_type, message):
        self._queue_backlog(message_type, message)
        active_engine = self._consensus_registry.get_active_engine_info()
        if active_engine is not None:
            for (queued_type, queued_msg) in self._drain_backlog():
                try:
                    self._service.send(
                        queued_type,
                        bytes(queued_msg),
                        active_engine.connection_id
                    ).result(timeout=NOTIFICATION_TIMEOUT)
                except FutureTimeoutError:
                    LOGGER.warning(
                        "Consensus notification %s timed out",
                        get_enum_name(queued_type))

    def notify_id(self, message_type, message, connection_id):
        self._service.send(
            message_type,
            bytes(message),
            connection_id
        ).result()

    def set_gossip(self, gossip):
        self._gossip = gossip

    def get_peers_public_keys(self):
        return (
            self._gossip.get_peers_public_keys()
            if self._gossip is not None
            else None
        )

    def get_public_key(self):
        return self._public_key

    def _queue_backlog(self, message_type, message):
        if message_type == Message.CONSENSUS_NOTIFY_ENGINE_ACTIVATED:
            self._message_backlog.appendleft((message_type, message))
        else:
            self._message_backlog.append((message_type, message))

    def _drain_backlog(self):
        while True:
            try:
                yield self._message_backlog.popleft()
            except IndexError:
                break


class ErrorCode(IntEnum):
    Success = CommonErrorCode.Success
    NullPointerProvided = CommonErrorCode.NullPointerProvided
    InvalidArgument = 0x02


class ConsensusNotifier(ffi.OwnedPointer):
    """Handles sending notifications to the consensus engine using the provided
    interconnect service."""

    def __init__(self, consensus_service, consensus_registry, public_key):
        super().__init__('consensus_notifier_drop')

        self._notifier_service = _NotifierService(
            consensus_service,
            consensus_registry,
            public_key)

        PY_LIBRARY.call(
            'consensus_notifier_new',
            ctypes.py_object(self._notifier_service),
            ctypes.byref(self.pointer))

    def _notify(self, fn_name, *args):
        return_code = LIBRARY.call(
            fn_name,
            self.pointer,
            *args)

        if return_code == ErrorCode.Success:
            return
        if return_code == ErrorCode.NullPointerProvided:
            raise TypeError("Provided null pointer(s)")
        if return_code == ErrorCode.InvalidArgument:
            raise ValueError("Input was not valid ")

    def notify_peer_connected(self, peer_id):
        """A new peer was added"""
        self._notify(
            "consensus_notifier_notify_peer_connected",
            ctypes.c_char_p(peer_id.encode()))

    def notify_peer_disconnected(self, peer_id):
        """An existing peer was dropped"""
        self._notify(
            "consensus_notifier_notify_peer_disconnected",
            ctypes.c_char_p(peer_id.encode()))

    def notify_peer_message(self, message, sender_id):
        """A new message was received from a peer"""
        payload = message.SerializeToString()
        self._notify(
            "consensus_notifier_notify_peer_message",
            payload,
            len(payload),
            sender_id,
            len(sender_id))

    def notify_block_new(self, block):
        """A new block was received and passed initial consensus validation"""
        payload = block.SerializeToString()
        self._notify(
            "consensus_notifier_notify_block_new", payload, len(payload))

    def notify_block_valid(self, block_id):
        """This block can be committed successfully"""
        self._notify(
            "consensus_notifier_notify_block_valid",
            ctypes.c_char_p(block_id.encode()))

    def notify_block_invalid(self, block_id):
        """This block cannot be committed successfully"""
        self._notify(
            "consensus_notifier_notify_block_invalid",
            ctypes.c_char_p(block_id.encode()))

    def notify_engine_activated(self, chain_head):
        """The consensus engine has been activated."""
        chain_head_bytes = chain_head.SerializeToString()
        self._notify(
            "consensus_notifier_notify_engine_activated",
            chain_head_bytes,
            len(chain_head_bytes))

    def notify_engine_deactivated(self, connection_id):
        """The consensus engine has been deactivated."""
        self._notify(
            "consensus_notifier_notify_engine_deactivated", connection_id)

    def set_gossip(self, gossip):
        self._notifier_service.set_gossip(gossip)
