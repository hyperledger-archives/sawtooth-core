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

    def gauge(self, name, default=0):
        return self._registry.gauge(
            ''.join([name, ',host=', platform.node()]),
            default=default)

    def counter(self, name, tags=None):
        if not tags:
            tags = []
        return self._registry.counter(
            ','.join([name, 'host={}'.format(platform.node())] + tags))

    def timer(self, name, tags=None):
        if not tags:
            tags = []
        return self._registry.timer(
            ','.join([name, 'host={}'.format(platform.node())] + tags))


class CounterWrapper():
    def __init__(self, counter=None):
        self._counter = counter

    def inc(self, val=1):
        if self._counter:
            self._counter.inc(val)


class GaugeWrapper():
    def __init__(self, gauge=None):
        self._gauge = gauge

    def set_value(self, val):
        if self._gauge:
            self._gauge.set_value(val)

    def get_value(self):
        if self._gauge:
            return self._gauge.get_value()
        return 0


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
        return self._noop
