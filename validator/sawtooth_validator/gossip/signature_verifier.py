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
import hashlib
# pylint: disable=import-error,no-name-in-module
# needed for google.protobuf import
from google.protobuf.message import DecodeError

import sawtooth_signing as signing

from sawtooth_validator.protobuf import client_pb2
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.network_pb2 import GossipMessage
from sawtooth_validator.protobuf.network_pb2 import GossipBlockResponse
from sawtooth_validator.protobuf.network_pb2 import GossipBatchResponse
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.protobuf.validator_pb2 import Message


LOGGER = logging.getLogger(__name__)


def is_valid_block(block):
    # validate block signature
    header = BlockHeader()
    header.ParseFromString(block.header)

    if not signing.verify(block.header,
                          block.header_signature,
                          header.signer_pubkey):
        LOGGER.debug("block failed signature validation: %s",
                     block.header_signature)
        return False

    # validate all batches in block. These are not all batches in the
    # batch_ids stored in the block header, only those sent with the block.
    if not all(map(is_valid_batch, block.batches)):
        return False

    return True


def is_valid_batch(batch):
    # validate batch signature
    header = BatchHeader()
    header.ParseFromString(batch.header)

    if not signing.verify(batch.header,
                          batch.header_signature,
                          header.signer_pubkey):
        LOGGER.debug("batch failed signature validation: %s",
                     batch.header_signature)
        return False

    # validate all transactions in batch
    for txn in batch.transactions:
        if not is_valid_transaction(txn):
            return False

        txn_header = TransactionHeader()
        txn_header.ParseFromString(txn.header)
        if txn_header.batcher_pubkey != header.signer_pubkey:
            LOGGER.debug("txn batcher pubkey does not match signer"
                         "pubkey for batch: %s txn: %s",
                         batch.header_signature,
                         txn.header_signature)
            return False

    return True


def is_valid_transaction(txn):
    # validate transactions signature
    header = TransactionHeader()
    header.ParseFromString(txn.header)

    if not signing.verify(txn.header,
                          txn.header_signature,
                          header.signer_pubkey):
        LOGGER.debug("transaction signature invalid for txn: %s",
                     txn.header_signature)
        return False

    # verify the payload field matches the header
    txn_payload_sha512 = hashlib.sha512(txn.payload).hexdigest()
    if txn_payload_sha512 != header.payload_sha512:
        LOGGER.debug("payload doesn't match payload_sha512 of the header"
                     "for txn: %s", txn.header_signature)
        return False

    return True


class GossipMessageSignatureVerifier(Handler):

    def handle(self, connection_id, message_content):
        gossip_message = GossipMessage()
        gossip_message.ParseFromString(message_content)
        if gossip_message.content_type == "BLOCK":
            block = Block()
            block.ParseFromString(gossip_message.content)
            if not is_valid_block(block):
                LOGGER.debug("block signature is invalid: %s",
                             block.header_signature)
                return HandlerResult(status=HandlerStatus.DROP)

            LOGGER.debug("block passes signature verification %s",
                         block.header_signature)
            return HandlerResult(status=HandlerStatus.PASS)
        elif gossip_message.content_type == "BATCH":
            batch = Batch()
            batch.ParseFromString(gossip_message.content)
            if not is_valid_batch(batch):
                LOGGER.debug("batch signature is invalid: %s",
                             batch.header_signature)
                return HandlerResult(status=HandlerStatus.DROP)

            LOGGER.debug("batch passes signature verification %s",
                         batch.header_signature)
            return HandlerResult(status=HandlerStatus.PASS)

        return HandlerResult(status=HandlerStatus.PASS)


class GossipBlockResponseSignatureVerifier(Handler):
    def handle(self, connection_id, message_content):
        block_response_message = GossipBlockResponse()
        block_response_message.ParseFromString(message_content)
        block = Block()
        block.ParseFromString(block_response_message.content)
        if not is_valid_block(block):
            LOGGER.debug("requested block's signature is invalid: %s",
                         block.header_signature)
            return HandlerResult(status=HandlerStatus.DROP)

        LOGGER.debug("requested block passes signature verification %s",
                     block.header_signature)
        return HandlerResult(status=HandlerStatus.PASS)


class GossipBatchResponseSignatureVerifier(Handler):
    def handle(self, connection_id, message_content):
        batch_response_message = GossipBatchResponse()
        batch_response_message.ParseFromString(message_content)

        batch = Batch()
        batch.ParseFromString(batch_response_message.content)
        if not is_valid_batch(batch):
            LOGGER.debug("requested batch's signature is invalid: %s",
                         batch.header_signature)
            return HandlerResult(status=HandlerStatus.DROP)

        LOGGER.debug("requested batch passes signature verification %s",
                     batch.header_signature)
        return HandlerResult(status=HandlerStatus.PASS)


class BatchListSignatureVerifier(Handler):

    def handle(self, connection_id, message_content):
        response_proto = client_pb2.ClientBatchSubmitResponse

        def make_response(out_status):
            return HandlerResult(
                status=HandlerStatus.RETURN,
                message_out=response_proto(status=out_status),
                message_type=Message.CLIENT_BATCH_SUBMIT_RESPONSE)
        try:
            request = client_pb2.ClientBatchSubmitRequest()
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
