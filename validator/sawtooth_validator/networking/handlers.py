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
import logging

from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf.network_pb2 import ConnectMessage
from sawtooth_validator.protobuf.network_pb2 import DisconnectMessage
from sawtooth_validator.protobuf.network_pb2 import PingRequest
from sawtooth_validator.protobuf.network_pb2 import NetworkAcknowledgement

LOGGER = logging.getLogger(__name__)


class ConnectHandler(Handler):
    def __init__(self, network):
        self._network = network

    def handle(self, connection_id, message_content):
        message = ConnectMessage()
        message.ParseFromString(message_content)
        LOGGER.debug("got connect message from %s. sending ack",
                     connection_id)

        ack = NetworkAcknowledgement()

        if self._network.allow_inbound_connection():
            LOGGER.debug("Allowing incoming connection: %s",
                         connection_id)
            ack.status = ack.OK
        else:
            LOGGER.debug("At max connections, sending error response")
            ack.status = ack.ERROR

        return HandlerResult(HandlerStatus.RETURN,
                             message_out=ack,
                             message_type=validator_pb2.Message.NETWORK_ACK)


class DisconnectHandler(Handler):
    def __init__(self, network):
        self._network = network

    def handle(self, connection_id, message_content):
        message = DisconnectMessage()
        message.ParseFromString(message_content)
        LOGGER.debug("got disconnect message from %s. sending ack",
                     connection_id)

        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        return HandlerResult(HandlerStatus.RETURN,
                             message_out=ack,
                             message_type=validator_pb2.Message.NETWORK_ACK)


class PingHandler(Handler):

    def handle(self, connection_id, message_content):
        request = PingRequest()
        request.ParseFromString(message_content)

        ack = NetworkAcknowledgement()
        ack.status = ack.OK

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.NETWORK_ACK)
