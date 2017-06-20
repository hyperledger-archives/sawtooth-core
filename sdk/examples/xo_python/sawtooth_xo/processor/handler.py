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

import hashlib
import logging

from sawtooth_sdk.processor.state import StateEntry
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader

LOGGER = logging.getLogger(__name__)


class XoTransactionHandler:
    def __init__(self, namespace_prefix):
        self._namespace_prefix = namespace_prefix

    @property
    def family_name(self):
        return 'xo'

    @property
    def family_versions(self):
        return ['1.0']

    @property
    def encodings(self):
        return ['csv-utf8']

    @property
    def namespaces(self):
        return [self._namespace_prefix]

    def apply(self, transaction, state_store):

        # 1. Deserialize the transaction and verify it is valid
        name, action, space, signer = _unpack_transaction(transaction)

        # 2. Retrieve the game data from state storage
        board, state, player1, player2, game_list = \
            _get_state_data(state_store, name)

        # 3. Validate the game data
        _validate_game_data(
            action, space, signer,
            board, state, player1, player2)

        # 4. Apply the transaction
        if action == "create":
            board = "---------"
            state = "P1-NEXT"
            player1 = ""
            player2 = ""

        elif action == "take":
            # Assign players if new game
            if player1 == "":
                player1 = signer

            elif player2 == "":
                player2 = signer

            # Verify player identity and take space
            lboard = list(board)

            if state == "P1-NEXT" and signer == player1:
                lboard[space - 1] = "X"
                state = "P2-NEXT"

            elif state == "P2-NEXT" and signer == player2:
                lboard[space - 1] = "O"
                state = "P1-NEXT"

            board = "".join(lboard)

            # Update game state
            if _is_win(board, "X"):
                state = "P1-WIN"
            elif _is_win(board, "O"):
                state = "P2-WIN"
            elif '-' not in board:
                state = "TIE"

        # 5. Log for tutorial usage
        if action == "create":
            _display("Player {} created a game.".format(signer[:6]))

        elif action == "take":
            _display(
                "Player {} takes space: {}\n\n".format(signer[:6], space) +
                _game_data_to_str(board, state, player1, player2, name)
            )

        # 6. Put the game data back in state storage
        _store_state_data(
            state_store, game_list,
            name, board, state,
            player1, player2)


def _unpack_transaction(transaction):
    header = TransactionHeader()
    header.ParseFromString(transaction.header)

    # The transaction signer is the player
    signer = header.signer_pubkey

    try:
        # The payload is csv utf-8 encoded string
        name, action, space = transaction.payload.decode().split(",")
    except ValueError:
        raise InvalidTransaction("Invalid payload serialization")

    _validate_transaction(name, action, space)

    if action == 'take':
        space = int(space)

    return name, action, space, signer


def _validate_transaction(name, action, space):
    if not name:
        raise InvalidTransaction('Name is required')

    if '|' in name:
        raise InvalidTransaction('Name cannot contain "|"')

    if not action:
        raise InvalidTransaction('Action is required')

    if action not in ('create', 'take'):
        raise InvalidTransaction('Invalid action: {}'.format(action))

    if action == 'take':
        try:
            assert int(space) in range(1, 10)
        except (ValueError, AssertionError):
            raise InvalidTransaction('Space must be an integer from 1 to 9')


def _validate_game_data(action, space, signer, board, state, player1, player2):
    if action == 'create':
        if board is not None:
            raise InvalidTransaction(
                'Invalid action: Game already exists.')

    elif action == 'take':
        if board is None:
            raise InvalidTransaction(
                'Invalid action: Take requires an existing game.')

        if state in ('P1-WIN', 'P2-WIN', 'TIE'):
            raise InvalidTransaction(
                'Invalid Action: Game has ended.')

        if ((player1 and state == 'P1-NEXT' and player1 != signer)
                or (player2 and state == 'P2-NEXT' and player2 != signer)):
            raise InvalidTransaction(
                "Not this player's turn: {}".format(signer[:6]))

        if board[space - 1] != '-':
            raise InvalidTransaction(
                'Invalid Action: space {} already taken'.format(space))


def _make_xo_address(name):
    return '5b7349' + hashlib.sha512(name.encode('utf-8')).hexdigest()[:64]


def _get_state_data(state_store, name):
    # Get data from address
    state_entries = state_store.get([_make_xo_address(name)])

    # state_store.get() returns a list. If no data has been stored yet
    # at the given address, it will be empty.
    if state_entries:
        try:
            state_data = state_entries[0].data

            game_list = {
                name: (board, state, player1, player2)
                for name, board, state, player1, player2 in [
                    game.split(',')
                    for game in state_data.decode().split('|')
                ]
            }

            board, state, player1, player2 = game_list[name]

        except ValueError:
            raise InternalError("Failed to deserialize game data.")

    else:
        game_list = {}
        board = state = player1 = player2 = None

    return board, state, player1, player2, game_list


def _store_state_data(
        state_store, game_list, name,
        board, state, player1, player2):

    game_list[name] = board, state, player1, player2

    state_data = '|'.join(sorted([
        ','.join([name, board, state, player1, player2])
        for name, (board, state, player1, player2) in game_list.items()
    ])).encode()

    addresses = state_store.set([
        StateEntry(
            address=_make_xo_address(name),
            data=state_data
        )
    ])

    if len(addresses) < 1:
        raise InternalError("State Error")


def _is_win(board, letter):
    wins = ((1, 2, 3), (4, 5, 6), (7, 8, 9),
            (1, 4, 7), (2, 5, 8), (3, 6, 9),
            (1, 5, 9), (3, 5, 7))

    for win in wins:
        if (board[win[0] - 1] == letter
                and board[win[1] - 1] == letter
                and board[win[2] - 1] == letter):
            return True
    return False


def _game_data_to_str(board, state, player1, player2, name):
    board = list(board.replace("-", " "))
    out = ""
    out += "GAME: {}\n".format(name)
    out += "PLAYER 1: {}\n".format(player1[:6])
    out += "PLAYER 2: {}\n".format(player2[:6])
    out += "STATE: {}\n".format(state)
    out += "\n"
    out += "{} | {} | {}\n".format(board[0], board[1], board[2])
    out += "---|---|---\n"
    out += "{} | {} | {}\n".format(board[3], board[4], board[5])
    out += "---|---|---\n"
    out += "{} | {} | {}".format(board[6], board[7], board[8])
    return out


def _display(msg):
    n = msg.count("\n")

    if n > 0:
        msg = msg.split("\n")
        length = max(len(line) for line in msg)
    else:
        length = len(msg)
        msg = [msg]

    LOGGER.debug("+" + (length + 2) * "-" + "+")
    for line in msg:
        LOGGER.debug("+ " + line.center(length) + " +")
    LOGGER.debug("+" + (length + 2) * "-" + "+")
