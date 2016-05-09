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
"""
This module defines the Stats class, which manages statistics about the
gossiper node. Additional supporting classes include: Metric, Value,
Counter, MapCounter, Average, and Sample.
"""

import logging
import time

from gossip import common

logger = logging.getLogger(__name__)


class Stats(object):
    """The Stats class manages a set of Metrics about a Node.

    Attributes:
        NodeIdentifier (str): The node identifier the statistics
            are associated with.
        DomainIdentifier (str): The domain to which the statistics
            belong. Used for developer categorization purposes when
            the statistics are logged. Current values in use include
            'packet', 'message', 'ledger', etc.
        Metrics (dict): A map of associated metrics.

    """

    def __init__(self, nodeid, statid):
        """Constructor for the Stats class.

        Args:
            nodeid (str): The node identifier the statistics are
                associated with.
            statid (str): The domain to which the statistics belong.
        """
        self.NodeIdentifier = nodeid
        self.DomainIdentifier = statid
        self.Metrics = {}

    def add_metric(self, metric):
        """Adds a Metric to the Stats object.

        Args:
            metric (Metric): The metric to add to the Stats object.
        """
        self.Metrics[metric.Name] = metric

    def __getattr__(self, attr):
        if attr in self.Metrics:
            return self.Metrics[attr]

        raise AttributeError("no metric of type %r", attr)

    def get_stats(self, metrics=[]):
        """
        Return a dictionary with current value of the statistics

        Args:
            metrics (list of Metric): A list of metrics to dump.
        """
        if len(metrics) == 0:
            metrics = self.Metrics.keys()

        result = dict()
        for metric in metrics:
            if metric in self.Metrics:
                result[metric] = self.Metrics[metric].get_metric()

        return result

    def dump_stats(self, batchid, metrics=[]):
        """Dumps associated metrics information to the log.

        Args:
            batchid (str): An identifier for correlating logged stats
               output with an event.
            metrics (list of Metric): A list of metrics to dump.
        """
        if len(metrics) == 0:
            metrics = self.Metrics.keys()

        metrics.sort()

        identifier = "{0}, {1:0.2f}, {2}, {3}".format(self.NodeIdentifier,
                                                      time.time(), batchid[:8],
                                                      self.DomainIdentifier)
        for metric in metrics:
            if metric in self.Metrics:
                self.Metrics[metric].dump_metric(identifier)

    def reset_stats(self, metrics=[]):
        """Resets the specified metrics.

        If no metrics are provided, all metrics are reset.

        Args:
            metrics (list of Metric): A list of metrics to reset.
        """
        if len(metrics) == 0:
            metrics = self.Metrics.keys()

        logger.info('metric, %s, %0.2f, %s, %s', self.NodeIdentifier,
                    time.time(), common.NullIdentifier[:8], 'reset')
        for metric in metrics:
            if metric in self.Metrics:
                self.Metrics[metric].reset()


class Metric(object):
    """The Metric class acts as a base class for a number of specific
    Metric types, including Value, Counter, MapCounter, Average, and
    Sample.

    Attributes:
        Name (str): the name of the metric.

    """

    def __init__(self, name):
        """Constructor for the Metric class.

        Args:
            name (str): the name of the metric.
        """
        self.Name = name

    def dump(self, *args):
        """Writes the provided args to a logger entry.

        Args:
            args (list): a list of arguments to append to the logger
               entry.
        """
        logger.info("metric, %s", ", ".join([str(x) for x in args]))
        return args

    def get_metric(self):
        """
        Return the current value of the metric. Subclasses will override.
        """
        return None

    def dump_metric(self, identifier):
        """Writes a logger entry containing the provided identifier and
        the metric name.

        Args:
            identifier (str): The identifier to log.
        """
        return self.dump(identifier, self.Name)

    def reset(self):
        """Base class reset of associated measure.

        Since the base Metric class doesn't track a measure, no action
        is taken.
        """
        pass


