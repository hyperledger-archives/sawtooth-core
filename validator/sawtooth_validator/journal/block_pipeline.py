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

import abc
import logging
import queue

from sawtooth_validator.concurrent.thread import InstrumentedThread


LOGGER = logging.getLogger(__name__)


class Sender:
    def __init__(self, queue_to_wrap):
        self._queue = queue_to_wrap

    def send(self, item, timeout=None):
        if timeout is None:
            self._queue.put_nowait(item)
        else:
            self._queue.put(item, timeout=timeout)


class Receiver:
    def __init__(self, queue_to_wrap):
        self._queue = queue_to_wrap

    def receive(self, timeout=None):
        if timeout is None:
            return self._queue.get_nowait()
        return self._queue.get(timeout=timeout)


class SimpleReceiverThread(InstrumentedThread):
    """Pull items off of the queue and submit them to an executor."""
    def __init__(self, receiver, task, name='SimpleReceiverThread',
                 executor=None, exit_poll_interval=1):
        super().__init__(name=name)
        self._receiver = receiver
        self._task = task
        self._executor = executor
        self._exit_poll_interval = exit_poll_interval
        self._exit = False

    def run(self):
        while True:
            try:
                # Set timeout so we can check if the thread has been stopped
                item = self._receiver.receive(
                    timeout=self._exit_poll_interval)
                if self._executor is not None:
                    self._executor.submit(self._task, item)
                else:
                    self._task(item)

            except queue.Empty:
                pass

            if self._exit:
                return

    def stop(self):
        self._exit = True


class BlockPipelineStage:
    @abc.abstractmethod
    def start(self, receiver, sender):
        """Start processing blocks from receiver and putting them onto
        sender."""

    @abc.abstractmethod
    def stop(self):
        """Stop processing blocks and cleanup."""

    @abc.abstractmethod
    def has_block(self, block_id):
        """Return whether this stage has the given block."""


class PipelineNotRunning(Exception):
    def __init__(self):
        super().__init__(
            "Cannot perform the requested operation as the pipeline is not "
            "running.")


class PipelineRunning(Exception):
    def __init__(self):
        super().__init__(
            "Cannot perform the requested operation as the pipeline is "
            "already running.")


class PipelineOutputEmpty(Exception):
    def __init__(self):
        super().__init__(
            "The pipeline has nothing ready in the output queue.")


class BlockPipeline:
    def __init__(self):
        self._incoming = None
        self._outgoing = None
        self._stages = []
        self._running = False

    def add_stage(self, stage):
        if self._running:
            raise PipelineRunning()
        self._stages.append(stage)

    def start(self):
        """Create queues and wire up the stages."""
        if self._running:
            raise PipelineRunning()

        receivers = []
        senders = []

        for stage in self._stages:
            inter = queue.Queue()
            receivers.append(Receiver(inter))
            senders.append(Sender(inter))

        last = queue.Queue()
        senders.append(Sender(last))

        for i, stage in enumerate(self._stages):
            stage.start(receivers[i], senders[i + 1])

        self._incoming = senders[0]
        self._outgoing = Receiver(last)
        self._running = True

    def stop(self):
        if not self._running:
            raise PipelineNotRunning()

        for stage in self._stages:
            stage.stop()
        self._running = False

    def has_block(self, block):
        if not self._running:
            raise PipelineNotRunning()

        return any(stage.has_block(block) for stage in self._stages)

    def submit(self, item):
        """Submit an item to be processed."""
        if not self._running:
            raise PipelineNotRunning()

        self._incoming.send(item)

    @property
    def receiver(self):
        return self._outgoing

    def poll(self, timeout=None):
        """Get the next finished item, if one is available.
        Raises:
            PipelineOutputEmpty: No items are ready.
        """
        if not self._running:
            raise PipelineNotRunning()

        try:
            return self._outgoing.receive()

        except queue.Empty:
            raise PipelineOutputEmpty()
