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

from sawtooth_signing import create_context
from sawtooth_signing.secp256k1 import Secp256k1PublicKey

from sawtooth_validator.protobuf import client_batch_submit_pb2
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
from sawtooth_validator.journal.timed_cache import TimedCache


LOGGER = logging.getLogger(__name__)


def is_valid_block(block):
    # validate block signature
    header = BlockHeader()
    header.ParseFromString(block.header)

    context = create_context('secp256k1')
    public_key = Secp256k1PublicKey.from_hex(header.signer_public_key)
    if not context.verify(block.header_signature,
                          block.header,
                          public_key):
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

    context = create_context('secp256k1')
    public_key = Secp256k1PublicKey.from_hex(header.signer_public_key)
    if not context.verify(batch.header_signature,
                          batch.header,
                          public_key):
        LOGGER.debug("batch failed signature validation: %s",
                     batch.header_signature)
        return False

    # validate all transactions in batch
    for txn in batch.transactions:
        if not is_valid_transaction(txn):
            return False

        txn_header = TransactionHeader()
        txn_header.ParseFromString(txn.header)
        if txn_header.batcher_public_key != header.signer_public_key:
            LOGGER.debug("txn batcher public_key does not match signer"
                         "public_key for batch: %s txn: %s",
                         batch.header_signature,
                         txn.header_signature)
            return False

    return True


def is_valid_transaction(txn):
    # validate transactions signature
    header = TransactionHeader()
    header.ParseFromString(txn.header)

    context = create_context('secp256k1')
    public_key = Secp256k1PublicKey.from_hex(header.signer_public_key)
    if not context.verify(txn.header_signature,
                          txn.header,
                          public_key):
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
    def __init__(self):
        self._seen_cache = TimedCache()

    def handle(self, connection_id, message_content):
        gossip_message = GossipMessage()
        gossip_message.ParseFromString(message_content)

        if gossip_message.content_type == GossipMessage.BLOCK:
            block = Block()
            block.ParseFromString(gossip_message.content)

            if block.header_signature in self._seen_cache:
                LOGGER.debug("Drop already validated block: %s",
                             block.header_signature)
                return HandlerResult(status=HandlerStatus.DROP)

            if not is_valid_block(block):
                LOGGER.debug("block signature is invalid: %s",
                             block.header_signature)
                return HandlerResult(status=HandlerStatus.DROP)

            self._seen_cache[block.header_signature] = None
            return HandlerResult(status=HandlerStatus.PASS)

        elif gossip_message.content_type == GossipMessage.BATCH:
            batch = Batch()
            batch.ParseFromString(gossip_message.content)
            if batch.header_signature in self._seen_cache:
                LOGGER.debug("Drop already validated batch: %s",
                             batch.header_signature)
                return HandlerResult(status=HandlerStatus.DROP)

            if not is_valid_batch(batch):
                LOGGER.debug("batch signature is invalid: %s",
                             batch.header_signature)
                return HandlerResult(status=HandlerStatus.DROP)

            self._seen_cache[batch.header_signature] = None
            return HandlerResult(status=HandlerStatus.PASS)

        # should drop the message if it does not have a valid content_type
        return HandlerResult(status=HandlerStatus.DROP)


class GossipBlockResponseSignatureVerifier(Handler):
    def __init__(self):
        self._seen_cache = TimedCache()

    def handle(self, connection_id, message_content):
        block_response_message = GossipBlockResponse()
        block_response_message.ParseFromString(message_content)
        block = Block()
        block.ParseFromString(block_response_message.content)
        if block.header_signature in self._seen_cache:
            LOGGER.debug("Drop already validated block: %s",
                         block.header_signature)
            return HandlerResult(status=HandlerStatus.DROP)

        if not is_valid_block(block):
            LOGGER.debug("requested block's signature is invalid: %s",
                         block.header_signature)
            return HandlerResult(status=HandlerStatus.DROP)

        self._seen_cache = TimedCache()
        return HandlerResult(status=HandlerStatus.PASS)


class GossipBatchResponseSignatureVerifier(Handler):
    def __init__(self):
        self._seen_cache = TimedCache()

    def handle(self, connection_id, message_content):
        batch_response_message = GossipBatchResponse()
        batch_response_message.ParseFromString(message_content)

        batch = Batch()
        batch.ParseFromString(batch_response_message.content)
        if batch.header_signature in self._seen_cache:
            LOGGER.debug("Drop already validated batch: %s",
                         batch.header_signature)
            return HandlerResult(status=HandlerStatus.DROP)

        if not is_valid_batch(batch):
            LOGGER.debug("requested batch's signature is invalid: %s",
                         batch.header_signature)
            return HandlerResult(status=HandlerStatus.DROP)

        self._seen_cache[batch.header_signature] = None
        return HandlerResult(status=HandlerStatus.PASS)


class BatchListSignatureVerifier(Handler):
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
