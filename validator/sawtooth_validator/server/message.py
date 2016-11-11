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

import sawtooth_validator.protobuf.validator_pb2 as validator_pb2


class Message(object):
    def __init__(self, message_type, correlation_id, content):
        self.message_type = message_type
        self.correlation_id = correlation_id
        self.content = content
        self.sender = None

    def to_pb2(self):
        return validator_pb2.Message(
            message_type=self.message_type,
            correlation_id=self.correlation_id,
            content=self.content)

    @staticmethod
    def from_pb2(pb2_message):
        message = Message(
            message_type=pb2_message.message_type,
            correlation_id=pb2_message.correlation_id,
            content=pb2_message.content)
        return message
