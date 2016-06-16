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

from sawtooth.client import SawtoothClient

from sawtooth_battleship.txn_family import BattleshipTransaction
from sawtooth_battleship.txn_family import BattleshipTransactionMessage


LOGGER = logging.getLogger(__name__)


class BattleshipClient(SawtoothClient):
    def __init__(self,
                 base_url,
                 keyfile):
        super(BattleshipClient, self).__init__(
            base_url=base_url,
            store_name='BattleshipTransaction',
            name='BattleshipClient',
            keyfile=keyfile)

    def create(self, name):
        """
        """
        update = {
            'Action': 'CREATE',
            'Name': name
        }

        return self.sendtxn(
            BattleshipTransaction,
            BattleshipTransactionMessage,
            update)


    def join(self, name, board):
        """
        """
        update = {
            'Action': 'JOIN',
            'Name': name,
            'Board': board
        }

        return self.sendtxn(
            BattleshipTransaction,
            BattleshipTransactionMessage,
            update)


    def fire(self, name, column, row):
        """
        """
        update = {
            'Action': 'FIRE',
            'Name': name,
            'Column': column,
            'Row': row
        }

        return self.sendtxn(
            BattleshipTransaction,
            BattleshipTransactionMessage,
            update)
