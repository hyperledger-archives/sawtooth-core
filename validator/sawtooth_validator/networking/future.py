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

import logging
from threading import Condition
from threading import RLock
import time


LOGGER = logging.getLogger(__name__)


class FutureResult:
    def __init__(self, message_type, content, connection_id=None):
        self.message_type = message_type
        self.content = content
        self.connection_id = connection_id


class FutureTimeoutError(Exception):
    pass


class Future:
    def __init__(self, correlation_id, request=None, callback=None,
                 timer_ctx=None):
        self.correlation_id = correlation_id
        self._request = request
        self._result = None
        self._condition = Condition()
        self._create_time = time.time()
        self._callback_func = callback
        self._reconcile_time = None
        self._timer_ctx = timer_ctx

    def done(self):
        return self._result is not None

    @property
    def request(self):
        return self._request

    def result(self, timeout=None):
        with self._condition:
            if self._result is None:
                if not self._condition.wait(timeout):
                    raise FutureTimeoutError('Future timed out')
        return self._result

    def set_result(self, result):
        with self._condition:
            self._reconcile_time = time.time()
            self._result = result
            self._condition.notify()

    def run_callback(self):
        """Calls the callback_func, passing in the two positional arguments,
        conditionally waiting if the callback function hasn't been set yet.
        Meant to be run in a threadpool owned by the FutureCollection.

        Returns:
            None
        """

        if self._callback_func is not None:
            try:
                self._callback_func(self._request, self._result)
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception('An unhandled error occurred while running '
                                 'future callback')

    def get_duration(self):
        return self._reconcile_time - self._create_time

    def timer_stop(self):
        if self._timer_ctx:
            self._timer_ctx.stop()
        self._timer_ctx = None


class FutureCollectionKeyError(Exception):
    pass


class FutureCollection:
    def __init__(self, resolving_threadpool=None):
        self._futures = {}
        self._lock = RLock()
        self._resolving_threadpool = resolving_threadpool

    def put(self, future):
        self._futures[future.correlation_id] = future

    def set_result(self, correlation_id, result):
        with self._lock:
            future = self.get(correlation_id)
            future.set_result(result)
            if self._resolving_threadpool is not None:
                self._resolving_threadpool.submit(future.run_callback)
            else:
                future.run_callback()

    def get(self, correlation_id):
        try:
            return self._futures[correlation_id]
        except KeyError:
            raise FutureCollectionKeyError(
                "no such correlation id: {}".format(correlation_id))

    def remove(self, correlation_id):
        try:
            del self._futures[correlation_id]
        except KeyError:
            raise FutureCollectionKeyError(
                "no such correlation id: {}".format(correlation_id))
