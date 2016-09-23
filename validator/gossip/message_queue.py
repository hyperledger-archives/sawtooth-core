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
import copy

from collections import deque
from threading import Condition


class MessageQueue(object):
    """The message queue used internally by Gossip."""

    def __init__(self):
        self._queue = deque()
        self._condition = Condition()

    def pop(self):
        self._condition.acquire()
        try:
            while len(self._queue) < 1:
                self._condition.wait()
            return self._queue.pop()
        finally:
            self._condition.release()

    def __len__(self):
        return len(self._queue)

    def __deepcopy__(self, memo):
        newmq = MessageQueue()
        newmq._queue = copy.deepcopy(self._queue, memo)
        return newmq

    def appendleft(self, msg):
        self._condition.acquire()
        try:
            self._queue.appendleft(msg)
            self._condition.notify()
        finally:
            self._condition.release()
