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

from sawtooth_validator.protobuf import validator_pb2


class SystemLoadHandler(object):
    def __init__(self, network):
        self._network = network

    def handle(self, message, responder):
        self._network.load(message.content)

        responder.send(validator_pb2.Message(
            sender=message.sender,
            message_type=validator_pb2.Message.CLIENT_BATCH_SUBMIT_RESPONSE,
            correlation_id=message.correlation_id,
            content='{ "status": "SUCCESS" }'.encode()))
