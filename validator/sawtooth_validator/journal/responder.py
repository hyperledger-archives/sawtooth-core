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

from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.protobuf import network_pb2
from sawtooth_validator.protobuf import validator_pb2

LOGGER = logging.getLogger(__name__)


class Responder(object):
    def __init__(self, completer):
        self.completer = completer

    def check_for_block(self, block_id):
        # Ask Completer
        if block_id == "HEAD":
            block = self.completer.get_chain_head()
        else:
            block = self.completer.get_block(block_id)
        return block

    def check_for_batch(self, batch_id):
        batch = self.completer.get_batch(batch_id)
        return batch

    def check_for_batch_by_transaction(self, transaction_id):
        batch = self.completer.get_batch_by_transaction(transaction_id)
        return batch


class BlockResponderHandler(Handler):
    def __init__(self, responder, gossip):
        self._responder = responder
        self._gossip = gossip

    def handle(self, connection_id, message_content):
        block_request_message = network_pb2.GossipBlockRequest()
        block_request_message.ParseFromString(message_content)
        block_id = block_request_message.block_id
        node_id = block_request_message.node_id
        block = self._responder.check_for_block(block_id)
        if block is None:
            # No block found, broadcast orignal message to other peers
            self._gossip.broadcast(block_request_message,
                                   validator_pb2.Message.GOSSIP_BLOCK_REQUEST)
        else:
            LOGGER.debug("Responding to block requests: %s",
                         block.get_block().header_signature)

            block_response = network_pb2.GossipBlockResponse(
                content=block.get_block().SerializeToString(),
                node_id=node_id)

            self._gossip.send(validator_pb2.Message.GOSSIP_BLOCK_RESPONSE,
                              block_response.SerializeToString(),
                              connection_id)

        return HandlerResult(status=HandlerStatus.PASS)


class BatchByBatchIdResponderHandler(Handler):
    def __init__(self, responder, gossip):
        self._responder = responder
        self._gossip = gossip

    def handle(self, connection_id, message_content):
        batch_request_message = network_pb2.GossipBatchByBatchIdRequest()
        batch_request_message.ParseFromString(message_content)
        batch = None
        batch = self._responder.check_for_batch(batch_request_message.id)
        node_id = batch_request_message.node_id

        if batch is None:
            self._gossip.broadcast(
                batch_request_message,
                validator_pb2.Message.GOSSIP_BATCH_BY_BATCH_ID_REQUEST)
        else:
            LOGGER.debug("Responding to batch requests %s",
                         batch.header_signature)

            batch_response = network_pb2.GossipBatchResponse(
                content=batch.SerializeToString(),
                node_id=node_id)

            self._gossip.send(validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
                              batch_response.SerializeToString(),
                              connection_id)

        return HandlerResult(status=HandlerStatus.PASS)


class BatchByTransactionIdResponderHandler(Handler):
    def __init__(self, responder, gossip):
        self._responder = responder
        self._gossip = gossip

    def handle(self, connection_id, message_content):
        batch_request_message = network_pb2.GossipBatchByTransactionIdRequest()
        batch_request_message.ParseFromString(message_content)
        node_id = batch_request_message.node_id
        batch = None
        batches = []
        unfound_txn_ids = []
        for txn_id in batch_request_message.ids:
            batch = self._responder.check_for_batch_by_transaction(
                txn_id)

            # The txn_id was not found.
            if batch is None:
                unfound_txn_ids.append(txn_id)

            # Check to see if a previous txn was in the same batch.
            elif batch not in batches:
                batches.append(batch)

            batch = None

        if batches == []:
            self._gossip.broadcast(
                batch_request_message,
                validator_pb2.Message.
                GOSSIP_BATCH_BY_TRANSACTION_ID_REQUEST)

        elif unfound_txn_ids != []:
            new_request = network_pb2.GossipBatchByTransactionIdRequest()
            new_request.ids.extend(unfound_txn_ids)
            new_request.node_id = batch_request_message.node_id
            self._gossip.broadcast(
                new_request,
                validator_pb2.Message.
                GOSSIP_BATCH_BY_TRANSACTION_ID_REQUEST)

        if batches != []:
            for batch in batches:
                LOGGER.debug("Responding to batch requests %s",
                             batch.header_signature)

                batch_response = network_pb2.GossipBatchResponse(
                    content=batch.SerializeToString(),
                    node_id=node_id)

                self._gossip.send(validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
                                  batch_response.SerializeToString(),
                                  connection_id)

        return HandlerResult(status=HandlerStatus.PASS)
