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


# namespace
def _hash_name(name):
    return hashlib.sha512(name.encode('utf-8')).hexdigest()

FAMILY_NAME = 'xo'
XO_NAMESPACE = _hash_name(FAMILY_NAME)[:6]


def make_xo_address(name):
    return XO_NAMESPACE + _hash_name(name)


# encodings
def decode_txn_payload(payload):
    return payload.decode().split(',')


def decode_state_data(state_data):
    return state_data.decode().split(',')


def encode_state_data(board, state, player_1, player_2, name):
    return ','.join([board, state, player_1, player_2, name]).encode()


class XoTransactionHandler:
    @property
    def family_name(self):
        return FAMILY_NAME

    @property
    def family_versions(self):
        return ['1.0']

    @property
    def encodings(self):
        return ['csv-utf8']

    @property
    def namespaces(self):
        return [XO_NAMESPACE]

    def apply(self, transaction, state_store):

        # 1. Deserialize the transaction and verify it is valid
        signer, name, action, space = _unpack_transaction(transaction)

        # 2. Retrieve the game data from state storage
        board, state, player_1, player_2, stored_name = \
            _get_state_data(state_store, name)

        # NOTE: Since the game data is stored in a Merkle tree, there is a
        # small chance of collision. A more correct usage would be to store
        # a dictionary of games so that multiple games could be store at
        # the same location. See the python intkey handler for an example
        # of this.
        if stored_name and stored_name != name:
            raise InternalError('Hash collision')

        # 3. Validate the game data
        _validate_state_data(action, board, state)

        # 4. Apply the transaction
        upd_board, upd_state, upd_player_1, upd_player_2 = _play_xo(
            action, space, signer,
            board, state, player_1, player_2)

        # 5. Log for tutorial usage
        _log_turn(
            name, action, space, signer,
            upd_board, upd_state,
            upd_player_1, upd_player_2)

        # 6. Put the game data back in state storage
        _store_game_data(
            state_store, name, upd_board,
            upd_state, upd_player_1, upd_player_2)


# transactions

def _unpack_transaction(transaction):
    header = TransactionHeader()
    header.ParseFromString(transaction.header)
    signer = header.signer_pubkey

    try:
        action, name, space = decode_txn_payload(transaction.payload)
    except:
        raise InvalidTransaction('Invalid payload serialization')

    _validate_name(name)
    _validate_action_and_space(action, space)

    if action == 'take':
        space = int(space)

    return signer, name, action, space


def _validate_name(name):
    if not name:
        raise InvalidTransaction('Name is required')


def _validate_action_and_space(action, space):
    if not action:
        raise InvalidTransaction('Action is required')

    if action not in ('create', 'take'):
        raise InvalidTransaction('Invalid action')

    # if action == 'create', ignore space

    if action == 'take':
        try:
            assert int(space) in range(1, 10)
        except (ValueError, AssertionError):
            raise InvalidTransaction(
                'Space must be an integer in {}'.format(range(1, 10)))


# state

def _get_state_data(state_store, name):
    address = make_xo_address(name)

    state_entries = state_store.get([address])

    try:
        state_data = state_entries[0].data
        return decode_state_data(state_data)
    except (IndexError, ValueError):
        entry_len = 5
        return [None for _ in range(entry_len)]
    except:
        raise InternalError('Failed to deserialize game data')


def _validate_state_data(action, board, state):
    if action == 'create':
        if board is not None:
            raise InvalidTransaction(
                'Invalid action: Game already exists.')

    elif action == 'take':
        if board is None:
            raise InvalidTransaction(
                'Invalid action: Take requires an existing game.')

        if any([mark not in ('X', 'O', '-') for mark in board]):
            raise InternalError(
                'Invalid board: {}'.format(board))

        if state in ('P1-WIN', 'P2-WIN', 'TIE'):
            raise InvalidTransaction(
                'Invalid Action: Game has ended.')
        elif state not in ('P1-NEXT', 'P2-NEXT', 'P1-WIN', 'P2-WIN', 'TIE'):
            raise InternalError(
                'Game has reached an invalid state: {}'.format(state))


def _store_game_data(state_store, name, board, state, player_1, player_2):
    addresses = state_store.set([
        StateEntry(
            address=make_xo_address(name),
            data=encode_state_data(board, state, player_1, player_2, name),
        )
    ])

    if not addresses:
        raise InternalError('State error')


# game logic

def _play_xo(action, space, signer, board, state, player_1, player_2):
    if action == 'create':
        board = '---------'
        state = 'P1-NEXT'
        player_1 = ''
        player_2 = ''

        return board, state, player_1, player_2

    elif action == 'take':
        # Assign players if new game
        if player_1 == '':
            player_1 = signer

        elif player_2 == '':
            player_2 = signer

        # Verify player identity and take space
        lboard = list(board)

        if lboard[space - 1] != '-':
            raise InvalidTransaction(
                'Invalid Action: Space already taken.'
            )

        if state == 'P1-NEXT' and signer == player_1:
            lboard[space - 1] = 'X'
            state = 'P2-NEXT'

        elif state == 'P2-NEXT' and signer == player_2:
            lboard[space - 1] = 'O'
            state = 'P1-NEXT'

        else:
            raise InvalidTransaction(
                "Not this player's turn: {}".format(signer[:6])
            )
        board = ''.join(lboard)

        # Update game state
        if _is_win(board, 'X'):
            state = 'P1-WIN'
        elif _is_win(board, 'O'):
            state = 'P2-WIN'
        elif '-' not in board:
            state = 'TIE'

        return board, state, player_1, player_2


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


# display

def _log_turn(name, action, space, signer, board, state, player_1, player_2):
    if action == 'create':
        _display('Player {} created a game.'.format(signer[:6]))

    elif action == 'take':
        _display(
            'Player {} takes space: {}\n\n'.format(signer[:6], space) +
            _game_data_to_str(board, state, player_1, player_2, name)
        )


def _game_data_to_str(board, state, player_1, player_2, name):
    board = list(board.replace('-', ' '))
    out = ''
    out += 'GAME: {}\n'.format(name)
    out += 'PLAYER 1: {}\n'.format(player_1[:6])
    out += 'PLAYER 2: {}\n'.format(player_2[:6])
    out += 'STATE: {}\n'.format(state)
    out += '\n'
    out += '{} | {} | {}\n'.format(board[0], board[1], board[2])
    out += '---|---|---\n'
    out += '{} | {} | {}\n'.format(board[3], board[4], board[5])
    out += '---|---|---\n'
    out += '{} | {} | {}'.format(board[6], board[7], board[8])
    return out


def _display(msg):
    n = msg.count('\n')

    if n > 0:
        msg = msg.split('\n')
        length = max(len(line) for line in msg)
    else:
        length = len(msg)
        msg = [msg]

    LOGGER.debug('+' + (length + 2) * '-' + '+')
    for line in msg:
        LOGGER.debug('+ ' + line.center(length) + ' +')
    LOGGER.debug('+' + (length + 2) * '-' + '+')
