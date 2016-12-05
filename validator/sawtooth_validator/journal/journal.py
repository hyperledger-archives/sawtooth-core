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

from concurrent.futures import ThreadPoolExecutor
import logging
import queue
from threading import RLock
from threading import Thread
import time

from sawtooth_validator.server.block import BlockState, Block, \
    BlockStatus, NullIdentifier
from sawtooth_validator.scheduler.serial import SerialScheduler

from sawtooth_validator.server.messages import BlockRequestMessage, \
    BlockMessage


LOGGER = logging.getLogger(__name__)


class BlockPublisher(object):
    """
    Responsible for generating new blocks and publishing them when the
    Consensus deems it appropriate.
    """
    def __init__(self,
                 consensus,
                 transaction_executor,
                 send_message):
        self._lock = RLock()
        self._candidate_block = None  # the next block in potentia
        self._consensus = consensus  # the consensus object.
        self._transaction_executor = transaction_executor
        self._pending_batches = []  # batches we are waiting for
        self._validated_batches = []
        self._send_message = send_message
        self._scheduler = None
        self._chain_head = None

    def _build_block(self, chain_head):
        """ Build a candidate block
        """
        block = Block(chain_head)
        self._consensus.initialize_block(block)

        # create a new scheduler
        # TBD move factory in to executor for easier mocking --
        # Yes I want to make fun of it.
        self._scheduler = self._transaction_executor.create_scheduler()
        self._transaction_executor.execute(self._scheduler)
        return block

    def _sign_block(self, block):
        """ The block should be complete and the final
        signature from the publishing validator(this validator) needs to
        be added.
        """
        block.signature = "X"
        return block

    def on_batch_received(self, batch):
        """
        A new batch is received, send it for validation
        :param block:
        :return:
        """
        with self._lock:
            LOGGER.info("on_batch_received: %s",
                        batch)
            self._pending_batches.append(batch)
            if self._scheduler:
                self._scheduler.add_batch(batch)

    def on_chain_updated(self, chain_head,
                         committed_batches=None,
                         uncommitted_batches=None):
        """
        The existing chain has been updated, the current head block has
        changed.

        chain_head: the new head of block_chain
        committed_batches:
        uncommitted_batches: the list of transactions if any that are now
            de-committed due to the switch in forks.

        :return:
        """
        with self._lock:
            LOGGER.info("Chain updated, new head: %s",
                        chain_head)
            self._chain_head = chain_head
            if self._candidate_block is not None and \
                    chain_head is not None and \
                    chain_head.id == self._candidate_block.previous_block_id:
                # nothing to do. We are building of the current head.
                # This can happen after we publish a block and speculatively
                # create a new block.
                return
            else:
                # TBD -- we need to rebuild the pending transaction queue --
                # which could be an unknown set depending if we switched forks

                # new head of the chain.
                self._candidate_block = self._build_block(chain_head)

    def _finalize_block(self, block):
        if self._scheduler:
            self._scheduler.finalize()
            self._scheduler.complete()

        # TBD -- Read valid batches from self._scheduler
        self._validated_batches = self._pending_batches
        self._pending_batches = []

        block.batches = self._validated_batches
        self._validated_batches = []

        self._consensus.finalize_block(block)
        self._sign_block(block)
        return block

    def on_check_publish_block(self, force=False):
        """
            Ask the consensus module if it is time to claim the candidate block
            if it is then, claim it and tell the world about it.
        :return:
        """
        with self._lock:
            if self._candidate_block is None and len(self._pending_batches) \
                    != 0:
                self._candidate_block = self._build_block(self._chain_head)

            if self._candidate_block and \
                    (force or len(self._pending_batches) != 0) and \
                    self._consensus.check_publish_block(self._candidate_block):
                candidate = self._candidate_block
                self._candidate_block = None
                self._finalize_block(candidate)

                self._send_message(BlockMessage(candidate))

                LOGGER.info("Claimed Block: %s", candidate.id)

                # create a new block based on this one -- opportunistically
                # assume the published block is the valid block.
                self.on_chain_updated(candidate)

    def generate_genesis_block(self):
        genesis_block = self._build_block(None)
        # Small hack here not asking consensus if it is happy.
        return self._finalize_block(genesis_block)


