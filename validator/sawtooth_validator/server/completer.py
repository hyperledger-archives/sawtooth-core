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
import queue
import logging
from threading import Thread
from sawtooth_validator.protobuf.block_pb2 import BlockHeader

LOGGER = logging.getLogger(__name__)


class Completer(Thread):
    def __init__(self, on_block_complete, condition, block_queue):
        super(Completer, self).__init__()
        self.on_block_complete = on_block_complete
        self._exit = False
        self.condition = condition
        self.block_queue = block_queue
        # temp batch cache
        self.batch_store = {}
        self.block_store = ["genesis"]

    def check_block(self, block, block_header):
        # currently only accepting finalized blocks
        # in the future if the blocks will be built

        if block_header.previous_block_id not in self.block_store:
            return False
        if len(block.batches) != len(block_header.batch_ids):
            return False

        for i in range(len(block.batches)):
            if block.batches[i].header_signature != block_header.batch_ids[i]:
                return False

        self.block_store.append(block.header_signature)
        return True

    def add_batch(self, batch):
        self.batch_store[batch.header_signature] = batch

    def stop(self):
        self._exit = True

    def run(self):
        while True:
            if self._exit:
                return
            try:
                block = self.block_queue.get(block=False)
                block_header = BlockHeader()
                block_header.ParseFromString(block.header)
                status = self.check_block(block, block_header)
                if status:
                    self.on_block_complete(block)
                    LOGGER.debug("Block passed to journal %s",
                                 block.header_signature)
                else:
                    self.block_queue.put(block)
            except queue.Empty:
                with self.condition:
                    self.condition.wait()
