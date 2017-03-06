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
import time
from threading import RLock

from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.timed_cache import TimedCache
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.batch_pb2 import BatchList
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
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
    complete block is a block whose predecessor is in the block cache and all
    the batches are present in the batch list and in the order specified by the
    block header. If the predecessor or a batch is missing, a request message
    is sent sent out over the gossip network. It also checks that all batches
    have their dependencies satisifed, otherwise it will request the batch that
    has the missing transaction.
    """
    def __init__(self, block_store, gossip, cache_purge_frequency=30):
        """
        :param block_store (dictionary) The block store shared with the journal
        :param gossip (gossip.Gossip) Broadcasts block and batch request to
                peers
        :param cache_purge_frequency (int) The time between purging the
                TimedCaches.
        """
        self.gossip = gossip
        self.batch_cache = TimedCache(cache_purge_frequency)
        self.block_cache = BlockCache(block_store, cache_purge_frequency)
        # avoid throwing away the genesis block
        self.block_cache[NULL_BLOCK_IDENTIFIER] = None
        self._seen_txns = TimedCache(cache_purge_frequency)
        self._incomplete_batches = TimedCache(cache_purge_frequency)
        self._incomplete_blocks = TimedCache(cache_purge_frequency)
        self._on_block_received = None
        self._on_batch_received = None
        self.lock = RLock()
        self._cache_purge_frequency = cache_purge_frequency
        self._purge_time = time.time() + self._cache_purge_frequency

    def _complete_block(self, block):
        """ Check the block to see if it is complete and if it can be passed to
            the journal. If the block's predecessor is not in the block_cache
            the predecessor is requested and the current block is added to the
            the incomplete_block cache. If the block.batches and
            block.header.batch_ids are not the same length, the batch_id list
            is checked against the batch_cache to see if the batch_list can be
            built. If any batches are missing from the block and we do not have
            the batches in the batch_cache, they are requested. The block is
            then added to the incomplete_block cache. If we can complete the
            block, a new batch list is created in the correct order and added
            to the block. The block is now considered complete and is returned.
            If block.batches and block.header.batch_ids are the same length,
            the block's batch list needs to be in the same order as the
            block.header.batch_ids list. If the block has all of its expected
            batches but are not in the correct order, the batch list is rebuilt
            and added to the block. Once a block has the correct batch list it
            is added to the block_cache and is returned.

        """

        if block.header_signature in self.block_cache:
            LOGGER.debug("Drop duplicate block: %s", block)
            return None

        if block.previous_block_id not in self.block_cache:
            LOGGER.debug("Request missing predecessor: %s",
                         block.previous_block_id)
            if block.previous_block_id not in self._incomplete_blocks:
                self._incomplete_blocks[block.previous_block_id] = [block]
            elif block not in self._incomplete_blocks[block.previous_block_id]:
                self._incomplete_blocks[block.previous_block_id] += [block]

            self.gossip.broadcast_block_request(block.previous_block_id)
            return None

        # Check for same number of batch_ids and batches
        # If different starting building batch list, Otherwise there is a batch
        # that does not belong, block should be dropped.
        if len(block.batches) > len(block.header.batch_ids):
            LOGGER.debug("Block has extra batches. Dropping %s", block)
            return None

        # used to supplement batch_cache, contains batches already in block
        temp_batches = {}
        for batch in block.batches:
            temp_batches[batch.header_signature] = batch

        # The block is missing batches. Check to see if we can complete it.
        if len(block.batches) != len(block.header.batch_ids):
            building = True
            for batch_id in block.header.batch_ids:
                if batch_id not in self.batch_cache and \
                        batch_id not in temp_batches:
                    # Request all missing batches
                    self.gossip.broadcast_batch_by_batch_id_request(batch_id)
                    if batch_id not in self._incomplete_blocks:
                        self._incomplete_blocks[batch_id] = [block]
                    elif block not in self._incomplete_blocks[batch_id]:
                        self._incomplete_blocks[batch_id] += [block]
                    building = False

            if not building:
                # The block cannot be completed.
                return None

            batches = self._finalize_batch_list(block, temp_batches)
            del block.batches[:]
            # reset batches with full list batches
            block.batches.extend(batches)
            return block

        else:
            batch_id_list = [x.header_signature for x in block.batches]
            # Check to see if batchs are in the correct order.
            if batch_id_list == list(block.header.batch_ids):
                return block
            # Check to see if the block has all batch_ids and they can be put
            # in the correct order
            elif sorted(batch_id_list) == sorted(list(block.header.batch_ids)):
                batches = self._finalize_batch_list(block, temp_batches)
                # Clear batches from block
                del block.batches[:]
                # reset batches with full list batches
                if batches is not None:
                    block.batches.extend(batches)
                else:
                    return None

                return block
            else:
                LOGGER.debug("Block.header.batch_ids does not match set of "
                             "batches in block.batches Dropping %s", block)
                return None

    def _finalize_batch_list(self, block, temp_batches):
        batches = []
        for batch_id in block.header.batch_ids:
            if batch_id in self.batch_cache:
                batches.append(self.batch_cache[batch_id])
            elif batch_id in temp_batches:
                batches.append(temp_batches[batch_id])
            else:
                return None

        return batches

    def _complete_batch(self, batch):
        valid = True
        dependencies = []
        for txn in batch.transactions:
            txn_header = TransactionHeader()
            txn_header.ParseFromString(txn.header)
            for dependency in txn_header.dependencies:
                # Check to see if the dependency has been seen or is in the
                # current chain (block_store)
                if dependency not in self._seen_txns and not \
                        self.block_cache.block_store.has_transaction(
                        dependency):
                    LOGGER.debug("Transaction %s in batch %s has "
                                 "unsatisfied dependency: %s",
                                 txn.header_signature,
                                 batch.header_signature,
                                 dependency)

                    dependencies.append(dependency)
                    if dependency not in self._incomplete_batches:
                        self._incomplete_batches[dependency] = [batch]
                    elif batch not in self._incomplete_batches[dependency]:
                        self._incomplete_batches[dependency] += [batch]
                    valid = False
        if not valid:
            self.gossip.broadcast_batch_by_transaction_id_request(
                dependencies)

        return valid

    def _add_seen_txns(self, batch):
        for txn in batch.transactions:
            if txn.header_signature in self._seen_txns and \
                    self._seen_txns[txn.header_signature] == \
                    batch.header_signature:
                break
            self._seen_txns[txn.header_signature] = batch.header_signature

    def _process_incomplete_batches(self, key):
        # Keys are transaction_id
        if key in self._incomplete_batches:
            batches = self._incomplete_batches[key]
            for batch in batches:
                self.add_batch(batch)
            del self._incomplete_batches[key]

    def _process_incomplete_blocks(self, key):
        # Keys are either a block_id or batch_id
        if key in self._incomplete_blocks:
            inc_blocks = self._incomplete_blocks[key]
            for inc_block in inc_blocks:
                if self._complete_block(inc_block):
                    self.block_cache[inc_block.header_signature] = \
                        inc_block
                    self._on_block_received(inc_block)
            del self._incomplete_blocks[key]

    def _purge_caches(self):
        if self._purge_time < time.time():
            LOGGER.debug("Purges caches of expired entries.")
            self._seen_txns.purge_expired()
            self._incomplete_batches.purge_expired()
            self._incomplete_blocks.purge_expired()
            self.batch_cache.purge_expired()
            self.block_cache.purge_expired()
            self._purge_time = time.time() + self._cache_purge_frequency

    def set_on_block_received(self, on_block_received_func):
        self._on_block_received = on_block_received_func

    def set_on_batch_received(self, on_batch_received_func):
        self._on_batch_received = on_batch_received_func

    def add_block(self, block):
        with self.lock:
            blkw = BlockWrapper(block)
            block = self._complete_block(blkw)
            if block is not None:
                self.block_cache[block.header_signature] = blkw
                self._on_block_received(blkw)
                self._process_incomplete_blocks(block.header_signature)
                self._purge_caches()

    def add_batch(self, batch):
        with self.lock:
            if batch.header_signature in self.batch_cache:
                return
            if self._complete_batch(batch):
                self.batch_cache[batch.header_signature] = batch
                self._add_seen_txns(batch)
                self._on_batch_received(batch)
                self._process_incomplete_blocks(batch.header_signature)
                # If there was a batch waiting on this transaction, process
                # that batch
                for txn in batch.transactions:
                    if txn.header_signature in self._incomplete_batches:
                        self._process_incomplete_batches(txn.header_signature)

    def get_block(self, block_id):
        with self.lock:
            if block_id in self.block_cache:
                return self.block_cache[block_id]
            return None

    def get_batch(self, batch_id):
        with self.lock:
            if batch_id in self.batch_cache:
                return self.batch_cache[batch_id]

            else:
                block_store = self.block_cache.block_store
                try:
                    return block_store.get_batch(batch_id)
                except ValueError:
                    return None

    def get_batch_by_transaction(self, transaction_id):
        with self.lock:
            if transaction_id in self._seen_txns:
                batch_id = self._seen_txns[transaction_id]
                return self.get_batch(batch_id)

            else:
                block_store = self.block_cache.block_store
                try:
                    return block_store.get_batch_by_transaction(transaction_id)
                except ValueError:
                    return None


class CompleterBatchListBroadcastHandler(Handler):

    def __init__(self, completer, gossip):
        self._completer = completer
        self._gossip = gossip

    def handle(self, identity, connection, message_content):
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

    def handle(self, identity, connection, message_content):
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
