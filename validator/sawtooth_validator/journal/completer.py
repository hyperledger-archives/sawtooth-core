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

from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.timed_cache import TimedCache
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.batch_pb2 import BatchList
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf import client_pb2
from sawtooth_validator.protobuf import network_pb2
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus

LOGGER = logging.getLogger(__name__)


class Completer(object):
    """
    The Completer is responsible for making sure blocks are formally
    complete before they are delivered to the chain controller. A formally
    complete block is a block that predecessor is in the block cache and all
    the batches are present in the batch list and in the order specified by the
    block header. If the predecessor or a batch is missing, a request message
    is sent sent out over the gossip network.
    """
    def __init__(self, block_store, gossip):
        """
        :param block_store (dictionary) The block store shared with the journal
        :param gossip (gossip.Gossip) Broadcasts block and batch request to
                peers
        """
        self.gossip = gossip
        self.batch_cache = TimedCache()
        self.block_cache = BlockCache(block_store)
        # avoid throwing away the genesis block
        self.block_cache[NULL_BLOCK_IDENTIFIER] = None
        self._on_block_received = None
        self._on_batch_received = None

    def _complete_block(self, block):
        """ Check the block to see if it is complete and if it can be passed to
            the journal. If the block's predecessor is not in the block_cache
            the predecessor is requested and the current block is dropped.
            False is returned. If the block.batches and block.header.batch_ids
            are not the same length, False is returned. The block's batch list
            needs to be in the same order as the block.header.batch_ids list.
            If any batches are missing from the block and we do not have the
            batches in the batch_cache, they are requested. The block is then
            dropped and False is returned. If the block has all of its expected
            batches it is added to the block_cache and True is returned.
        """
        valid = True
        if block.previous_block_id not in self.block_cache:
            LOGGER.debug("Block discarded(Missing predecessor): %s",
                         block.header_signature[:8])
            LOGGER.debug("Request missing predecessor: %s",
                         block.previous_block_id)
            self.gossip.broadcast_block_request(block.previous_block_id)
            return False

        if len(block.batches) != len(block.header.batch_ids):
            LOGGER.debug("Block discarded(Missing batches): %s",
                         block.header_signature[:8])
            valid = False

        for i in range(len(block.header.batch_ids)):
            if block.batches[i].header_signature != block.header.batch_ids[i]:
                LOGGER.debug("Block discarded(Missing batch): %s",
                             block.header_signature[:8])
                if block.header.batch_ids[i] not in self.batch_cache:
                    LOGGER.debug("Request missing batch: %s",
                                 block.header.batch_ids[i])
                    self.gossip.broadcast_batch_by_batch_id_request(
                        block.header.batch_ids[i])
                valid = False

        return valid

    def set_on_block_received(self, on_block_received_func):
        self._on_block_received = on_block_received_func

    def set_on_batch_received(self, on_batch_received_func):
        self._on_batch_received = on_batch_received_func

    def add_block(self, block):
        blkw = BlockWrapper(block)
        if self._complete_block(blkw):
            self.block_cache[block.header_signature] = blkw
            self._on_block_received(blkw)

    def add_batch(self, batch):
        self.batch_cache[batch.header_signature] = batch
        self._on_batch_received(batch)

    def get_block(self, block_id):
        if block_id in self.block_cache:
            return self.block_cache[block_id]
        return None

    def get_batch(self, batch_id=None, ):
        if batch_id in self.batch_cache:
            return self.batch_cache[batch_id]
        return None

    def get_batch_by_transaction(self, transaction_id):
        # need a transaction to batch store
        return None


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
