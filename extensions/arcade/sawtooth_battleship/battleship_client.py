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


LOGGER = logging.getLogger(__name__)


class BattleshipClient(SawtoothClient):
    def __init__(self,
                 base_url,
                 keyfile):
        super(BattleshipClient, self).__init__(
            base_url=base_url,
            store_name='BattleshipTransaction',
            name='BattleshipClient',
            txntype_name='/BattleshipTransaction',
            msgtype_name='/Battleship/Transaction',
            keyfile=keyfile)

    def send_battleship_txn(self, update):
        """The client needs to have the same
            defaults as the Transaction subclass
            before it is signed inside sendtxn
        """
        if 'Name' not in update:
            update['Name'] = None
        if 'Action' not in update:
            update['Action'] = None
        if 'Ships' not in update:
            update['Ships'] = None
        if update['Action'] == 'JOIN':
            if 'Board' not in update:
                update['Board'] = None
        if update['Action'] == 'FIRE':
            if 'Column' not in update:
                update['Column'] = None
            if 'Row' not in update:
                update['Row'] = None

        return self.sendtxn('/BattleshipTransaction',
                            '/Battleship/Transaction',
                            update)

    def create(self, name, ships):
        """
        """
        update = {
            'Action': 'CREATE',
            'Name': name,
            'Ships': ships
        }

        return self.send_battleship_txn(update)

    def join(self, name, board):
        """
        """
        update = {
            'Action': 'JOIN',
            'Name': name,
            'Board': board
        }

        return self.send_battleship_txn(update)

    def fire(self, name, column, row, reveal_space, reveal_nonce):
        """
        """
        update = {
            'Action': 'FIRE',
            'Name': name,
            'Column': column,
            'Row': row
        }

        if reveal_space is not None:
            update['RevealSpace'] = reveal_space

        if reveal_nonce is not None:
            update['RevealNonce'] = reveal_nonce

        return self.send_battleship_txn(update)
