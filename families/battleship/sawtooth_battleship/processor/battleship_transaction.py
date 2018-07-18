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
import re
import json
import hashlib

from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError

from sawtooth_battleship.battleship_board import hash_space

LOGGER = logging.getLogger(__name__)


class BattleshipTransaction:

    def __init__(self, name_prefix, transaction):
        """Constructor for the BattleshipTransaction class.

        Args:
            transaction: Dictionary of values for transaction fields.
        """

        header = transaction.header

        try:
            payload = json.loads(
                transaction.payload.decode(), encoding="utf-8")
        except ValueError:
            raise InvalidTransaction("Invalid payload serialization")

        LOGGER.debug("payload recieved by battleship tp: %s", repr(payload))
        self._signer_public_key = header.signer_public_key
        self._name = payload['Name'] if 'Name' in payload else None
        self._action = payload['Action'] if 'Action' in payload else None
        self._board = payload['Board'] if 'Board' in payload else None
        self._ships = payload['Ships'] if 'Ships' in payload else None
        self._column = payload['Column'] if 'Column' in payload else None
        self._row = payload['Row'] if 'Row' in payload else None
        self._reveal_space = payload['RevealSpace'] \
            if 'RevealSpace' in payload else None
        self._reveal_nonce = payload['RevealNonce'] \
            if 'RevealNonce' in payload else None
        self._battleship_addr = \
            _make_battleship_address(name_prefix, self._name)

        # self._column is valid (letter from A-J)
        self._acceptable_columns = set('ABCDEFGHIJ')

        # size of the board (10x10)
        self._size = 10

    def __str__(self):
        oid = "unknown" if not self._signer_public_key else \
            self._signer_public_key

        return "{} {} {}".format(oid, self._action, self._name) \
            if self._action == "CREATE" \
            else "{} {}".format(oid, self._action)

    def check_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.
        """

        # Name (of the game) is always required
        if self._name is None or self._name == '':
            raise InvalidTransaction('name not set')

        # Action is always required
        if self._action is None or self._action == '':
            raise InvalidTransaction('action not set')

        # The remaining validity rules depend upon which action has
        # been specified.

        if self._action == 'CREATE':
            if self._name in store:
                raise InvalidTransaction('game already exists')

            # Restrict game name letters and numbers.
            if not re.match("^[a-zA-Z0-9]*$", self._name):
                raise InvalidTransaction(
                    "Only letters a-z A-Z and numbers 0-9 are allowed in "
                    "the game name!")

        elif self._action == 'JOIN':

            # Check that self._name is in the store (to verify
            # that the game exists (see FIRE below).
            if self._name not in store:
                raise InvalidTransaction(
                    'Trying to join a game that does not exist')

            state = store[self._name]['State']

            if state != "NEW":
                # Check that the game can be joined (the state is 'NEW')
                raise InvalidTransaction(
                    'The game cannot accept any new participant')

            # Check that the game board is the right size (10x10)
            if len(self._board) != self._size:
                raise InvalidTransaction('Game board is not valid size')
            for row in range(0, self._size):
                if len(self._board[row]) != self._size:
                    raise InvalidTransaction(
                        'Game board is not valid size')

            # Validate that self._board contains hash-like strings
            for row in range(0, self._size):
                for col in range(0, self._size):
                    # length of sha512 hexdigest is 32 characters
                    if len(self._board[row][col]) != 128:
                        raise InvalidTransaction("invalid board hash")

        elif self._action == 'FIRE':

            if self._name not in store:
                raise InvalidTransaction('no such game')

            if self._column is None:
                raise InvalidTransaction("Column is required")

            if self._row is None:
                raise InvalidTransaction("Row is required")

            # Check that self._column is valid (letter from A-J)
            if not any((c in self._acceptable_columns) for c in self._column):
                raise InvalidTransaction(
                    'Acceptable columns letters are A to J')

            # Check that self._row is valid (number from 1-10)
            try:
                row = int(self._row)
                if (row < 1) or (row > 10):
                    raise InvalidTransaction(
                        'Acceptable rows numbers are 1 to 10')
            except ValueError:
                raise InvalidTransaction(
                    'Acceptable rows numbers are 1 to 10')

            state = store[self._name]['State']

            if state in ['P1-WIN', 'P2-WIN']:
                raise InvalidTransaction('game complete')

            if state == 'NEW':
                raise InvalidTransaction(
                    "Game doesn't have enough players.")

            player = None
            if state == 'P1-NEXT':
                player1_firing = True
                player = store[self._name]['Player1']
                if player != self._signer_public_key:
                    raise InvalidTransaction('invalid player 1')
            elif state == 'P2-NEXT':
                player1_firing = False
                player = store[self._name]['Player2']
                if player != self._signer_public_key:
                    raise InvalidTransaction('invalid player 2')
            else:
                raise InvalidTransaction(
                    "invalid state: {}".format(state))

            # Check whether the board's column and row have already been
            # fired upon.
            if player1_firing:
                target_board = store[self._name]['TargetBoard1']
            else:
                target_board = store[self._name]['TargetBoard2']

            firing_row = int(self._row) - 1
            firing_column = ord(self._column) - ord('A')
            if target_board[firing_row][firing_column] != '?':
                raise InvalidTransaction(
                    "{} {} has already been fired upon".format(
                        self._column, self._row)
                )

            # Make sure a space is revealed if it isn't the first turn.
            if 'LastFireColumn' in store[self._name]:
                if self._reveal_space is None or self._reveal_nonce is None:
                    raise InvalidTransaction(
                        "Attempted to fire without revealing target")

                if state == 'P1-NEXT':
                    hashed_board = 'HashedBoard1'
                else:
                    hashed_board = 'HashedBoard2'

                col = ord(store[self._name]['LastFireColumn']) - ord('A')
                row = int(store[self._name]['LastFireRow']) - 1
                hashed_space = hash_space(self._reveal_space,
                                          self._reveal_nonce)
                if store[self._name][hashed_board][row][col] != hashed_space:
                    raise InvalidTransaction(
                        "Hash mismatch on reveal: {} != {}".format(
                            store[self._name][hashed_board][row][col],
                            hashed_space))

        else:
            raise InvalidTransaction(
                'invalid action: {}'.format(self._action))

    def apply(self, context):
        """Applies all the updates in the transaction to the transaction
        store.

        Args:
            store: context"""

        state = _get_state_data(self._battleship_addr, context)
        LOGGER.debug('Applying changes to state\nCURRENT STATE:\n%s', state)

        self.check_valid(state)

        if self._action == 'CREATE':
            state[self._name] = {'State': 'NEW', 'Ships': self._ships}
        elif self._action == 'JOIN':
            game = state[self._name].copy()

            # If this is the first JOIN, set HashedBoard1 and Player1 in the
            # store.  if this is the second JOIN, set HashedBoard2 and
            # Player2 in the store.  Also, initialize TargetBoard1 and
            # TargetBoard2 as empty.
            if 'Player1' not in game:
                game['HashedBoard1'] = self._board
                size = len(self._board)
                game['TargetBoard1'] = [['?'] * size for _ in range(size)]
                game['Player1'] = self._signer_public_key
            else:
                game['HashedBoard2'] = self._board
                size = len(self._board)
                game['TargetBoard2'] = [['?'] * size for _ in range(size)]
                game['Player2'] = self._signer_public_key

                # Move to 'P1-NEXT' as both boards have been entered.
                game["State"] = 'P1-NEXT'

            state[self._name] = game
        elif self._action == 'FIRE':
            game = state[self._name].copy()

            # Reveal the previously targeted space
            if 'LastFireColumn' in game:
                if game['State'] == 'P1-NEXT':
                    target_board = 'TargetBoard2'
                else:
                    target_board = 'TargetBoard1'

                col = ord(game['LastFireColumn']) - ord('A')
                row = int(game['LastFireRow']) - 1
                if self._reveal_space != '-':
                    game[target_board][row][col] = 'H'
                else:
                    game[target_board][row][col] = 'M'

                # calculate number of hits for later determination
                # of win
                number_of_hits = sum(sum([1 if space == 'H' else 0
                                          for space in row])
                                     for row in game[target_board])
            else:
                number_of_hits = None

            # Update LastFireColumn and LastFireRow in the store so
            # they can be used in the next transaction.
            game['LastFireColumn'] = self._column
            game['LastFireRow'] = self._row

            # if the game has been won, change the State
            # to P1-WIN or P2-WIN as appropriate
            total_ship_spaces = sum([len(ship) for ship in game['Ships']])
            if number_of_hits is not None and \
                    total_ship_spaces == number_of_hits:
                if target_board == 'TargetBoard2':
                    game['State'] = 'P2-WIN'
                else:
                    game['State'] = 'P1-WIN'

            if game['State'] == 'P1-NEXT':
                game['State'] = 'P2-NEXT'
            elif game['State'] == 'P2-NEXT':
                game['State'] = 'P1-NEXT'

            state[self._name] = game
        else:
            raise InvalidTransaction(
                "invalid state: {}".format(state[self._name].copy))

        _store_state_data(self._battleship_addr, state, context)

    def dump(self):
        """Returns a dict with attributes from the transaction object.

        Returns:
            dict: The updates from the transaction object.
        """
        result = super(BattleshipTransaction, self).dump()

        result['Name'] = self._name
        result['Action'] = self._action
        result['Ships'] = self._ships
        if self._action == 'JOIN':
            result['Board'] = self._board
        if self._action == 'FIRE':
            result['Row'] = self._row
            result['Column'] = self._column
            if self._reveal_space is not None:
                result['RevealSpace'] = self._reveal_space
            if self._reveal_nonce is not None:
                result['RevealNonce'] = self._reveal_nonce

        return result


def _make_battleship_address(namespace_prefix, name):
    return namespace_prefix + \
        hashlib.sha512(name.encode('utf-8')).hexdigest()[:64]


def _get_state_data(game_address, context):
    # Get data from address
    state_entries = context.get_state([game_address])

    # context.get_state() returns a list. If no data has been stored yet
    # at the given address, it will be empty.
    if state_entries:
        try:
            state_data = state_entries[0].data.decode()

            return json.loads(state_data, encoding="utf-8")

        except ValueError:
            raise InternalError("Failed to deserialize game data.")

    else:
        return {}


def _store_state_data(addr, new_state, context):
    LOGGER.debug('Storing Upadated State....\nUPDATED STATE:\n%s', new_state)
    addresses = context.set_state(
        {addr, json.dumps(new_state).encode()}
    )

    if not addresses:
        raise InternalError("State Error")
