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

from sawtooth_sdk.processor.state import StateEntry
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader

LOGGER = logging.getLogger(__name__)


class BattleshipHandler(object):
    def __init__(self, namespace_prefix):
        self._namespace_prefix = namespace_prefix

    @property
    def family_name(self):
        return 'battleship'

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
        except:
            raise InvalidTransaction("Invalid payload serialization")

        if name == "":
            raise InvalidTransaction("Name is required")

        if action == "":
            raise InvalidTransaction("Action is required")

        if action == 'CREATE':
            state_store[self._name] = {'State': 'NEW', 'Ships': self._ships}
        elif action == 'JOIN':
            game = state_store[self._name].copy()

            # If this is the first JOIN, set HashedBoard1 and Player1 in the
            # store.  if this is the second JOIN, set HashedBoard2 and
            # Player2 in the store.  Also, initialize TargetBoard1 and
            # TargetBoard2 as empty.
            if 'Player1' not in game:
                game['HashedBoard1'] = self._board
                size = len(self._board)
                game['TargetBoard1'] = [['?'] * size for _ in range(size)]
                game['Player1'] = self.OriginatorID
            else:
                game['HashedBoard2'] = self._board
                size = len(self._board)
                game['TargetBoard2'] = [['?'] * size for _ in range(size)]
                game['Player2'] = self.OriginatorID

                # Move to 'P1-NEXT' as both boards have been entered.
                game["State"] = 'P1-NEXT'

            state_store[self._name] = game
        elif self._action == 'FIRE':
            game = state_store[self._name].copy()

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

            state_store[self._name] = game
        else:
            raise InvalidTransaction(
                "invalid state: {}".format(state_store[self._name].copy))


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

    print("+" + (length + 2) * "-" + "+")
    for line in msg:
        print("+ " + line.center(length) + " +")
    print("+" + (length + 2) * "-" + "+")
