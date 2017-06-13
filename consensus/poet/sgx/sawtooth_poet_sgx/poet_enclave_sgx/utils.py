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

import json
import os
import re
from collections import deque
from threading import Lock


class LruCache(object):
    """
    A simple thread-safe lru cache.
    """
    def __init__(self, max_size=100):
        self.max_size = max_size
        self.order = deque(maxlen=self.max_size)
        self.values = {}
        self.lock = Lock()

    def __setitem__(self, key, value):
        with self.lock:
            if key not in self.values:
                while len(self.order) >= self.max_size:
                    v = self.order.pop()
                    del self.values[v]
                self.values[key] = value
                self.order.appendleft(key)

    def __getitem__(self, key):
        return self.get(key)

    def get(self, key, default=None):
        with self.lock:
            result = self.values.get(key, default)
            if result is not default:
                self.order.remove(key)
                self.order.appendleft(key)
        return result


def parse_configuration_file(filename):
    cpattern = re.compile('##.*$')

    with open(filename) as fp:
        lines = fp.readlines()

    text = ""
    for line in lines:
        text += re.sub(cpattern, '', line) + ' '

    config = ascii_encode_dict(json.loads(text))

    params = os.environ.copy()
    params["CONFIGPATH"] = os.path.dirname(os.path.realpath(filename))
    for k, v in config.iteritems():
        if isinstance(v, str):
            config[k] = v.format(**params)

    return config


def ascii_encode_dict(item):
    """
    Support method to ensure that JSON is converted to ascii since unicode
    identifiers, in particular, can cause problems
    """
    if isinstance(item, dict):
        return dict(
            (ascii_encode_dict(key), ascii_encode_dict(item[key]))
            for key in item.keys())
    elif isinstance(item, list):
        return [ascii_encode_dict(element) for element in item]
    elif isinstance(item, unicode):
        return item.encode('ascii')
    else:
        return item
