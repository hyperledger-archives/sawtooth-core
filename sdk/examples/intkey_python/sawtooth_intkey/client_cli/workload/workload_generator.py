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
import json
from http.client import RemoteDisconnected

from threading import Lock
from collections import deque
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures._base import CancelledError
import requests
from sawtooth_sdk.messaging.exceptions import WorkloadConfigurationError

PendingBatch = namedtuple('PendingBatch', ['id', 'url'])

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


class WorkloadGenerator:
    """
    This is the object that manages the workload sent to the validators and
    keeps track of submitted and committed batches. To run, it must first have
    a Workload set, as this is where the batches are created.
    """

    def __init__(self, args):
        self._workload = None
        self._auth_info = args.auth_info
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
                        sum(self._submitted_batch_samples)
                        / len(self._submitted_batch_samples))
                    LOGGER.warning(
                        'Transaction commit rate for last %d sample(s)'
                        ' is %.2f tps',
                        len(self._committed_batch_samples),
                        sum(self._committed_batch_samples)
                        / len(self._committed_batch_samples))

                    self._submitted_batches_sample = 0
                    self._committed_batches_sample = 0
                    self._time_since_last_check = now

                self._number_of_outstanding_requests += 1
                # If there are pending batchess, then pull off the first
                # one.
                batch = \
                    self._pending_batches.popleft() \
                    if self._pending_batches else None
                self.loop.run_in_executor(
                    self.thread_pool, self._check_on_batch, batch)

    def stop(self):
        tasks = list(asyncio.Task.all_tasks(self.loop))
        for task in tasks:
            self.loop.call_soon_threadsafe(task.cancel)
        try:
            self.loop.run_until_complete(asyncio.gather(*tasks))
        except CancelledError:
            self.loop.call_soon_threadsafe(self.loop.stop)
        self._workload.on_will_stop()

    def _check_on_batch(self, batch):
        """ If the batch is not None, then we will check its status and
            perform the appropriate callback into the workload generator.
            This function is run in a separate thread.

            Args:
                batch: PendingBatch named tuple that contains the batch id and
                       the url the batch was submitted to.
        """
        if batch is not None:
            status = self._status_request([batch.id], batch.url,
                                          auth_info=self._auth_info)
            if status == "COMMITTED":
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
        if validator in self._validators:
            self._validators.remove(validator)
        self._workload.on_validator_removed(validator)

    def on_new_batch(self, batch_id, url):
        """
        Called by the workload to let the workload_generator know that a new
        batch should be tracked.

        Args:
            batch_id: The ID for the new batch.
            url: The rest_api to which the batch has been submitted.

        Returns:
            Nothing
        """
        if batch_id is not None:
            with self._lock:
                self._submitted_batches_sample += 1
                self._pending_batches.append(
                    PendingBatch(id=batch_id, url=url))

    def _status_request(self, batch_id, url, auth_info=None):
        data = json.dumps(batch_id).encode()
        headers = {'Content-Type': 'application/json'}
        headers['Content-Length'] = '%d' % len(data)
        if auth_info is not None:
            headers['Authorization'] = 'Basic {}'.format(auth_info)

        try:
            result = requests.post(
                url + '/batch_statuses', data=data, headers=headers)

            code, json_result = \
                result.status_code, result.json()
            result.raise_for_status()

            if code in (200, 201, 202):
                return json_result['data'][0]['status']

            if 'error' in json_result:
                message = json_result['error']['message']
            else:
                message = json_result

            LOGGER.debug("(%s): %s", code, message)
            return "UNKNOWN"

        except json.decoder.JSONDecodeError as e:
            LOGGER.warning('Unable to retrieve status: %s', str(e))
            return "UNKNOWN"

        except requests.exceptions.HTTPError as e:
            error_code = e.response.json()['error']['code']
            if error_code == 18:
                self._remove_unresponsive_validator(url)
                LOGGER.warning("The validator at %s is no longer connected. "
                               "Removing Validator.", url)
            return "UNKNOWN"
        except RemoteDisconnected as e:
            self._remove_unresponsive_validator(url)
            LOGGER.warning("The validator at %s is no longer connected. "
                           "Removing Validator.", url)
            return "UNKNOWN"
        except requests.exceptions.ConnectionError as e:
            LOGGER.warning(
                'Unable to connect to "%s": make sure URL is correct', url)
            self._remove_unresponsive_validator(url)
            return "UNKNOWN"
