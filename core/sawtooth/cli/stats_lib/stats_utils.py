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

from __future__ import print_function

import time
import json
import collections

from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.client import readBody
from twisted.web.http_headers import Headers


class ValidatorCommunications(object):

    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.agent = Agent(reactor)
        self.completion_callback = None
        self.error_callback = None
        self.request_path = None

        self.error_value = None
        self.error_type = None
        self.error_name = None
        self.error_message = None
        self.responding = None
        self.json_stats = None
        self.response_code = None

    def get_request(self, path, ccb=None, ecb=None):
        self.completion_callback = self._completion_default if ccb is None \
            else ccb
        self.error_callback = self._error_default if ecb is None \
            else ecb

        self.request_path = path
        d = self.agent.request(
            'GET',
            path,
            Headers({'User-Agent': ['sawtooth stats collector']}),
            None)

        d.addCallback(self._handle_request)
        d.addErrback(self._handle_error)

        return d

    def _handle_request(self, response):
        self.responding = True
        self.response_code = response.code
        d = readBody(response)
        d.addCallback(self._handle_body)
        return d

    def _handle_body(self, body):
        if self.response_code is 200:
            self.json_stats = json.loads(body)
        else:
            self.json_stats = None
        self.completion_callback(self.json_stats, self.response_code)

    def _handle_error(self, failure):
        self.error_value = failure.value
        self.error_type = failure.type
        self.error_name = failure.type.__name__
        self.error_message = failure.getErrorMessage()

        self.error_count += 1
        self.error_callback(failure)

    def _completion_default(self, data):
        print("ValidatorCommunications.get_request() "
              "default completion handler")
        print(json.dumps(data, indent=4))

    def _error_default(self):
        print("ValidatorCommunications.get_request() "
              "default error handler")


class StatsModule(object):
    def __init__(self):
        self.module_list = []

    def initialize(self, module_list):
        pass

    def connect(self):
        pass

    def collect(self):
        pass

    def process(self):
        pass

    def analyze(self):
        pass

    def report(self):
        pass

    def stop(self):
        pass

    def get_module(self, class_reference, default=None):
        for module in self.module_list:
            if type(module).__name__ == class_reference.__name__:
                return module
        if default is None:
            assert False, "module not found"
        else:
            return default


class DictWalker(object):
    def __init__(self):
        self.name_list = []
        self.unique_name_list = []
        self.unique_name_with_comma_list = []

        # generates a new set of key/value pairs
        # each time walk() is called
        self.data = dict()
        # contains a set of keys ordered by entry order
        # that persists across calls to walk() - this lets you discover
        # (and remember) new keys as the appear in the data stream
        self.names = collections.OrderedDict()

        self.value_type_error_count = 0
        self.value_has_comma_error_count = 0

    def walk(self, data_dict):
        self.data = dict()
        return self._traverse_dict(data_dict)

    def _traverse_dict(self, data_dict):
        for key, value in data_dict.iteritems():
            self.name_list.append(key)
            if isinstance(value, dict):
                self._traverse_dict(value)
            else:
                if isinstance(value, (list, tuple)):
                    self.value_type_error_count += 1
                    value = "value_type_error"
                if isinstance(value, str):
                    if value.find(",") is not -1:
                        self.value_has_comma_error += 1
                        value = "value_comma_error"

                unique_name = self._unique_name(self.name_list)
                if unique_name.find(",") is not -1:
                    self.name_has_comma_error_count += 1
                    self.unique_name_with_comma_list.append(unique_name)
                else:
                    self.unique_name_list.append(unique_name)
                    self.data[unique_name] = value
                    self.names[unique_name] = None

                self.name_list.pop()
        if len(self.name_list) > 0:
            self.name_list.pop()

    def get_data(self):
        # retrieve data using names so it is always reported in the same order
        # this is important when using get_data() and get_names()
        # to write header and data to csv file to ensure headers and data
        # are written in the same order even if the source dictionary changes
        # size (which it will - at minimum validators do not all process
        # the same messages
        data_list = []
        for name, value in self.names.items():
            value = self.data.get(name, "no_val")
            data_list.append(value)
        return data_list

    def get_names(self):
        name_list = []
        for name in self.names:
            name_list.append(name)
        return name_list

    def _unique_name(self, name_list):
        s = ""
        for name in name_list:
            if len(s) == 0:
                s = name
            else:
                s = "{}-{}".format(s, name)
        return s