class Value(Metric):
    """The Value class extends Metric to track a single associated
    value.

    Attributes:
        Value: The value to track.
    """

    def __init__(self, name, value):
        """Constructor for the Value class.

        Args:
            name (str): The name of the metric.
            value: The value to track.
        """
        super(Value, self).__init__(name)
        self.Value = value

    def get_metric(self):
        """
        Return the current value of the metric.
        """
        return self.Value

    def dump_metric(self, identifier):
        """Writes a logger entry containing the provided identifier,
        the metric name, and the metric value.

        Args:
            identifier (str): The identifier to log.
        """
        return self.dump(identifier, self.Name, self.Value)


class Counter(Metric):
    """The Counter class extends Metric to track a counter value.

    Attributes:
        Value (int): The counter value.
    """

    def __init__(self, name):
        """Constructor for the Counter class.

        Args:
            name (str): The name of the metric.
        """
        super(Counter, self).__init__(name)
        self.reset()

    def increment(self, value=1):
        """Adds to the metric's current value.

        Args:
            value (int): the amount to add to the metric's value.
                Defaults to 1.
        """
        self.Value += int(value)

    def get_metric(self):
        """
        Return the current value of the metric.
        """
        return self.Value

    def dump_metric(self, identifier):
        """Writes a logger entry containing the provided identifier,
        the metric name, and the metric value.

        Args:
            identifier (str): The identifier to log.
        """
        return self.dump(identifier, self.Name, self.Value)

    def reset(self):
        """Resets the value of the metric to zero.
        """
        self.Value = 0


class MapCounter(Metric):
    """The MapCounter class extends Metric to track a set of key/value
    counters.

    Attributes:
        Values (dict): A map of named counter values.
    """

    def __init__(self, name):
        """Constructor for the MapCounter class.

        Args:
            name (str): The name of the metric.
        """
        super(MapCounter, self).__init__(name)
        self.reset()

    def increment(self, key, value=1):
        """Adds to the value of 'key' within the metric.

        Args:
            key (str): The key whose value will be created or incremented.
            value (int): the amount to add to the key's value. Defaults to
                1.
        """
        if key not in self.Values:
            self.Values[key] = 0
        self.Values[key] += int(value)

    def get_metric(self):
        """
        Return the current value of the metric.
        """
        return self.Values

    def dump_metric(self, identifier):
        """Writes a logger entry for each key in the map containing the
        provided identifier, the key and the metric value.

        Args:
            identifier (str): The identifier to log.
        """
        for key, val in self.Values.iteritems():
            self.dump(identifier, key, val)

        return

    def reset(self):
        """Resets the contents of the Values dict.
        """
        self.Values = {}


class Average(Metric):
    """The Average class extends Metric to track an averaged value.

    Attributes:
        Total (int): The total incremented value of the measure.
        Count (int): The number of times that Total has been
            incremented.
    """

    def __init__(self, name):
        """Constructor for the Average class.

        Args:
            name (str): The name of the metric.
        """
        super(Average, self).__init__(name)
        self.reset()

    def add_value(self, value):
        """Adds to the total value and increments the counter.

        Args:
            value (int): The amount to add to the total value.
        """
        self.Total += value
        self.Count += 1

    def get_metric(self):
        """
        Return the current value of the metric.
        """
        return [self.Total, self.Count]

    def dump_metric(self, identifier):
        """Writes a logger entry containing the provided identifier,
        the name of the metric, the total value, and the counter.

        Args:
            identifier (str): The identifier to log.
        """

        self.dump(identifier, self.Name, self.Total, self.Count)

    def reset(self):
        """Resets the total value and the counter to zero.
        """
        self.Total = 0
        self.Count = 0


class Sample(Metric):
    """The Sample class extends Metric to capture the output of a
    provided closure when dump_metric() is called.

    Attributes:
        Closure (function): The function to be called when dump_metric()
            is called.
    """

    def __init__(self, name, closure):
        """Constructor for the Sample class.

        Args:
            name (str): The name of the metric.
            closure (function): The function to be called when dump_metric()
                is called.
        """
        super(Sample, self).__init__(name)
        self.Closure = closure

    def get_metric(self):
        """
        Return the current value of the metric.
        """
        return self.Closure()

    def dump_metric(self, identifier):
        """Writes a logger entry containing the provided identifier, the
        name of the metric, and the return value of Closure()

        Args:
            identifier (str): The identifier to log.
        """
        self.dump(identifier, self.Name, self.Closure())
