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

from threading import Thread, Condition
from google.protobuf.message import DecodeError

from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.journal.completer import Completer
LOGGER = logging.getLogger(__name__)


class Dispatcher(Thread):
    def __init__(self):
        super(Dispatcher, self).__init__()
        self.on_batch_received = None
        self.on_block_received = None
        self.on_block_requested = None
        self.incoming_msg_queue = None
        self.completer_queue = queue.Queue()
        self.completer_conditon = Condition()
        self.condition = None
        self._exit = False
        self.completer = None

    def create_completer(self):
        self.completer = Completer(self.on_block_received,
                                   self.completer_conditon,
                                   self.completer_queue)
        self.completer.start()

    def set_incoming_msg_queue(self, msg_queue):
        self.incoming_msg_queue = msg_queue

    def set_condition(self, condition):
        self.condition = condition

    def set_on_block_received(self, on_block_received_func):
        self.on_block_received = on_block_received_func

    def set_on_batch_received(self, on_batch_received_func):
        self.on_batch_received = on_batch_received_func

    def set_on_block_requested(self, on_block_requested_func):
        self.on_block_requested = on_block_requested_func

    def stop(self):
        self._exit = True
        self.completer.stop()
        with self.completer_conditon:
            self.completer_conditon.notify_all()

    def run(self):
        if self.incoming_msg_queue is None or self.condition is None:
            LOGGER.warning("Dispatcher can not be used if incoming_msg_queue "
                           "or condition is not set.")
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
                        LOGGER.debug("Block given to Completer %s",
                                     block.header_signature)
                        self.completer_queue.put_nowait(block)
                        with self.completer_conditon:
                            self.completer_conditon.notify_all()
                    except DecodeError as e:
                        # what to do with a bad msg
                        LOGGER.warning("Problem decoding GossipMessage for "
                                       "Block, %s", e)

                elif request.content_type == "Batch":
                    try:
                        batch = Batch()
                        batch.ParseFromString(request.content)
                        self.completer.add_batch(batch)
                        self.on_batch_received(batch)

                    except DecodeError as e:
                        LOGGER.warning("Problem decoding GossipMessage for "
                                       "Batch, %s", e)

                elif request.content_type == "BlockRequest":
                    block_id = str(request.content, "utf-8")
                    self.on_block_requested(block_id)

                elif request.content_type == "Test":
                    LOGGER.debug("Dispatch Handle Test")

            except queue.Empty:
                with self.condition:
                    self.condition.wait()
