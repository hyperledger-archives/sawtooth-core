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
from sawtooth_validator.protobuf.network_pb2 import GossipMessage
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf.network_pb2 import PeerRegisterRequest


class Gossip(object):
    def __init__(self, network):
        self._network = network

    def broadcast_block(self, block):
        gossip_message = GossipMessage(
            content_type="BLOCK",
            content=block.SerializeToString())

        self._broadcast(gossip_message)

    def broadcast_batch(self, batch):
        gossip_message = GossipMessage(
            content_type="BATCH",
            content=batch.SerializeToString())

        self._broadcast(gossip_message)

    def _broadcast(self, gossip_message):
        message_type = validator_pb2.Message.GOSSIP_MESSAGE
        for connection in self._network.connections:
            connection.send(message_type, gossip_message.SerializeToString())

    def broadcast_peer_request(self, message_type, message):
        for connection in self._network.connections:
            connection.send(message_type, message.SerializeToString())

    def start(self):
        for connection in self._network.connections:
            connection.start(daemon=True)
        register_request = PeerRegisterRequest()
        self.broadcast_peer_request(
            validator_pb2.Message.GOSSIP_REGISTER,
            register_request)
