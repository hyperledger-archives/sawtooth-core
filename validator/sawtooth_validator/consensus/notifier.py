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

import ctypes
from enum import IntEnum
import hashlib
import logging


from sawtooth_validator import ffi
from sawtooth_validator.ffi import PY_LIBRARY
from sawtooth_validator.ffi import LIBRARY
from sawtooth_validator.ffi import CommonErrorCode
from sawtooth_validator.ffi import OwnedPointer
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf import consensus_pb2
from sawtooth_validator.protobuf import validator_pb2

LOGGER = logging.getLogger(__name__)


class _NotifierService:
    def __init__(self, consensus_service, registered_engines):
        self._service = consensus_service
        self._registered_engines = registered_engines

    def notify(self, message_type, message):
        message_bytes = bytes(message)
        LOGGER.critical("type=%s, message=%s", message_type, message_bytes)
        if self._registered_engines:
            futures = self._service.send_all(
                message_type,
                message_bytes)
            for future in futures:
                future.result()


class ErrorCode(IntEnum):
    Success = 0
    NullPointerProvided = 0x01
    InvalidArgument = 0x02


class ConsensusNotifier(ffi.OwnedPointer):
    """Handles sending notifications to the consensus engine using the provided
    interconnect service."""

    def __init__(self, consensus_service, registered_engines):
        super().__init__('consensus_notifier_drop')

        self._notifier_service = _NotifierService(
            consensus_service,
            registered_engines)

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
            ctypes.c_char_p(sender_id.encode()))

    def notify_block_new(self, block):
        """A new block was received and passed initial consensus validation"""
        payload = block.SerializeToString()
        self._notify("consensus_notifier_block_new", payload, len(payload))

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
