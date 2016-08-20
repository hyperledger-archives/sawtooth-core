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


LOGGER = logging.getLogger(__name__)


class BattleshipClient(SawtoothClient):
    def __init__(self,
                 base_url,
                 keyfile):
        super(BattleshipClient, self).__init__(
            base_url=base_url,
            store_name='BattleshipTransaction',
            name='BattleshipClient',
            transaction_type=BattleshipTransaction,
            message_type=BattleshipTransaction.MessageType,
            keyfile=keyfile)

    def create(self, name, ships):
        """
        """
        update = {
            'Action': 'CREATE',
            'Name': name,
            'Ships': ships
        }

        return self.sendtxn(
            BattleshipTransaction,
            BattleshipTransaction.MessageType,
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
            BattleshipTransaction.MessageType,
            update)

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

        return self.sendtxn(
            BattleshipTransaction,
            BattleshipTransaction.MessageType,
            update)
