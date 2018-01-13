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
import multiprocessing
import time
import os

from concurrent.futures import ThreadPoolExecutor

from sawtooth_validator.concurrent import atomic


LOGGER = logging.getLogger(__name__)


class InstrumentedThreadPoolExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers=None, name='', trace=None):
        if trace is None:
            self._trace = 'SAWTOOTH_TRACE_LOGGING' in os.environ
        else:
            self._trace = trace

        self._name = name
        if name == '':
            self._name = 'Instrumented'

        LOGGER.debug('Creating thread pool executor %s', self._name)

        self._workers_in_use = atomic.Counter()

        self._max_workers = max_workers
        if self._max_workers is None:
            # This is the same default as ThreadPoolExecutor, but we want to
            # know how many workers there are for logging
            self._max_workers = multiprocessing.cpu_count() * 5
        super().__init__(max_workers)

    def submit(self, fn, *args, **kwargs):
        submitted_time = time.time()

        try:
            task_name = fn.__qualname__
        except AttributeError:
            task_name = str(fn)

        if self._trace:
            task_details = '{}[{},{}]'.format(fn, args, kwargs)
        else:
            task_details = task_name

        def wrapper():
            start_time = time.time()
            workers_already_in_use = self._workers_in_use.get_and_inc()
            time_in_queue = (start_time - submitted_time) * 1000.0

            if self._trace:
                LOGGER.debug(
                    '(%s) Task \'%s\' in queue for %0.3f ms',
                    self._name,
                    task_name,
                    time_in_queue)
                LOGGER.debug(
                    '(%s) Workers already in use %s/%s',
                    self._name,
                    workers_already_in_use,
                    self._max_workers)
                LOGGER.debug(
                    '(%s) Executing task %s', self._name, task_details)

            return_value = None
            try:
                return_value = fn(*args, **kwargs)
            # pylint: disable=broad-except
            except Exception:
                LOGGER.exception(
                    '(%s) Unhandled exception during execution of task %s',
                    self._name,
                    task_details)

            end_time = time.time()
            run_time = (end_time - start_time) * 1000.0

            self._workers_in_use.dec()

            if self._trace:
                LOGGER.debug(
                    '(%s) Finished task %s', self._name, task_details)

                LOGGER.debug(
                    '(%s) Task \'%s\' took %0.3f ms',
                    self._name,
                    task_name,
                    run_time)

            return return_value

        return super().submit(wrapper)