class BlockValidator(object):
    """
    Responsible for validating a block, handles both chain extensions and fork
    will determine if the new block should be the head of the chain and

    """
    def __init__(self, consensus,
                 block_store,
                 new_block,
                 chain_head,
                 request_block_cb,
                 done_cb):
        self._consensus = consensus
        self._block_store = block_store
        self._new_block = new_block
        self._chain_head = chain_head
        self._request_block_cb = request_block_cb
        self._done_cb = done_cb

        self._commit_new_block = False

    def commit_new_block(self):
        return self._commit_new_block

    @property
    def new_block(self):
        return self._new_block

    @property
    def chain_head(self):
        return self._chain_head

    def _validate_block(self, block):
        LOGGER.info(block)
        if block.status == BlockStatus.Valid:
            return True
        elif block.status == BlockStatus.Invalid:
            return False
        else:
            valid = True
            # verify signature
            # valid = block.signature == 'X'

            if valid:
                # TBD validate transactions
                pass

            if valid:
                valid = self._consensus.verify_block(block)

            # Update the block store
            block.weight = self._consensus.compute_block_weight(block)
            block.status = BlockStatus.Valid if valid else BlockStatus.Invalid
            self._block_store[block.id] = block
            return valid

    def run(self):
        LOGGER.info("Starting block validation of : %s",
                    self._new_block.id)
        current_chain = []  # ordered list of the current chain
        new_chain = []

        newb = self._new_block
        curb = self._chain_head

        # 1) find the common ancestor of this block in the current chain
        # Walk back until we have both chains at the same length
        while newb.block_num > curb.block_num\
                and newb.previous_block_id != NullIdentifier:
            new_chain.append(newb)
            try:
                newb = self._block_store[newb.previous_block_id]
            except KeyError as e:
                # required block is missing
                self._request_block_cb(newb.previous_block_id, self)
                return

        while curb.block_num > newb.block_num \
                and newb.previous_block_id != NullIdentifier:
            current_chain.append(curb)
            curb = self._block_store[curb.previous_block_id]

        # 2) now we have both chain at the same block number
        # continue walking back until we find a common block.
        while curb.id != newb.id:
            if curb.previous_block_id == NullIdentifier or \
                    newb.previous_block_id == NullIdentifier:
                # We are at a genesis block and the blocks are not the
                # same
                LOGGER.info("Block rejected due to wrong genesis : %s %s",
                            curb.id, newb.id)

                self._done_cb(self)
                return
            new_chain.append(newb)
            newb = self._block_store[newb.previous_block_id]

            current_chain.append(curb)
            curb = self._block_store[curb.previous_block_id]

        # 3) We now have the root of the fork.
        # determine the validity of the new fork
        for block in reversed(new_chain):
            if not self._validate_block(block):
                LOGGER.info("Block validation failed: %s",
                            block)
                self._done_cb(self)
                return

        # 4) new chain is valid... should we switch to it?
        LOGGER.info("Finished block validation of XXXX: %s, %s",
                    new_chain[0].weight, self._chain_head.weight)
        self._commit_new_block = new_chain[0].weight > self._chain_head.weight

        # Tell the journal we are done
        self._done_cb(self)
        LOGGER.info("Finished block validation of : %s",
                    self._new_block.id)


class ChainController(object):
    """
    To evaluating new blocks to determine if they should extend or replace
    the current chain. If they are valid extend the chain.
    """
    def __init__(self,
                 consensus,
                 block_store,
                 send_message,
                 executor,
                 transaction_executor,
                 on_chain_updated):
        self._lock = RLock()
        self._consensus = consensus
        self._block_store = block_store
        self._send_message = send_message
        self._executor = executor
        self._transaction_executor = transaction_executor
        self._notifiy_on_chain_updated = on_chain_updated

        self._blocks_requested = {}  # a set of blocks that were requested.
        self._blocks_processing = {}  # a set of blocks that are
        # currently being processed.
        self._blocks_pending = {}  # set of blocks that the previous block
        # is being processed. Once that completes this block will be
        # scheduled for validation.

        try:
            self._chain_head = \
                self._block_store[self._block_store["chain_head_id"]]

            LOGGER.info("Chain controller initialized with chain head: %s",
                        self._chain_head)
        except Exception as e:
            LOGGER.error("Invalid block store. Head of the block chain cannot "
                         "be determined: %s", e)
            raise

        self._notifiy_on_chain_updated(self._chain_head)

    @property
    def chain_head(self):
        return self._chain_head

    def _verify_block(self, block_state):
        validator = BlockValidator(
            consensus=self._consensus,
            new_block=block_state,
            chain_head=self._chain_head,
            block_store=self._block_store,
            request_block_cb=self._request_block,
            done_cb=self.on_block_validated)
        self._blocks_processing[block_state.id] = validator
        self._executor.submit(validator.run)

    def _request_block(self, block_id, validator):
        # TBD add request time and time out
        self._blocks_requested[block_id] = validator
        self._send_message(BlockRequestMessage(block_id))

    def on_block_validated(self, validator):
        """
        Message back from the block validator
        :param block:
        :return:
        """
        with self._lock:
            LOGGER.info("on_block_validated : %s",
                        validator.new_block.id)
            # remove from the processing list
            del self._blocks_processing[validator.new_block.id]

            # if the head has changed, since we started the work.
            if validator.chain_head != self._chain_head:
                # chain has advanced since work started.
                # the block validation work we have done is saved.
                self._verify_block(validator.new_block)
            elif validator.commit_new_block():
                self._chain_head = validator.new_block
                self._block_store["chain_head_id"] = self._chain_head.id
                LOGGER.info("Chain head updated to: %s",
                            self._chain_head.id)

                # tell everyone else the chain is updated
                self._notifiy_on_chain_updated(self._chain_head)

                pending_blocks = \
                    self._blocks_pending.get(
                        self._chain_head.previous_block_id, [])
                for pending_block in pending_blocks:
                    self._verify_block(pending_block)

    def on_block_received(self, block):
        with self._lock:
            LOGGER.info("on_block_received : %s",
                        block)
            if block.id in self._block_store:
                # do we already have this block
                return

            block_state = BlockState(block)
            self._block_store[block.id] = block_state

            if block.id in self._blocks_requested:
                # is it a requested block
                # route block to the validator that requested
                validator = self._blocks_requested.pop(block.id)
                if validator.chain_head.id != self._chain_head.id:
                    # the head of the chain has changed start over
                    self._verify_block(validator.new_block)
                else:
                    self._executor.submit(validator.run)
            elif block.previous_block_id in self._blocks_processing:
                # if the previous block is being processed...put it in a wait
                # queue
                pending_blocks = \
                    self._blocks_pending.get(block.previous_block_id, [])
                pending_blocks.push(block_state)
            else:
                # schedule this block for validation.
                self._verify_block(block_state)