class TransactionRate(object):
    def __init__(self):
        self.txn_history = collections.deque()
        self.previous_block_count = 0
        self.avg_txn_rate = 0.0
        self.avg_block_time = 0.0
        self.window_time = 0.0
        self.window_txn_count = 0

    def calculate_txn_rate(self, current_block_count, current_txn_count,
                           window_size=10):
        """

        Args:
            current_block_count: current number of committed blocks
            current_txn_count: current number of committed transactions
            window_size: number of blocks to average over

        Synopsis:
            Each time the block count changes, a snapshot of the
            current number of committed txns and current time is placed in
            the queue.  If there are two or more entries in the queue, the
            average txn rate and average block commit time is calculated.
            If there are more than window_size transactions in the queue,
            the oldest entry is popped from the queue.

        Returns:
            avg_txn_rate: average number of transactions per second
            avg_block_time: average block commit time

        """
        if not current_block_count == self.previous_block_count:
            self.previous_block_count = current_block_count
            current_block_time = time.time()
            self.txn_history.append([current_txn_count, current_block_time])
            # if less than 2 samples, can't do anything
            if len(self.txn_history) < 2:
                self.avg_txn_rate = 0.0
                self.avg_block_time = 0.0
                return self.avg_txn_rate, self.avg_block_time
            # otherwise calculate from tip to tail; current is tip, [0] is tail
            past_txn_count, past_block_time = self.txn_history[0]
            self.window_time = current_block_time - past_block_time
            self.window_txn_count = current_txn_count - past_txn_count
            self.avg_txn_rate = \
                float(self.window_txn_count) / self.window_time
            self.avg_block_time = \
                self.window_time / (len(self.txn_history) - 1)
            # if more than "window_size" samples, discard oldest
            if len(self.txn_history) > window_size:
                self.txn_history.popleft()

            return self.avg_txn_rate, self.avg_block_time


class StatsCollector(object):
    def __init__(self):
        self.statslist = []

    def get_names(self):
        """
        Returns: All data element names as list - for csv writer (header)
        """
        names = []

        for stat in self.statslist:
            statname = type(stat).__name__
            for name in stat._fields:
                names.append(statname + "_" + name)

        return names

    def get_data(self):
        """
        Returns: All data element values in list - for csv writer
        """
        values = []

        for stat in self.statslist:
            for value in stat:
                values.append(value)

        return values

    def get_data_as_dict(self):
        """
        Returns: returns platform stats as dictionary - for stats web interface
        """
        p_stats = collections.OrderedDict()

        for stat in self.statslist:
            statname = type(stat).__name__
            p_stats[statname] = stat._asdict()

        return p_stats

    def pprint_stats(self):
        p_stats = self.get_data_as_dict()
        print(json.dumps(p_stats, indent=4))


def get_public_attrs_as_dict(class_instance):
    # walk dictionary of class instance objects
    # filter out built-in attributes, private attributes, functions
    # requires private attributes to start with underscore
    stats = {}
    for key, value in class_instance.__dict__.items():
        if not key.startswith('__') and \
                not key.startswith('_') and \
                not callable(key):
            stats[key] = value
    return stats


def named_tuple_init(named_tuple, default=0, defaults=None):
    '''
    Initialize the instance rather than the named tuple itself because
    some values have to be initialized at runtime
    Args:
        named_tuple: named tuple instance of which is to be returned
        default: default value to be applied to all fields
        defaults: dict of default values to be applied to specified fields

    Returns:
        an initialized instance of the named_tuple
    '''
    nt = named_tuple
    default_map = {}
    for field in nt._fields:
        default_map[field] = default

    if defaults is not None:
        for k, v in defaults.iteritems():
            default_map[k] = v

    nti = named_tuple(**default_map)
    return nti


class SignalHandler(StatsModule):
    def __init__(self):
        super(SignalHandler, self).__init__()
        self.sig_user1 = False
