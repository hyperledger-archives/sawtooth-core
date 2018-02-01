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

from sawtooth_validator.metrics.wrappers import CounterWrapper
from sawtooth_validator.metrics.wrappers import GaugeWrapper
from sawtooth_validator.metrics.wrappers import TimerWrapper


def make_counter(name, metrics_registry=None):
    if metrics_registry is None:
        return CounterWrapper()

    return CounterWrapper(
        metrics_registry.counter(name))


def make_gauge(name, metrics_registry=None):
    if metrics_registry is None:
        return GaugeWrapper()

    return GaugeWrapper(
        metrics_registry.gauge(name))


def make_timer(name, metrics_registry=None):
    if metrics_registry is None:
        return TimerWrapper()

    return TimerWrapper(
        metrics_registry.timer(name))
