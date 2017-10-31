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

from threading import Lock


class Counter:
    def __init__(self, initial_value=0):
        self._value = initial_value
        self._lock = Lock()

    def get(self):
        with self._lock:
            return self._value

    def get_and_inc(self, step=1):
        with self._lock:
            ret_value = self._value
            self._value += step

        return ret_value

    def get_and_dec(self, step=1):
        with self._lock:
            ret_value = self._value
            self._value -= step

        return ret_value

    def inc(self, step=1):
        with self._lock:
            self._value += step

    def dec(self, step=1):
        with self._lock:
            self._value -= step
