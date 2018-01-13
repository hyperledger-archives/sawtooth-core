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
# pylint: disable=import-error,no-name-in-module
# needed for google.protobuf import
from google.protobuf.message import DecodeError

from sawtooth_validator.protobuf import client_batch_submit_pb2
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf import network_pb2
from sawtooth_validator.protobuf.network_pb2 import GossipBlockResponse
from sawtooth_validator.protobuf.network_pb2 import GossipBatchResponse
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.protobuf.validator_pb2 import Message

LOGGER = logging.getLogger(__name__)


def is_valid_block(block):
    # block structure verification
    header = BlockHeader()
    header.ParseFromString(block.header)

    if len(header.batch_ids) != len(set(header.batch_ids)):
        LOGGER.debug("Block has duplicate batches. Dropping block: %s",
                     block.header_signature)
        return False

    if not all(map(is_valid_batch, block.batches)):
        return False

    return True


def is_valid_batch(batch):
    # batch structure verification
    header = BatchHeader()
    header.ParseFromString(batch.header)

    # check whether a batch has duplicate transactions
    if len(header.transaction_ids) != len(set(header.transaction_ids)):
        LOGGER.debug("Batch has duplicate transactions. Dropping batch: %s",
                     batch.header_signature)
        return False

    # validate the transaction_ids field in batch header contains a list of
    # transaction header_signatures and must be the same order as the
    # transactions field
    if len(batch.transactions) > len(header.transaction_ids):
        LOGGER.debug("Batch has extra transactions. Dropping batch: %s",
                     batch.header_signature)
        return False
    elif len(batch.transactions) < len(header.transaction_ids):
        LOGGER.debug("Batch lacks transactions. Dropping batch: %s",
                     batch.header_signature)
        return False

    for header_txn_id, txn in zip(header.transaction_ids, batch.transactions):
        if header_txn_id != txn.header_signature:
            LOGGER.debug("The header.transaction_ids does not match the "
                         "order of transactions in the batch: %s txn: %s",
                         batch.header_signature, header_txn_id)
            return False

    return True


class GossipHandlerStructureVerifier(Handler):
    def handle(self, connection_id, message_content):
        gossip_message = network_pb2.GossipMessage()
        gossip_message.ParseFromString(message_content)
        if gossip_message.content_type == network_pb2.GossipMessage.BLOCK:
            block = Block()
            block.ParseFromString(gossip_message.content)
            if not is_valid_block(block):
                LOGGER.debug("block's batches structure is invalid: %s",
                             block.header_signature)
                return HandlerResult(status=HandlerStatus.DROP)

            return HandlerResult(status=HandlerStatus.PASS)
        elif gossip_message.content_type == network_pb2.GossipMessage.BATCH:
            batch = Batch()
            batch.ParseFromString(gossip_message.content)
            if not is_valid_batch(batch):
                LOGGER.debug("batch structure is invalid: %s",
                             batch.header_signature)
                return HandlerResult(status=HandlerStatus.DROP)

            return HandlerResult(status=HandlerStatus.PASS)

        return HandlerResult(status=HandlerStatus.PASS)


class GossipBlockResponseStructureVerifier(Handler):
    def handle(self, connection_id, message_content):
        block_response_message = GossipBlockResponse()
        block_response_message.ParseFromString(message_content)

        block = Block()
        block.ParseFromString(block_response_message.content)
        if not is_valid_block(block):
            LOGGER.debug("requested block's batches structure is invalid: %s",
                         block.header_signature)
            return HandlerResult(status=HandlerStatus.DROP)

        return HandlerResult(status=HandlerStatus.PASS)


class GossipBatchResponseStructureVerifier(Handler):
    def handle(self, connection_id, message_content):
        batch_response_message = GossipBatchResponse()
        batch_response_message.ParseFromString(message_content)

        batch = Batch()
        batch.ParseFromString(batch_response_message.content)
        if not is_valid_batch(batch):
            LOGGER.debug("requested batch's structure is invalid: %s",
                         batch.header_signature)
            return HandlerResult(status=HandlerStatus.DROP)

        return HandlerResult(status=HandlerStatus.PASS)


class BatchListStructureVerifier(Handler):
    def handle(self, connection_id, message_content):
        response_proto = client_batch_submit_pb2.ClientBatchSubmitResponse

        def make_response(out_status):
            return HandlerResult(
                status=HandlerStatus.RETURN,
                message_out=response_proto(status=out_status),
                message_type=Message.CLIENT_BATCH_SUBMIT_RESPONSE)

        try:
            request = client_batch_submit_pb2.ClientBatchSubmitRequest()
            request.ParseFromString(message_content)
        except DecodeError:
            return make_response(response_proto.INTERNAL_ERROR)

        for batch in request.batches:
            if batch.trace:
                LOGGER.debug("TRACE %s: %s", batch.header_signature,
                             self.__class__.__name__)

        if not all(map(is_valid_batch, request.batches)):
            return make_response(response_proto.INVALID_BATCH)

        return HandlerResult(status=HandlerStatus.PASS)
