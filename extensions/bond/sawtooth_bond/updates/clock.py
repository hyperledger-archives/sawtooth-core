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

import logging
import time

from sawtooth.exceptions import InvalidTransactionError

from journal.transaction import Update


LOGGER = logging.getLogger(__name__)


class ClockUpdate(Update):

    def __init__(self, update_type, blocknum, timestamp, previous_block_id):
        super(ClockUpdate, self).__init__(update_type)

        self._blocknum = blocknum
        self._timestamp = timestamp
        self._previous_block_id = previous_block_id
        self.__key__ = "clock{}".format(blocknum)
        self.__prev_key__ = "clock{}".format(blocknum - 1)

    def __str__(self):
        return "({0} {1} {2} {3})".format(self.OriginatorID,
                                          self._blocknum,
                                          self._timestamp,
                                          self._previous_block_id)

    def check_valid(self, store, txn):
        clock_tolerance = 120

        if self._blocknum is None or self._blocknum == '':
            raise InvalidTransactionError('blocknum not set')

        if self._timestamp is None or self._timestamp == '':
            raise InvalidTransactionError('timestamp not set')

        if self.__key__ in store:
            raise InvalidTransactionError(
                'clock entry already exists: {}'.format(self.__key__))

        if self._blocknum != 0 and self.__prev_key__ not in store:
            raise InvalidTransactionError(
                'previous clock entry does not exist: '
                '{}'.format(self.__prev_key__))

        if self._blocknum != 0 and \
           (self._timestamp + clock_tolerance) <= \
                store[self.__prev_key__]['timestamp']:
            raise InvalidTransactionError(
                'timestamp is smaller than prior block blocknum {0}: {1},'
                'blocknum {2}: {3}'.format(
                    self._blocknum - 1,
                    store[self.__prev_key__]['timestamp'],
                    self._blocknum,
                    self._timestamp))

        if self._timestamp >= (time.time() + clock_tolerance):
            raise InvalidTransactionError('timestamp is in the future')

    def apply(self, store, txn):
        info = {
            'object-type': 'clock',
            'object-id': self.__key__,
            'blocknum': self._blocknum,
            'timestamp': self._timestamp,
            'previous-block-id': self._previous_block_id
        }
        store[self.__key__] = info

        info = {
            'object-type': 'clock',
            'object-id': 'current_clock',
            'blocknum': self._blocknum,
            'timestamp': self._timestamp,
            'previous-block-id': self._previous_block_id
        }
        store['current_clock'] = info
