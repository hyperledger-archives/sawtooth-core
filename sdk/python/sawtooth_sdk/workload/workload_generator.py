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
import asyncio
import logging
import time

from threading import Lock
from collections import deque
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor

from sawtooth_sdk.client.future import FutureTimeoutError
from sawtooth_sdk.client.exceptions import ValidatorConnectionError
from sawtooth_sdk.client.exceptions import WorkloadConfigurationError
from sawtooth_sdk.protobuf.client_pb2 import ClientBatchStatusRequest
from sawtooth_sdk.protobuf.client_pb2 import ClientBatchStatusResponse
from sawtooth_sdk.protobuf.validator_pb2 import Message

PendingBatch = namedtuple('PendingBatch', ['id', 'stream'])

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


class WorkloadGenerator(object):
    """
    This is the object that manages the workload sent to the validators and
    keeps track of submitted and committed batches. To run, it must first have
    a Workload set, as this is where the batches are created.
    """
    def __init__(self, args):
        self._workload = None
        self._lock = Lock()
        # needs to be locked
        self._pending_batches = deque()
        self._validators = args.urls.split(",")
        self._number_of_outstanding_requests = 0
        self._submitted_batches_sample = 0
        self._committed_batches_sample = 0

        self._time_since_last_check = 0
        self._submitted_batch_samples = deque()
        self._committed_batch_samples = deque()

        self._rate = 1.0 / int(args.rate)
        self._display_frequency = args.display_frequency
        self.loop = asyncio.get_event_loop()
        self.thread_pool = ThreadPoolExecutor(10)
        asyncio.ensure_future(self._simulator_loop(), loop=self.loop)

    def set_workload(self, workload):
        self._workload = workload
        self._discover_validators()
        self._workload.on_will_start()

    def run(self):
        if self._workload is None:
            raise WorkloadConfigurationError()
        self._time_since_last_check = time.time()
        self.loop.run_forever()

    @asyncio.coroutine
    def _simulator_loop(self):
        try:
            while True:
                yield from asyncio.sleep(self._rate)
                with self._lock:
                    now = time.time()
                    delta = now - self._time_since_last_check
                    if delta >= self._display_frequency:
                        sample =  \
                            (self._submitted_batches_sample / delta)
                        self._submitted_batch_samples.append(sample)
                        LOGGER.warning(
                            'Transaction submission rate for last sample '
                            'period is %.2f tps',
                            sample)
                        sample =  \
                            (self._committed_batches_sample / delta)
                        self._committed_batch_samples.append(sample)
                        LOGGER.warning(
                            'Transaction commit rate for last sample period is'
                            ' %.2f tps',
                            sample)

                        # We are going to only use at most the last 10 samples
                        # to calculate the moving average
                        if len(self._submitted_batch_samples) == 11:
                            self._submitted_batch_samples.popleft()
                            self._committed_batch_samples.popleft()

                        LOGGER.warning(
                            'Transaction submission rate for last %d sample(s)'
                            ' is %.2f tps',
                            len(self._submitted_batch_samples),
                            sum(self._submitted_batch_samples) /
                            len(self._submitted_batch_samples))
                        LOGGER.warning(
                            'Transaction commit rate for last %d sample(s)'
                            ' is %.2f tps',
                            len(self._committed_batch_samples),
                            sum(self._committed_batch_samples) /
                            len(self._committed_batch_samples))

                        self._submitted_batches_sample = 0
                        self._committed_batches_sample = 0
                        self._time_since_last_check = now

                    self._number_of_outstanding_requests += 1
                    # If there are pending batchess, then pull off the first
                    # one.
                    batch = \
                        self._pending_batches.popleft() \
                        if len(self._pending_batches) > 0 else None

                    self.loop.run_in_executor(
                        self.thread_pool, self._check_on_batch, batch)

        except KeyboardInterrupt:
            self._workload.on_will_stop()
            self.loop.stop()

    def _check_on_batch(self, batch):
        """ If the batch is not None, then we will check its status and
            perform the appropriate callback into the workload generator.
            This function is run in a separate thread.

            Args:
                batch: PendingBatch named tuple that contains the batch id and
                       the stream the batch was submitted to.
        """
        if batch is not None:
            status = self._get_batch_status(batch.id, batch.stream)
            if status == "COMMITTED":
                committed = True
            else:
                committed = False
            if committed:
                with self._lock:
                    self._committed_batches_sample += 1
                self._workload.on_batch_committed(batch.id)

            else:
                if status == "PENDING":
                    self._workload.on_batch_not_yet_committed()
                    with self._lock:
                        self._pending_batches.appendleft(batch)
                else:
                    LOGGER.debug("Batch's status is %s, "
                                 "dropping batch: %s.",
                                 status, batch.id)
                    self._workload.on_batch_not_yet_committed()
        else:
            self._workload.on_all_batches_committed()

        with self._lock:
            self._number_of_outstanding_requests -= 1

    def _discover_validators(self):
        for validator in self._validators:
            self._workload.on_validator_discovered(validator)

    def _remove_unresponsive_validator(self, validator):
        self._validator.remove(validator)
        self._workload.on_validator_removed(validator)

    def on_new_batch(self, batch_id, stream):
        """
        Called by the workload to let the workload_generator know that a new
        batch should be tracked.

        Args:
            batch_id: The ID for the new batch.
            stream: The validator to which the batch has been submitted.

        Returns:
            Nothing
        """
        if batch_id is not None:
            with self._lock:
                self._submitted_batches_sample += 1
                self._pending_batches.append(
                    PendingBatch(id=batch_id, stream=stream))

    def _get_batch_status(self, batch_id, stream):
        """
        Sends a ClientBatchStatusRequest to the stream that the batch was
        submitted to
        """
        request = ClientBatchStatusRequest(batch_ids=[batch_id])
        future = stream.send(
            message_type=Message.CLIENT_BATCH_STATUS_REQUEST,
            content=request.SerializeToString())
        try:
            result = future.result(timeout=0.5)
            response = ClientBatchStatusResponse()
            response.ParseFromString(result.content)
            return ClientBatchStatusResponse.BatchStatus.Name(
                response.batch_statuses[batch_id])

        except ValidatorConnectionError:
            LOGGER.warnig("The validator at %s is no longer connected. "
                          "Removing Validator.", stream.url)
            self._remove_unresponsive_validator(stream.url)
            return "UNKNOWN"

        except FutureTimeoutError:
            LOGGER.debug("The future timed out for %s.", batch_id)
            return "UNKNOWN"
