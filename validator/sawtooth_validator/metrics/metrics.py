# Copyright 2018 Intel Corporation
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

import os
import platform


DEBUG = 10
INFO = 20
PERF = 30
DEFAULT = INFO


def init_metrics(level=None, registry=None):
    """
    Initialize metrics reporting with the given level and registry. This
    should be called before get_collector().
    """
    MetricsCollector.set_instance(level, registry)


def get_collector(module_name):
    """
    Get a handle to the metrics collector.
    """
    return MetricsCollectorHandle(module_name.split(".")[-1])


class MetricsCollector:
    __instance = None

    @classmethod
    def set_instance(cls, level=None, registry=None):
        cls.__instance = cls(level, registry)

    @classmethod
    def get_instance(cls, level=None, registry=None):
        if cls.__instance is None:
            cls.set_instance(level, registry)
        return cls.__instance

    def __init__(self, level=None, registry=None):
        if level is None:
            level = DEFAULT
        self._level = level

        self._noop_registry = NoOpMetricsRegistry()
        self._registry = registry

        self._base_tags = (
            ("pid", os.getpid()),
            ("host", platform.node()),
        )

    def gauge(self, identifier, level, instance=None, tags=None):
        if self._registry is None or self._disabled(identifier, level):
            return self._noop_registry.gauge(identifier)

        return self._registry.gauge(
            self._join(identifier, instance, tags))

    def counter(self, identifier, level, instance=None, tags=None):
        if self._registry is None or self._disabled(identifier, level):
            return self._noop_registry.counter(identifier)

        return self._registry.counter(
            self._join(identifier, instance, tags))

    def timer(self, identifier, level, instance=None, tags=None):
        if self._registry is None or self._disabled(identifier, level):
            return self._noop_registry.timer(identifier)

        return self._registry.timer(
            self._join(identifier, instance, tags))

    # Private methods
    def _disabled(self, identifier, level):
        """Check if the metric is enabled based on the level."""
        return level < self._level

    def _join(self, identifier, instance=None, tags=None):
        """
        Join the identifier tuple with periods ".", combine the arbitrary tags
        with the base tags and the identifier tag, convert tags to "tag=value"
        format, and then join everything with ",".
        """
        tag_list = []
        if tags is not None:
            tag_list.extend(tags.items())
        tag_list.extend(self._base_tags)
        if instance is not None:
            tag_list.append(("instance", id(instance)))
        return ".".join(identifier) + "," + ",".join(
            "{}={}".format(k, v)
            for k, v in tag_list
        )


class MetricsCollectorHandle:
    def __init__(self, module_name):
        self._module_name = module_name

    def gauge(self, metric_name, level=DEFAULT, instance=None, tags=None):
        return MetricsCollector.get_instance().gauge(
            identifier=self._create_identifier(metric_name, instance),
            level=level,
            instance=instance,
            tags=tags)

    def counter(self, metric_name, level=DEFAULT, instance=None, tags=None):
        return MetricsCollector.get_instance().counter(
            identifier=self._create_identifier(metric_name, instance),
            level=level,
            instance=instance,
            tags=tags)

    def timer(self, metric_name, level=DEFAULT, instance=None, tags=None):
        return MetricsCollector.get_instance().timer(
            identifier=self._create_identifier(metric_name, instance),
            level=level,
            instance=instance,
            tags=tags)

    def _create_identifier(self, metric_name, instance=None):
        if instance is None:
            return (self._module_name, metric_name)
        return (self._module_name, instance.__class__.__name__, metric_name)


class NoOpMetricsRegistry:
    def __init__(self):
        self._noop_gauge = NoOpGauge()
        self._noop_counter = NoOpCounter()
        self._noop_timer = NoOpTimer()

    def gauge(self, identifier):
        return self._noop_gauge

    def counter(self, identifier):
        return self._noop_counter

    def timer(self, identifier):
        return self._noop_timer


class NoOpGauge:
    def set_value(self, *args, **kwargs):
        pass

    def get_value(self, *args, **kwargs):
        return 0


class NoOpCounter:
    def inc(self, *args, **kwargs):
        pass

    def dec(self, *args, **kwargs):
        pass


class NoOpTimer:
    def __init__(self):
        self._ctx = NoOpTimerContext()

    def time(self):
        return self._ctx


class NoOpTimerContext():
    def __enter__(self):
        pass

    def __exit__(self, exception_type, exception_value, traceback):
        pass

    def stop(self, *args, **kwargs):
        pass
