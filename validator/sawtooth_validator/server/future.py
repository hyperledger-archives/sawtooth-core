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
from threading import Condition
from threading import RLock
from threading import Thread
import time


class FutureResult(object):
    def __init__(self, message_type, content):
        self.message_type = message_type
        self.content = content


class Future(object):
    def __init__(self, correlation_id, request=None):
        self.correlation_id = correlation_id
        self.request = request
        self._result = None
        self._condition = Condition()
        self._create_time = time.time()
        self._callback_func = None

    def done(self):
        return self._result is not None

    def result(self):
        with self._condition:
            if self._result is None:
                self._condition.wait()
        return self._result

    def set_result(self, result):
        with self._condition:
            self._reconcile_time = time.time()
            self._result = result
            self._condition.notify()
            if self._callback_func is None:
                self._condition.wait()
            Thread(target=self._callback_func, args=(
                   self.request, result)).start()

    def add_callback(self, callback_func):
        """Add a callback to be executed on set_result.
        The callback must take request and result.
        request is the bytes serialized request,
        result is the FutureResult.

        :param callback_func: a function with parameters request and result
        """
        with self._condition:
            self._callback_func = callback_func
            self._condition.notify_all()

    def get_duration(self):
        return self._reconcile_time - self._create_time


class FutureCollectionKeyError(Exception):
    pass


class FutureCollection(object):
    def __init__(self):
        self._futures = {}
        self._lock = RLock()

    def put(self, future):
        with self._lock:
            self._futures[future.correlation_id] = future

    def set_result(self, correlation_id, result):
        with self._lock:
            future = self.get(correlation_id)
            future.set_result(result)

    def get(self, correlation_id):
        with self._lock:
            if correlation_id not in self._futures:
                raise FutureCollectionKeyError(
                    "no such correlation id: {}".format(correlation_id))
            return self._futures[correlation_id]

    def remove(self, correlation_id):
        with self._lock:
            if correlation_id not in self._futures:
                raise FutureCollectionKeyError(
                    "no such correlation id: {}".format(correlation_id))
            del self._futures[correlation_id]
