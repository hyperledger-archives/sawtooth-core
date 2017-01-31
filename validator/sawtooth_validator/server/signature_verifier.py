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

# pylint: disable=import-error,no-name-in-module
# needed for google.protobuf import
import queue
import logging

from threading import Thread
from google.protobuf.message import DecodeError

from sawtooth_signing import pbct_nativerecover as signing
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader, Batch
from sawtooth_validator.protobuf.block_pb2 import BlockHeader, Block
from sawtooth_validator.protobuf.network_pb2 import GossipMessage

LOGGER = logging.getLogger(__name__)


class SignatureVerifier(Thread):
    def __init__(self, incoming_msg_queue, dispatcher_msg_queue,
                 in_condition, dispatcher_condition, broadcast):
        super(SignatureVerifier, self).__init__()
        self._exit = False
        self.incoming_msg_queue = incoming_msg_queue
        self.dispatcher_msg_queue = dispatcher_msg_queue
        self.in_condition = in_condition
        self.dispatcher_condition = dispatcher_condition
        self.broadcast = broadcast

    def validate_block(self, block):
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
            valid = self.validate_batch(block.batches[index])
            index += 1

        return valid

    def validate_batch(self, batch):
        # validate batch signature
        header = BatchHeader()
        header.ParseFromString(batch.header)
        valid = signing.verify(batch.header,
                               batch.header_signature,
                               header.signer_pubkey)

        # validate all transactions in batch
        total = len(batch.transactions)
        index = 0
        while valid and index < total:
            txn = batch.transactions[index]
            valid = self.validate_transaction(txn)
            if valid:
                txn_header = TransactionHeader()
                txn_header.ParseFromString(txn.header)
                if txn_header.batcher_pubkey != header.signer_pubkey:
                    valid = False
            index += 1

        return valid

    def validate_transaction(self, txn):
        # validate transactions signature
        header = TransactionHeader()
        header.ParseFromString(txn.header)
        valid = signing.verify(txn.header,
                               txn.header_signature,
                               header.signer_pubkey)
        return valid

    def stop(self):
        self._exit = True

    def run(self):
        while True:
            if self._exit:
                return
            try:
                message = self.incoming_msg_queue.get(block=False)
                request = GossipMessage()
                request.ParseFromString(message.content)
                if request.content_type == "Block":
                    try:
                        block = Block()
                        block.ParseFromString(request.content)
                        status = self.validate_block(block)
                        if status:
                            LOGGER.debug("Pass block to dispatch %s",
                                         block.header_signature)
                            self.dispatcher_msg_queue.put_nowait(request)
                            self.broadcast(message)
                            with self.dispatcher_condition:
                                self.dispatcher_condition.notify_all()

                        else:
                            LOGGER.debug("Block signature is invalid: %s",
                                         block.header_signature)
                    except DecodeError as e:
                        # what to do with a bad msg
                        LOGGER.warning("Problem decoding GossipMessage for "
                                       "Block, %s", e)

                elif request.content_type == "Batch":
                    try:
                        batch = Batch()
                        batch.ParseFromString(request.content)
                        status = self.validate_batch(batch)
                        if status:
                            self.dispatcher_msg_queue.put_nowait(request)
                            self.broadcast(message)
                            with self.dispatcher_condition:
                                self.dispatcher_condition.notify_all()

                        else:
                            LOGGER.debug("Batch signature is invalid: %s",
                                         batch.header_signature)
                    except DecodeError as e:
                        LOGGER.warning("Problem decoding GossipMessage for "
                                       "Batch, %s", e)

                elif request.content_type == "BlockRequest":
                    self.dispatcher_msg_queue.put_notwait(request)
                    with self.dispatcher_condition:
                        self.dispatcher_condition.notify_all()

                elif request.content_type == "Test":
                    LOGGER.debug("Verifier Handle Test")
                    self.dispatcher_msg_queue.put_nowait(request)
                    with self.dispatcher_condition:
                        self.dispatcher_condition.notify_all()

            except queue.Empty:
                with self.in_condition:
                    self.in_condition.wait()
