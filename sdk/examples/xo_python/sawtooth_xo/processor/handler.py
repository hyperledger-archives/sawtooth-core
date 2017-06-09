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
        header = TransactionHeader()
        header.ParseFromString(transaction.header)

        # The transaction signer is the player
        player = header.signer_pubkey

        try:
            # The payload is csv utf-8 encoded string
            name, action, space = transaction.payload.decode().split(",")
        except ValueError:
            raise InvalidTransaction("Invalid payload serialization")

        if name == "":
            raise InvalidTransaction("Name is required")

        if '|' in name:
            raise InvalidTransaction('Name cannot contain "|"')

        if action == "":
            raise InvalidTransaction("Action is required")

        elif action == "take":
            try:
                space = int(space)
            except ValueError:
                raise InvalidTransaction(
                    "Space could not be converted as an integer."
                )

            if space < 1 or space > 9:
                raise InvalidTransaction("Invalid space {}".format(space))

        if action not in ("take", "create"):
            raise InvalidTransaction("Invalid Action : '{}'".format(action))

        # 2. Retrieve the game data from state storage

        # Use the namespace prefix + the has of the game name to create the
        # storage address
        game_address = self._namespace_prefix \
            + hashlib.sha512(name.encode("utf-8")).hexdigest()[0:64]

        # Get data from address
        state_entries = state_store.get([game_address])

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

        # 3. Validate the game data
        if action == "create" and board is not None:
            raise InvalidTransaction("Invalid Action: Game already exists.")

        elif action == "take":
            if board is None:
                raise InvalidTransaction(
                    "Invalid Action: Take requires an existing game."
                )
            else:
                if state in ("P1-WIN", "P2-WIN", "TIE"):
                    raise InvalidTransaction(
                        "Invalid Action: Game has ended."
                    )
                elif state not in ("P1-NEXT", "P2-NEXT"):
                    raise InternalError(
                        "Game has reached an invalid state: {}".format(state))

        # 4. Apply the transaction
        if action == "create":
            board = "---------"
            state = "P1-NEXT"
            player1 = ""
            player2 = ""

        elif action == "take":
            # Assign players if new game
            if player1 == "":
                player1 = player

            elif player2 == "":
                player2 = player

            # Verify player identity and take space
            lboard = list(board)

            if lboard[space - 1] != '-':
                raise InvalidTransaction(
                    "Invalid Action: Space already taken."
                )

            if state == "P1-NEXT" and player == player1:
                lboard[space - 1] = "X"
                state = "P2-NEXT"

            elif state == "P2-NEXT" and player == player2:
                lboard[space - 1] = "O"
                state = "P1-NEXT"

            else:
                raise InvalidTransaction(
                    "Not this player's turn: {}".format(player[:6])
                )
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
            _display("Player {} created a game.".format(player[:6]))

        elif action == "take":
            _display(
                "Player {} takes space: {}\n\n".format(player[:6], space) +
                _game_data_to_str(board, state, player1, player2, name)
            )

        # 6. Put the game data back in state storage
        game_list[name] = board, state, player1, player2

        state_data = '|'.join(sorted([
            ','.join([name, board, state, player1, player2])
            for name, (board, state, player1, player2) in game_list.items()
        ])).encode()

        addresses = state_store.set([
            StateEntry(
                address=game_address,
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
