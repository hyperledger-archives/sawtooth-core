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
import os

from concurrent.futures import ThreadPoolExecutor

from sawtooth_validator import metrics


LOGGER = logging.getLogger(__name__)
COLLECTOR = metrics.get_collector(__name__)


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

        super().__init__(max_workers)

        self._workers_in_use = COLLECTOR.counter(
            "workers_in_use",
            instance=self,
            tags={"name": self._name})
        # Tracks how long tasks take to run
        self._task_run_timer = COLLECTOR.timer(
            "task_run_time",
            instance=self,
            tags={"name": self._name})
        # Tracks how long tasks wait in the queue
        self._task_time_in_queue_timer = COLLECTOR.timer(
            "task_time_in_queue",
            instance=self,
            tags={"name": self._name})

    def submit(self, fn, *args, **kwargs):
        time_in_queue_ctx = self._task_time_in_queue_timer.time()

        try:
            task_name = fn.__qualname__
        except AttributeError:
            task_name = str(fn)

        if self._trace:
            task_details = '{}[{},{}]'.format(fn, args, kwargs)
        else:
            task_details = task_name

        def wrapper():
            time_in_queue_ctx.stop()

            self._workers_in_use.inc()

            if self._trace:
                LOGGER.debug(
                    '(%s) Executing task %s', self._name, task_details)

            with self._task_run_timer.time():
                return_value = None
                try:
                    return_value = fn(*args, **kwargs)
                # pylint: disable=broad-except
                except Exception:
                    LOGGER.exception(
                        '(%s) Unhandled exception during execution of task %s',
                        self._name,
                        task_details)

                self._workers_in_use.dec()

                if self._trace:
                    LOGGER.debug(
                        '(%s) Finished task %s', self._name, task_details)

                return return_value

        return super().submit(wrapper)
