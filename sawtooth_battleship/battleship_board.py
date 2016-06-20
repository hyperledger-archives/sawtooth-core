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
import random
import string
import hashlib

from enum import Enum

from battleship_exceptions import BoardLayoutException


LOGGER = logging.getLogger(__name__)


class ShipOrientation(Enum):
    horizontal = 1
    vertical = 2


class BoardLayout(object):
    def __init__(self, size):
        self.ship_positions = []
        self.size = size

    def append(self, ship_position):
        """Attempts to append the ship at the specified position.

        Attributes:
            ship_position (ShipPosition): The ship to append to the layout.

        Raises:
            BoardLayoutException: If the position is already occupied or is
                otherwise invalid.
        """

        self.ship_positions.append(ship_position)

        # Check validity by rendering the board into a string
        try:
            self.render()
        except BoardLayoutException, e:
            self.ship_positions = self.ship_positions[:-1]
            raise e

    def render(self):
        """Returns a game board layout as a list of strings.

        Raises:
            BoardLayoutException: If the position is already occupied or is
                otherwise invalid.
        """

        board = [['-'] * self.size for i in range(self.size)]

        for position in self.ship_positions:
            orientation = position.orientation
            row = position.row
            col = position.column
            text = position.text

            if orientation == ShipOrientation.horizontal:
                for i in xrange(0, len(text)):
                    if board[row][col + i] != '-':
                        raise BoardLayoutException(
                            "can not place ship at {}{}, space "
                            "is occupied with {}".format(
                                'ABCDEFGHIJ'[col],
                                row,
                                board[row][col]))
                    board[row][col + i] = text[i]
            elif orientation == ShipOrientation.vertical:
                for i in xrange(0, len(text)):
                    if board[row + i][col] != '-':
                        raise BoardLayoutException(
                            "can not place ship at {}{}, space "
                            "is occupied with {}".format(
                                'ABCDEFGHIJ'[col],
                                row,
                                board[row][col]))
                    board[row + i][col] = text[i]
            else:
                assert False, "invalid orientation: {}".format(orientation)

        return board

    @staticmethod
    def generate(size=10, ships=None, max_placement_attempts=100):
        if ships is None:
            ships = ["AAAAA", "BBBB", "CCC", "DD", "DD", "SSS", "SSS"]

        remaining = list(ships)
        layout = BoardLayout(size)

        while len(remaining) > 0:
            ship = remaining[0]
            remaining.remove(ship)

            success = False
            attempts = 0
            while not success:
                attempts += 1

                orientation = random.choice(
                    [ShipOrientation.horizontal,
                     ShipOrientation.vertical])
                if orientation == ShipOrientation.horizontal:
                    row = random.randrange(0, size)
                    col = random.randrange(0, size - len(ship) + 1)
                else:
                    row = random.randrange(0, size - len(ship) + 1)
                    col = random.randrange(0, size)

                position = ShipPosition(
                    text=ship, row=row, column=col, orientation=orientation)

                try:
                    layout.append(position)
                    success = True
                except BoardLayoutException, e:
                    if attempts > max_placement_attempts:
                        LOGGER.debug("exceeded attempts, resetting...")
                        layout = BoardLayout(size)
                        remaining = list(ships)
                        break

        return layout


class ShipPosition(object):
    """Represents a ship and it's placement on the board.

    Attributes:
        text (str): Ship's textual representation (example: AAAAA, BBBB)
        row (int): First row on which the ship appears (starts at 0)
        column (int): First column on which the ship appears (starts at 0)
        orientation (ShipOrientation): Whether placed horizontal or vertical
    """
    def __init__(self, text, row, column, orientation):
        self.text = text
        self.row = row
        self.column = column
        self.orientation = orientation


class Board:
    """The Board object manages local state for each game board instance.
    Calling create_game() will return an encrypted board to send to the server

    Attributes:
        secret_board (str): Board with ship positions in the clear
        secret_board_keys (str): Keys for each board space
        board_commitment (str): Commitment to the keys that unlock the board
    """
    # TODO: figure out how to send in a pre-defined board
    # TODO: figure out which class is responsible for persisting board and keys
    # TODO: figure out call pattern with client for accessing this state
    # TODO: txn_family should take advantage of these decrypt method(s)
    # TODO: enhance the 'encryption' method

    def __init__(self):
        """
        Constructor for the battleship Game class
        """
        self.secret_board = ''
        self.secret_board_keys = ''
        self.board_commitment = ''

    def create_game(self):
        self.secret_board = self.create_secret_board()
        self.secret_board_keys = self.create_board_keys(self.secret_board)
        self.board_commitment = hashlib.sha1(self.secret_board_keys)\
            .hexdigest()
        return self.encrypt_board(self.secret_board, self.secret_board_keys)

    def create_secret_board(self):
        """
        Create board with ship positions
        """
        # TODO: Generate a board automatically or parametrically
        # Hard coding for test purposes
        sb = ''
        sb += '-----'
        sb += 'AAAA-'
        sb += '--BBB'
        sb += 'S----'
        sb += 'CCC--'
        return sb

    def create_board_keys(self, board):
        return ''.join(random.choice(string.ascii_uppercase)
                       for _ in range(len(board)))

    def encrypt_space(self, space, secret_key):
        return chr(ord(space) + ord(secret_key))

    def decrypt_space(self, space, secret_key):
        return chr(ord(space) - ord(secret_key))

    def encrypt_board(self, board, board_keys):
        encboard = ''
        for i in range(len(board)):
            encspace = self.encrypt_space(board[i], (board_keys[i]))
            encboard += encspace
        return encboard

    def decrypt_board(self, board, board_keys):
        decboard = ''
        for i in range(len(board)):
            decspace = self.decrypt_space(board[i], (board_keys[i]))
            decboard += decspace
        return decboard
