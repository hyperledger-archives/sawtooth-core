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
# pylint: disable=import-error,no-name-in-module
# needed for google.protobuf import
from google.protobuf.message import DecodeError

from sawtooth_signing import secp256k1_signer as signing

from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader, BatchList
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.block_pb2 import BlockHeader, Block
from sawtooth_validator.protobuf.network_pb2 import GossipMessage
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.protobuf.validator_pb2 import Message
from sawtooth_validator.protobuf.client_pb2 import ClientBatchSubmitResponse


LOGGER = logging.getLogger(__name__)


def validate_block(block):
    # validate block signature
    header = BlockHeader()
    header.ParseFromString(block.header)
    valid = signing.verify(block.header,
                           block.header_signature,
                           header.signer_pubkey)

    # validate all batches in block. These are not all batches in the
    # batch_ids stored in the block header, only those sent with the block.
    total = len(block.batches)
    index = 0
    while valid and index < total:
        valid = validate_batch(block.batches[index])
        index += 1

    return valid


def validate_batch_list(batch_list):
    valid = False
    for batch in batch_list.batches:
        valid = validate_batch(batch)
        if valid is False:
            break
    return valid


def validate_batch(batch):
    # validate batch signature
    header = BatchHeader()
    header.ParseFromString(batch.header)
    valid = signing.verify(batch.header,
                           batch.header_signature,
                           header.signer_pubkey)

    if not valid:
        LOGGER.debug("batch failed signature validation: %s",
                     batch.header_signature)

    # validate all transactions in batch
    total = len(batch.transactions)
    index = 0
    while valid and index < total:
        txn = batch.transactions[index]
        valid = validate_transaction(txn)
        if valid:
            txn_header = TransactionHeader()
            txn_header.ParseFromString(txn.header)
            if txn_header.batcher_pubkey != header.signer_pubkey:
                LOGGER.debug("txn batcher pubkey does not match signer"
                             "pubkey for batch: %s txn: %s",
                             batch.header_signature,
                             txn.header_signature)
                valid = False
        index += 1

    return valid


def validate_transaction(txn):
    # validate transactions signature
    header = TransactionHeader()
    header.ParseFromString(txn.header)
    valid = signing.verify(txn.header,
                           txn.header_signature,
                           header.signer_pubkey)

    if not valid:
        LOGGER.debug("transaction signature invalid for txn: %s",
                     txn.header_signature)
    return valid


class GossipMessageSignatureVerifier(Handler):

    def handle(self, identity, message_content):

        gossip_message = GossipMessage()
        gossip_message.ParseFromString(message_content)
        if gossip_message.content_type == "BLOCK":
            block = Block()
            block.ParseFromString(gossip_message.content)
            status = validate_block(block)
            if status is True:
                LOGGER.debug("block passes signature verification %s",
                             block.header_signature)
                return HandlerResult(status=HandlerStatus.PASS)

            LOGGER.debug("block signature is invalid: %s",
                         block.header_signature)
            return HandlerResult(status=HandlerStatus.DROP)
        elif gossip_message.content_type == "BATCH":
            batch = Batch()
            batch.ParseFromString(gossip_message.content)
            status = validate_batch(batch)
            if status is True:
                LOGGER.debug("batch passes signature verification %s",
                             batch.header_signature)
                return HandlerResult(status=HandlerStatus.PASS)
            LOGGER.debug("batch signature is invalid: %s",
                         batch.header_signature)
            return HandlerResult(status=HandlerStatus.DROP)


class BatchListSignatureVerifier(Handler):

    def handle(self, identity, message_content):
        try:
            batch_list = BatchList()
            batch_list.ParseFromString(message_content)
            status = validate_batch_list(batch_list)
        except DecodeError:
            return self._response(ClientBatchSubmitResponse.INTERNAL_ERROR)

        if status is not True:
            return self._response(ClientBatchSubmitResponse.INVALID_BATCH)

        return HandlerResult(status=HandlerStatus.PASS)

    def _response(self, out_status):
        return HandlerResult(
            status=HandlerStatus.RETURN,
            message_out=ClientBatchSubmitResponse(status=out_status),
            message_type=Message.CLIENT_BATCH_SUBMIT_RESPONSE)
