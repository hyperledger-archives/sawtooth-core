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

from sawtooth_signing import create_context
from sawtooth_signing.secp256k1 import Secp256k1PublicKey

from sawtooth_validator.protobuf import client_batch_submit_pb2
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.consensus_pb2 import \
    ConsensusPeerMessageHeader
from sawtooth_validator.protobuf.network_pb2 import GossipMessage
from sawtooth_validator import metrics
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.protobuf.validator_pb2 import Message
from sawtooth_validator.journal.timed_cache import TimedCache


LOGGER = logging.getLogger(__name__)
COLLECTOR = metrics.get_collector(__name__)


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


def is_valid_consensus_message(message):
    # validate consensus message signature
    header = ConsensusPeerMessageHeader()
    header.ParseFromString(message.header)

    context = create_context('secp256k1')
    public_key = Secp256k1PublicKey.from_bytes(header.signer_id)
    if not context.verify(message.header_signature,
                          message.header,
                          public_key):
        LOGGER.debug("message signature invalid for message: %s",
                     message.header_signature)
        return False

    # verify the message field matches the header
    content_sha512 = hashlib.sha512(message.content).digest()
    if content_sha512 != header.content_sha512:
        LOGGER.debug("message doesn't match content_sha512 of the header for"
                     "message envelope: %s", message.header_signature)
        return False

    return True


class GossipMessageSignatureVerifier(Handler):
    def __init__(self):
        self._seen_cache = TimedCache()
        self._batch_dropped_count = COLLECTOR.counter(
            'already_validated_batch_dropped_count', instance=self)
        self._block_dropped_count = COLLECTOR.counter(
            'already_validated_block_dropped_count', instance=self)

    def handle(self, connection_id, message_content):
        obj, tag, _ = message_content

        if tag == GossipMessage.BLOCK:
            if obj.header_signature in self._seen_cache:
                self._block_dropped_count.inc()
                return HandlerResult(status=HandlerStatus.DROP)

            if not is_valid_block(obj):
                LOGGER.debug("block signature is invalid: %s",
                             obj.header_signature)
                return HandlerResult(status=HandlerStatus.DROP)

            self._seen_cache[obj.header_signature] = None
            return HandlerResult(status=HandlerStatus.PASS)

        if tag == GossipMessage.BATCH:
            if obj.header_signature in self._seen_cache:
                self._batch_dropped_count.inc()
                return HandlerResult(status=HandlerStatus.DROP)

            if not is_valid_batch(obj):
                LOGGER.debug("batch signature is invalid: %s",
                             obj.header_signature)
                return HandlerResult(status=HandlerStatus.DROP)

            self._seen_cache[obj.header_signature] = None
            return HandlerResult(status=HandlerStatus.PASS)

        if tag == GossipMessage.CONSENSUS:
            if not is_valid_consensus_message(obj):
                return HandlerResult(status=HandlerStatus.DROP)

            return HandlerResult(status=HandlerStatus.PASS)

        # should drop the message if it does not have a valid content_type
        return HandlerResult(status=HandlerStatus.DROP)


class GossipBlockResponseSignatureVerifier(Handler):
    def __init__(self):
        self._seen_cache = TimedCache()
        self._block_dropped_count = COLLECTOR.counter(
            'already_validated_block_dropped_count', instance=self)

    def handle(self, connection_id, message_content):
        block, _ = message_content

        if block.header_signature in self._seen_cache:
            self._block_dropped_count.inc()
            return HandlerResult(status=HandlerStatus.DROP)

        if not is_valid_block(block):
            LOGGER.debug("requested block's signature is invalid: %s",
                         block.header_signature)
            return HandlerResult(status=HandlerStatus.DROP)

        self._seen_cache[block.header_signature] = None
        return HandlerResult(status=HandlerStatus.PASS)


class GossipBatchResponseSignatureVerifier(Handler):
    def __init__(self):
        self._seen_cache = TimedCache()
        self._batch_dropped_count = COLLECTOR.counter(
            'already_validated_batch_dropped_count', instance=self)

    def handle(self, connection_id, message_content):
        batch, _ = message_content

        if batch.header_signature in self._seen_cache:
            self._batch_dropped_count.inc()
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

        for batch in message_content.batches:
            if batch.trace:
                LOGGER.debug("TRACE %s: %s", batch.header_signature,
                             self.__class__.__name__)

        if not all(map(is_valid_batch, message_content.batches)):
            return make_response(response_proto.INVALID_BATCH)

        return HandlerResult(status=HandlerStatus.PASS)
