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


class ClientHandler(object):
    # The validator will use this handler to deal with client/get messages
    # it recieves from a client
    def handle(self, message, responder):
        print("Message recieved", message)
        responder.send(validator_pb2.Message(
            sender=message.sender,
            message_type="client/get_response",
            correlation_id=message.correlation_id,
            content="{ 'status': 'SUCCESS' }".encode()))
