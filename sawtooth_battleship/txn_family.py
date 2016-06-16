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
# -----------------------------------------------------------------------------

import logging

from journal import transaction, global_store_manager
from journal.messages import transaction_message

from sawtooth_battleship.battleship_exceptions import BattleshipException

LOGGER = logging.getLogger(__name__)


def _register_transaction_types(ledger):
    """Registers the Battleship transaction types on the ledger.

    Args:
        ledger (journal.journal_core.Journal): The ledger to register
            the transaction type against.
    """
    ledger.register_message_handler(
        BattleshipTransactionMessage,
        transaction_message.transaction_message_handler)
    ledger.add_transaction_store(BattleshipTransaction)


class BattleshipTransactionMessage(transaction_message.TransactionMessage):
    """Battleship transaction message represent Battleship transactions.

    Attributes:
        MessageType (str): The class name of the message.
        Transaction (BattleshipTransaction): The transaction the
            message is associated with.
    """
    MessageType = "/Battleship/Transaction"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}

        super(BattleshipTransactionMessage, self).__init__(minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = BattleshipTransaction(tinfo)


class BattleshipTransaction(transaction.Transaction):
    """A Transaction is a set of updates to be applied atomically
    to a ledger.

    It has a unique identifier and a signature to validate the source.

    Attributes:
        TransactionTypeName (str): The name of the Battleship
            transaction type.
        TransactionTypeStore (type): The type of transaction store.
        MessageType (type): The object type of the message associated
            with this transaction.
    """
    TransactionTypeName = '/BattleshipTransaction'
    TransactionStoreType = global_store_manager.KeyValueStore
    MessageType = BattleshipTransactionMessage

    def __init__(self, minfo=None):
        """Constructor for the BattleshipTransaction class.

        Args:
            minfo: Dictionary of values for transaction fields.
        """

        if minfo is None:
            minfo = {}

        super(BattleshipTransaction, self).__init__(minfo)

        LOGGER.debug("minfo: %s", repr(minfo))
        self._name = minfo['Name'] if 'Name' in minfo else None
        self._action = minfo['Action'] if 'Action' in minfo else None

    def __str__(self):
        try:
            oid = self.OriginatorID
        except AssertionError:
            oid = "unknown"

        if self._action == "CREATE":
            return "{} {} {}".format(oid, self._action, self._name)
        else:
            return "{} {}".format(oid, self._action)

    def is_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.
        """

        try:
            self.check_valid(store)
        except BattleshipException as e:
            LOGGER.debug('invalid transaction (%s): %s', str(e), str(self))
            return False

        return True

    def check_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.
        """

        if not super(BattleshipTransaction, self).is_valid(store):
            raise BattleshipException("invalid transaction")
        
        LOGGER.debug('checking %s', str(self))

        if self._name is None or self._name == '':
            raise BattleshipException('name not set')

        if self._action is None or self._action == '':
            raise BattleshipException('action not set')

        if self._action == 'CREATE':    
            if self._name in store:
                raise BattleshipException('game already exists')
        elif self._action == 'FIRE':
            if self._name not in store:
                raise BattleshipException('no such game')
            
            #TODO: how to deal with the board without space?
            #TODO: Set spaec to 25 for a 5x5 board game
            """
            if self._space < 1 or self._space > 25:  
                raise BattleshipException('invalid choice')
            
            """
            state = store[self._name]['State']
            
            # TIE isn't possible during a battleship 
            if state in ['P1-WIN', 'P2-WIN']:
                raise XoException('game complete')

            if state == 'P1-NEXT' and 'Player1' in store[self._name]:
                player1 = store[self._name]['Player1']
                if player1 != self.OriginatorID:
                    raise XoException('invalid player 1')

            if state == 'P2-NEXT' and 'Player2' in store[self._name]:
                player1 = store[self._name]['Player2']
                if player1 != self.OriginatorID:
                    raise XoException('invalid player 2')

            if store[self._name]['Board'][self._space - 1] != '-':
                raise XoException('space already bombed')

        elif self._action == 'ADD_BOARD':
            raise BattleshipException('ADD_BOARD not implemented')
        elif self._action == 'REVEAL':
            raise BattleshipException('REVEAL not implemented')
        else:
            raise BattleshipException('invalid action')

        

    def apply(self, store):
        """Applies all the updates in the transaction to the transaction
        store.

        Args:
            store (dict): Transaction store mapping.
        """
        LOGGER.debug('apply %s', str(self))
        LOGGER.error('BattleshipTransaction.apply() not implemented')

    def dump(self):
        """Returns a dict with attributes from the transaction object.

        Returns:
            dict: The updates from the transaction object.
        """
        result = super(BattleshipTransaction, self).dump()

        result['Name'] = self._name
        result['Action'] = self._action

        return result
