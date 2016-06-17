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

LOGGER = logging.getLogger(__name__)


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
