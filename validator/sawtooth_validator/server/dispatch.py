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
import queue
import logging

from threading import Thread
from google.protobuf.message import DecodeError

from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader, Batch
from sawtooth_validator.protobuf.block_pb2 import BlockHeader, Block
LOGGER = logging.getLogger(__name__)


class Dispatcher(Thread):
    def __init__(self):
        super(Dispatcher, self).__init__()
        self.on_batch_received = None
        self.on_block_received = None
        self.on_block_requested = None
        self.incoming_msg_queue = None
        self.condition = None
        self._exit = False

    def set_incoming_msg_queue(self, msg_queue):
        self.incoming_msg_queue = msg_queue

    def set_condition(self, condition):
        self.condition = condition

    def stop(self):
        self._exit = True

    def run(self):
        if self.incoming_msg_queue is None or self.condition is None:
            LOGGER.warn("Dispatcher can not be used if incoming_msg_queue or"
                        "condition is not set.")
            return

        while True:
            if self._exit:
                return

            try:
                request = self.incoming_msg_queue.get(block=False)
                if request.content_type == "Block":
                    try:
                        block = Block()
                        block.ParseFromString(request.content)
                        self.on_block_received(block)
                    except DecodeError as e:
                        # what to do with a bad msg
                        LOGGER.warn("Problem decoding GossipMessage for Block,"
                                    "%s", e)

                elif request.content_type == "Batch":
                    try:
                        batch = Batch()
                        batch.ParseFromString(request.content)
                        self.on_batch_received(batch)

                    except DecodeError as e:
                        LOGGER.warn("Problem decoding GossipMessage for Batch,"
                                    " %s", e)

                elif request.content_type == "BlockRequest":
                    block_id = str(request.content, "utf-8")
                    self.on_block_requested(block_id)

                elif request.content_type == "Test":
                    LOGGER.debug("Dispatch Handle Test")

            except queue.Empty:
                with self.condition:
                    self.condition.wait()
