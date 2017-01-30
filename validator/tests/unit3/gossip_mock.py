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

from sawtooth_validator.protobuf import batch_pb2
from sawtooth_validator.protobuf import block_pb2


class GossipMock(object):
    def __init__(self):
        self.messages = []

        def nop_callback(msg):
            pass

        self.on_batch_received = nop_callback
        self.on_block_received = nop_callback
        self.on_block_requested = nop_callback

    def send_message(self, message):
        self.messages.append(message)

    @property
    def has_messages(self):
        return len(self.messages) != 0

    def dispatch_messages(self):
        while self.has_messages:
            self.dispatch_message()

    def dispatch_message(self):
        msg = self.messages.pop()
        if isinstance(msg, str):
            if self.on_block_request is not None:
                self.on_block_request(msg)
        elif isinstance(msg, block_pb2.Block):
            if self.on_block_received is not None:
                self.on_block_received(msg)
        elif isinstance(msg, batch_pb2.Batch):
            if self.on_batch_received is not None:
                self.on_batch_received(msg)

    def clear(self):
        self.messages = []
