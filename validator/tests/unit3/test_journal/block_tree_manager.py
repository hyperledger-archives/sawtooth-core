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

from concurrent.futures import Executor
import pprint
import random
import string

from sawtooth_validator.journal.journal import \
    BlockPublisher
from sawtooth_validator.journal.consensus.test_mode.test_mode_consensus \
    import \
    BlockPublisher as TestModePublisher

from sawtooth_validator.protobuf.block_pb2 import Block, BlockHeader
from sawtooth_validator.protobuf.batch_pb2 import Batch

from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import BlockState
from sawtooth_validator.journal.block_wrapper import BlockStatus

from test_journal.mock import MockTransactionExecutor

pp = pprint.PrettyPrinter(indent=4)


def _generate_id(length=16):
    return ''.join(
        random.SystemRandom().choice(string.ascii_uppercase + string.digits)
        for _ in range(length))


class BlockTreeManager(object):
    def block_def(self,
                  add_to_store=False,
                  batch_count=0,
                  status=BlockStatus.Unknown,
                  invalid_consensus=False,
                  invalid_batch=False,
                  invalid_signature=False,
                  weight=1
                  ):
        return {
            "add_to_store": add_to_store,
            "batch_count": batch_count,
            "status": status,
            "invalid_consensus": invalid_consensus,
            "invalid_batch": invalid_batch,
            "invalid_signature": invalid_signature,
            "weight": weight
        }

    def __init__(self):
        self.block_store = {}
        self._new_block = None
        self.block_publisher = BlockPublisher(
            consensus=TestModePublisher(),
            transaction_executor=MockTransactionExecutor(),
            send_message=self._send_message,
            squash_handler=None)

        block = self.generate_block(add_to_store=True,
                                    status=BlockStatus.Valid)
        self.set_chain_head(block)

    def _send_message(self, block):
        self._new_block = block

    def _get_block_id(self, block):
        if (block is None):
            return None
        elif isinstance(block, Block) or isinstance(block, BlockState) or \
                isinstance(block, BlockWrapper):
            return block.header_signature
        elif isinstance(block, basestring):
            return block
        else:
            return str(block)

    def _get_block(self, block):
        if (block is None):
            return None
        elif isinstance(block, Block):
            return block
        elif isinstance(block, BlockWrapper):
            return block
        elif isinstance(block, BlockState):
            return block.block
        elif isinstance(block, str):
            return self.block_store[block]
        else:  # WTF try something crazy
            return self.block_store[str(block)]

    def set_chain_head(self, block):
        self.block_store["chain_head_id"] = self._get_block_id(block)

    @property
    def chain_head(self):
        return self.block_store[self.block_store["chain_head_id"]]

    def generate_block(self, previous_block=None,
                       add_to_store=False,
                       batch_count=0,
                       status=BlockStatus.Unknown,
                       invalid_consensus=False,
                       invalid_batch=False,
                       invalid_signature=False,
                       weight=1):

        previous = self._get_block(previous_block)
        if previous is None:
            previous = BlockWrapper(BlockHeader(
                block_num=0,
                previous_block_id="0000000000000000",
            ))
            previous.set_signature(_generate_id())
            previous_block_state = BlockState(
                block_wrapper=previous,
                weight=0,
                status=BlockStatus.Valid)
            self.block_store[previous.header_signature] = previous_block_state
            self.block_publisher.on_chain_updated(previous)

        while self._new_block is None:
            self.block_publisher.on_batch_received(Batch())
            self.block_publisher.on_check_publish_block(True)

        block = self._new_block
        self._new_block = None

        header = BlockHeader()
        header.ParseFromString(block.header)
        block = BlockWrapper(header, block)

        if invalid_signature:
            block.set_signature("BAD")

        if add_to_store:
            block_state = BlockState(block_wrapper=block, weight=0)
            block_state.status = status
            self.block_store[block.header_signature] = block_state

        return block

    def generate_chain(self, root_block,
                       blocks):
        # block options
        # valid/invalid how
        # add to store
        out = []
        if not isinstance(blocks, list):
            blocks = self.generate_chain_definition(int(blocks))

        previous = self._get_block(root_block)
        for b in blocks:
            new_block = self.generate_block(previous_block=previous,
                                            **b)
            out.append(new_block)
            previous = new_block
        return out

    def generate_chain_definition(self, count):
        out = []
        for _ in range(0, count):
            out.append(self.block_def())
        return out

    def __str__(self):
        return str(self.block_store)

    def __repr__(self):
        return repr(self.block_store)


class GossipMock(object):
    def __init__(self):
        self.messages = []

    def send_message(self, message):
        self.messages.append(message)

    def clear(self):
        self.messages = []


class SynchronousProcessor(Executor):
    def __init__(self):
        self._work_queue = []

    def submit(self, job):
        self._work_queue.append(job)

    def process_next(self):
        job = self._work_queue.pop()
        job.run()

    def process_all(self):
        while len(self._work_queue):
            self.process_next()
