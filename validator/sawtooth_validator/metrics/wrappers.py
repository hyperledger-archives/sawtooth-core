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

import platform


class MetricsRegistryWrapper():
    def __init__(self, registry):
        self._registry = registry

    def gauge(self, name):
        return self._registry.gauge(
            ''.join([name, ',host=', platform.node()]))

    def counter(self, name):
        return self._registry.counter(
            ''.join([name, ',host=', platform.node()]))

    def timer(self, name):
        return self._registry.timer(
            ''.join([name, ',host=', platform.node()]))


class CounterWrapper():
    def __init__(self, counter=None):
        self._counter = counter

    def inc(self):
        if self._counter:
            self._counter.inc()


class NoopTimerContext():
    def __enter__(self):
        pass

    def __exit__(self, exception_type, exception_value, traceback):
        pass

    def stop(self):
        pass


class TimerWrapper():
    def __init__(self, timer=None):
        self._timer = timer
        self._noop = NoopTimerContext()

    def time(self):
        if self._timer:
            return self._timer.time()
        else:
            return self._noop
