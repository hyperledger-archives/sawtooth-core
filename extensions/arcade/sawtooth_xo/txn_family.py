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

from sawtooth.exceptions import InvalidTransactionError

LOGGER = logging.getLogger(__name__)


def _register_transaction_types(journal):
    """Registers the Xo transaction types on the ledger.

    Args:
        ledger (journal.journal_core.Journal): The ledger to register
            the transaction type against.
    """
    journal.dispatcher.register_message_handler(
        XoTransactionMessage,
        transaction_message.transaction_message_handler)
    journal.add_transaction_store(XoTransaction)


class XoTransactionMessage(transaction_message.TransactionMessage):
    """Xo transaction message represent Xo transactions.

    Attributes:
        MessageType (str): The class name of the message.
        Transaction (XoTransaction): The transaction the
            message is associated with.
    """
    MessageType = "/Xo/Transaction"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}

        super(XoTransactionMessage, self).__init__(minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = XoTransaction(tinfo)


class XoTransaction(transaction.Transaction):
    """A Transaction is a set of updates to be applied atomically
    to a ledger.

    It has a unique identifier and a signature to validate the source.

    Attributes:
        TransactionTypeName (str): The name of the Xo
            transaction type.
        TransactionTypeStore (type): The type of transaction store.
        MessageType (type): The object type of the message associated
            with this transaction.
    """
    TransactionTypeName = '/XoTransaction'
    TransactionStoreType = global_store_manager.KeyValueStore
    MessageType = XoTransactionMessage

    def __init__(self, minfo=None):
        """Constructor for the XoTransaction class.

        Args:
            minfo: Dictionary of values for transaction fields.
        """

        if minfo is None:
            minfo = {}

        super(XoTransaction, self).__init__(minfo)

        LOGGER.debug("minfo: %s", repr(minfo))
        self._name = minfo['Name'] if 'Name' in minfo else None
        self._action = minfo['Action'] if 'Action' in minfo else None
        self._space = minfo['Space'] if 'Space' in minfo else None

    def __str__(self):
        try:
            oid = self.OriginatorID
        except AssertionError:
            oid = "unknown"
        return "({0} {1} {2})".format(oid,
                                      self._name,
                                      self._space)

    def check_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.
        """

        super(XoTransaction, self).check_valid(store)

        LOGGER.debug('checking %s', str(self))

        if self._name is None or self._name == '':
            raise InvalidTransactionError('name not set')

        if self._action is None or self._action == '':
            raise InvalidTransactionError('action not set')

        if self._action == 'CREATE':
            if self._name in store:
                raise InvalidTransactionError('game already exists')
        elif self._action == 'TAKE':
            if self._space is None:
                raise InvalidTransactionError('TAKE requires space')

            if self._space < 1 or self._space > 9:
                raise InvalidTransactionError('invalid space')

            if self._name not in store:
                raise InvalidTransactionError('no such game')

            state = store[self._name]['State']
            if state in ['P1-WIN', 'P2-WIN', 'TIE']:
                raise InvalidTransactionError('game complete')

            if state == 'P1-NEXT' and 'Player1' in store[self._name]:
                player1 = store[self._name]['Player1']
                if player1 != self.OriginatorID:
                    raise InvalidTransactionError('invalid player 1')

            if state == 'P2-NEXT' and 'Player2' in store[self._name]:
                player1 = store[self._name]['Player2']
                if player1 != self.OriginatorID:
                    raise InvalidTransactionError('invalid player 2')

            if store[self._name]['Board'][self._space - 1] != '-':
                raise InvalidTransactionError('space already taken')
        else:
            raise InvalidTransactionError('invalid action')

    def _is_win(self, board, letter):
        wins = ((1, 2, 3), (4, 5, 6), (7, 8, 9),
                (1, 4, 7), (2, 5, 8), (3, 6, 9),
                (1, 5, 9), (3, 5, 7))

        for win in wins:
            if (board[win[0] - 1] == letter
                    and board[win[1] - 1] == letter
                    and board[win[2] - 1] == letter):
                return True

        return False

    def apply(self, store):
        """Applies all the updates in the transaction to the transaction
        store.

        Args:
            store (dict): Transaction store mapping.
        """
        LOGGER.debug('apply %s', str(self))

        if self._name in store:
            game = store[self._name].copy()
        else:
            game = {}

        if 'Board' in game:
            board = list(game['Board'])
        else:
            board = list('---------')
            state = 'P1-NEXT'

        if self._space is not None:
            if board.count('X') > board.count('O'):
                board[self._space - 1] = 'O'
                state = 'P1-NEXT'
            else:
                board[self._space - 1] = 'X'
                state = 'P2-NEXT'

            # The first time a space is taken, player 1 will be assigned.  The
            # second time a space is taken, player 2 will be assigned.
            if 'Player1' not in game:
                game['Player1'] = self.OriginatorID
            elif 'Player2' not in game:
                game['Player2'] = self.OriginatorID

        game['Board'] = "".join(board)
        if self._is_win(game['Board'], 'X'):
            state = 'P1-WIN'
        elif self._is_win(game['Board'], 'O'):
            state = 'P2-WIN'
        elif '-' not in game['Board']:
            state = 'TIE'

        game['State'] = state
        store[self._name] = game

    def dump(self):
        """Returns a dict with attributes from the transaction object.

        Returns:
            dict: The updates from the transaction object.
        """
        result = super(XoTransaction, self).dump()

        result['Action'] = self._action
        result['Name'] = self._name
        if self._space is not None:
            result['Space'] = self._space

        return result