class Journal(object):
    """
    Manages the block chain, This responsibility boils down
    1) to evaluating new blocks to determine if they should extend or replace
    the current chain. Handled by the ChainController/
    2) Claiming new blocks, handled by the BlockPublisher

    This object provides the threading and event queue for the processors.

    """

    class _ChainThread(Thread):
        def __init__(self, chain_controller, block_queue):
            Thread.__init__(self)
            self._block_publisher = chain_controller
            self._block_queue = block_queue
            self._exit = False

        def run(self):
            while (True):
                try:
                    block = self._block_queue.get(timeout=0.1)
                    self._block_publisher.on_block_received(block)
                except queue.Empty:
                    time.sleep(0.1)
                if self._exit:
                    return

        def stop(self):
            self._exit = True

    class _PublisherThread(Thread):
        def __init__(self, block_publisher, batch_queue):
            Thread.__init__(self)
            self._block_publisher = block_publisher
            self._batch_queue = batch_queue
            self._exit = False

        def run(self):
            while(True):
                try:
                    batch = self._batch_queue.get(timeout=0.1)
                    self._block_publisher.on_batch_received(batch)
                except queue.Empty:
                    time.sleep(0.1)

                self._block_publisher.on_check_publish_block()
                if self._exit:
                    return

        def stop(self):
            self._exit = True

    def __init__(self,
                 consensus,
                 block_store,
                 send_message,
                 transaction_executor):
        self._consensus = consensus
        self._block_store = block_store
        self._send_message = send_message

        self._block_publisher = BlockPublisher(
            consensus=consensus.BlockPublisher(),
            transaction_executor=transaction_executor,
            send_message=send_message
        )
        self._batch_queue = queue.Queue()
        self._publisher_thread = self._PublisherThread(self._block_publisher,
                                                       self._batch_queue)
        # HACK until genesis tool is working
        if "chain_head_id" not in self._block_store:
            genesis_block = BlockState(
                self._block_publisher.generate_genesis_block())
            genesis_block.status = BlockStatus.Valid

            self._block_store[genesis_block.block.id] = genesis_block
            self._block_store["chain_head_id"] = genesis_block.id
            LOGGER.info("Journal created genesis block: %s",
                        genesis_block.id)

        self._chain_controller = ChainController(
            consensus=consensus.BlockVerifier(),
            block_store=block_store,
            send_message=send_message,
            executor=ThreadPoolExecutor(1),
            transaction_executor=transaction_executor,
            on_chain_updated=self._block_publisher.on_chain_updated
        )
        self._block_queue = queue.Queue()
        self._chain_thread = self._ChainThread(self._chain_controller,
                                               self._block_queue)

    def start(self):
        # TBD do load activities....
        # TBD transfer activities - request chain-head from
        # network
        self._publisher_thread.start()
        self._chain_thread.start()

    def stop(self):
        # time to murder the child threads. First ask politely for
        # suicide
        self._publisher_thread.stop()
        self._chain_thread.stop()

    def on_block_received(self, block):
        self._block_queue.put(block)

    def on_batch_received(self, batch):
        self._batch_queue.put(batch)

    def on_block_request(self, block_id):
        if block_id in self._block_store:
            msg = BlockMessage(self._block_store[block_id].block)
            self._send_message(msg)
