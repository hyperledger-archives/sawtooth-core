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

from threading import RLock
import time

from sawtooth_validator.networking import dispatch
from sawtooth_validator.protobuf import validator_pb2


class MockHandler1(dispatch.Handler):
    def __init__(self):
        self._time_to_sleep = 2.0

    def handle(self, connection_id, message_content):
        if self._time_to_sleep > 0:
            time.sleep(self._time_to_sleep)
            self._time_to_sleep -= 0.1
        return dispatch.HandlerResult(
            dispatch.HandlerStatus.PASS)


class MockHandler2(dispatch.Handler):
    def handle(self, connection_id, message_content):
        request = validator_pb2.Message()
        request.ParseFromString(message_content)
        return dispatch.HandlerResult(
            dispatch.HandlerStatus.RETURN,
            message_out=validator_pb2.Message(
                correlation_id=request.correlation_id,
            ),
            message_type=validator_pb2.Message.DEFAULT)


class MockSendMessage:
    def __init__(self, connections):
        self.message_ids = []
        self.identities = []
        self._lock = RLock()
        self.connections = connections

    def send_message(self, connection_id, msg):
        with self._lock:
            message = validator_pb2.Message()
            message.ParseFromString(msg.content)
            self.identities.append(self.connections[connection_id])
            self.message_ids.append(message.correlation_id)
