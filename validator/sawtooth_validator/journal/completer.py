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

import logging

from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.batch_pb2 import BatchList
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf import client_pb2
from sawtooth_validator.protobuf import network_pb2
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.server.dispatch import Handler
from sawtooth_validator.server.dispatch import HandlerResult
from sawtooth_validator.server.dispatch import HandlerStatus

LOGGER = logging.getLogger(__name__)


class Completer(object):
    def __init__(self):
        # temp batch cache
        self.batch_store = {}
        self.block_store = ["genesis"]
        self._on_block_received = None
        self._on_batch_received = None

    def _check_block(self, block, block_header):
        # currently only accepting finalized blocks
        # in the future if the blocks will be built

        if block_header.previous_block_id not in self.block_store:
            return False
        if len(block.batches) != len(block_header.batch_ids):
            return False

        for i in range(len(block.batches)):
            if block.batches[i].header_signature != block_header.batch_ids[i]:
                return False

        self.block_store.append(block.header_signature)
        return True

    def set_on_block_received(self, on_block_received_func):
        self._on_block_received = on_block_received_func

    def set_on_batch_received(self, on_batch_received_func):
        self._on_batch_received = on_batch_received_func

    def add_block(self, block):
        header = BlockHeader()
        header.ParseFromString(block.header)
        if self._check_block(block, header) is True:
            self._on_block_received(block)

    def add_batch(self, batch):
        self.batch_store[batch.header_signature] = batch
        self._on_batch_received(batch)


class CompleterBatchListBroadcastHandler(Handler):

    def __init__(self, completer, gossip):
        self._completer = completer
        self._gossip = gossip

    def handle(self, identity, message_content):
        batch_list = BatchList()
        batch_list.ParseFromString(message_content)
        for batch in batch_list.batches:
            self._completer.add_batch(batch)
            self._gossip.broadcast_batch(batch)
        message = client_pb2.ClientBatchSubmitResponse(
            status=client_pb2.ClientBatchSubmitResponse.OK)
        return HandlerResult(
            status=HandlerStatus.RETURN,
            message_out=message,
            message_type=validator_pb2.Message.CLIENT_BATCH_SUBMIT_RESPONSE)


class CompleterGossipHandler(Handler):

    def __init__(self, completer):
        self._completer = completer

    def handle(self, identity, message_content):
        gossip_message = network_pb2.GossipMessage()
        gossip_message.ParseFromString(message_content)
        if gossip_message.content_type == "BLOCK":
            block = Block()
            block.ParseFromString(gossip_message.content)
            self._completer.add_block(block)
        elif gossip_message.content_type == "BATCH":
            batch = Batch()
            batch.ParseFromString(gossip_message.content)
            self._completer.add_batch(batch)
        return HandlerResult(
            status=HandlerStatus.PASS)
