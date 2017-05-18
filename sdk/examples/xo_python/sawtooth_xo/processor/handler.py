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

import json
import hashlib
import logging

from sawtooth_sdk.processor.state import StateEntry
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader


LOGGER = logging.getLogger(__name__)


# namespace
def hash_name(name):
    return hashlib.sha512(name.encode('utf-8')).hexdigest()

FAMILY_NAME = 'xo'
XO_NAMESPACE = hash_name(FAMILY_NAME)[:6]


def make_xo_address(name):
    return XO_NAMESPACE + hash_name(name)[-64:]


# encodings
def decode_txn_payload(payload):
    return payload.decode().split(',')


def decode_state_data(state_data_bytes, name):
    state_data_dict = json.loads(state_data_bytes.decode())
    return state_data_dict[name].split(',') + [state_data_dict]


def encode_state_data(state_data_dict, name,
                      board, state, player_1, player_2):
    state_data_dict[name] = ','.join([board, state, player_1, player_2])
    return json.dumps(state_data_dict).encode()

# board
SIDE_LENGTH = 3
SPACE_COUNT = SIDE_LENGTH ** 2
VALID_SPACES = range(1, SPACE_COUNT + 1)
VALID_MARKS = MARK_1, MARK_2, EMPTY_SPACE = 'X', 'O', '-'
EMPTY_BOARD = EMPTY_SPACE * SPACE_COUNT

# actions
VALID_ACTIONS = CREATE, TAKE = 'create', 'take'

# states
VALID_STATES = P1_NEXT, P2_NEXT, P1_WIN, P2_WIN, TIE = \
    'P1-NEXT', 'P2-NEXT', 'P1-WIN', 'P2-WIN', 'TIE'
END_STATES = 'P1-WIN', 'P2-WIN', 'TIE'


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
        signer, name, action, space = _unpack_transaction(transaction)

        board, state, player_1, player_2, state_data = _get_state_data(
            name, state_store)

        _validate_data(action, board, state)

        upd_board, upd_state, upd_player_1, upd_player_2 = _play_xo(
            action, space, signer,
            board, state, player_1, player_2)

        _log_turn(
            name, action, space, signer,
            upd_board, upd_state,
            upd_player_1, upd_player_2)

        _store_game_data(
            state_store, state_data,
            name, upd_board, upd_state,
            upd_player_1, upd_player_2)


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

    space = space if space == '' else int(space)

    return signer, name, action, space


def _validate_name(name):
    if not name:
        raise InvalidTransaction('Name is required')


def _validate_action_and_space(action, space):
    if not action:
        raise InvalidTransaction('Action is required')

    if action not in VALID_ACTIONS:
        raise InvalidTransaction('Invalid action')

    # if action == CREATE, should space be ignored? required to be ''?

    if action == TAKE:
        try:
            assert int(space) in VALID_SPACES
        except (ValueError, AssertionError):
            raise InvalidTransaction(
                'Space must be an integer in {}'.format(VALID_SPACES))


# state

def _get_state_data(name, state_store):
    '''
    Return: board, state, player_1, player_2, state_data_dict
    '''
    state_entries = state_store.get([make_xo_address(name)])

    try:
        state_data = state_entries[0].data
        return decode_state_data(state_data, name)

    except IndexError:
        return None, None, None, None, {}
    except:
        raise InternalError('Failed to deserialize game data.')


def _validate_data(action, board, state):
    if action == CREATE:
        if board is not None:
            raise InvalidTransaction(
                'Invalid action: Game already exists.')

    elif action == TAKE:
        if board is None:
            raise InvalidTransaction(
                'Invalid action: Take requires an existing game.')

        elif any([mark not in VALID_MARKS for mark in board]):
            raise InternalError(
                'Invalid board: {}'.format(board))

        else:
            if state in END_STATES:
                raise InvalidTransaction(
                    'Invalid Action: Game has ended.')
            elif state not in VALID_STATES:
                raise InternalError(
                    'Game has reached an invalid state: {}'.format(state))


def _store_game_data(state_store, state_data,
                     name, board, state,
                     player_1, player_2):

    upd_state_data = encode_state_data(
        state_data, name, board, state, player_1, player_2)

    addresses = state_store.set([
        StateEntry(
            address=make_xo_address(name),
            data=upd_state_data)
    ])

    if not addresses:
        raise InternalError('State Error')


# game logic

def _play_xo(action, space, signer, board, state, player_1, player_2):
    '''
    Return: upd_board, upd_state, upd_player_1, upd_player_2
    '''
    if action == CREATE:
        return EMPTY_BOARD, P1_NEXT, '', ''

    elif action == TAKE:
        # Assign players if new game
        upd_player_1, upd_player_2 = _update_players(
            player_1, player_2, signer)

        # Verify player identity and take space
        mark = _check_turn_and_get_mark(
            state, signer, upd_player_1, upd_player_2)

        upd_board = _update_board(board, space, mark)

        upd_state = _update_state(state, upd_board)

        return upd_board, upd_state, upd_player_1, upd_player_2

    else:
        raise InternalError('Unhandled action: {}'.format(action))


def _update_state(state, board):
    x_wins = _is_win(board, MARK_1)
    o_wins = _is_win(board, MARK_2)

    if x_wins and o_wins:
        raise InternalError(
            'Two winners (there can be only one)')

    elif x_wins:
        return P1_WIN

    elif o_wins:
        return P2_WIN

    elif EMPTY_SPACE not in board:
        return TIE

    elif state == P1_NEXT:
        return P2_NEXT

    elif state == P2_NEXT:
        return P1_NEXT

    elif state in END_STATES:
        return state

    else:
        raise InternalError(
            'Unhandled state: {}'.format(state))


def _update_players(player_1, player_2, signer):
    '''
    Return: upd_player_1, upd_player_2
    '''
    if player_1 == '':
        return signer, player_2

    elif player_2 == '':
        return player_1, signer

    else:
        return player_1, player_2


def _update_board(board, space, mark):
    index = space - 1

    if board[index] != EMPTY_SPACE:
        raise InvalidTransaction(
            'Invalid Action: space {} already taken'.format(space))

    return ''.join([curr if sqr != index else mark
                    for sqr, curr in enumerate(board)])


def _check_turn_and_get_mark(state, signer, player_1, player_2):
    '''
    Return: MARK_1 or MARK_2
    '''
    if state == P1_NEXT and signer == player_1:
        return MARK_1
    elif state == P2_NEXT and signer == player_2:
        return MARK_2
    else:
        raise InvalidTransaction(
            "Not this player's turn: {}".format(signer[:6]))


def _get_rows(board):
    return [
        board[i:i + SIDE_LENGTH]
        for i in range(0, SPACE_COUNT, SIDE_LENGTH)
    ]


def _get_columns(board_rows):
    return [
        ''.join([row[i] for row in board_rows])
        for i in range(SIDE_LENGTH)
    ]


def _get_diagonals(board_rows):
    diag_left_above = ''.join([
        board_rows[i][i]
        for i in range(SIDE_LENGTH)
    ])

    diag_right_above = ''.join([
        board_rows[SIDE_LENGTH - i - 1][i]
        for i in range(SIDE_LENGTH)
    ])

    return diag_left_above, diag_right_above


def _split_up_board(board):
    rows = _get_rows(board)
    columns = _get_columns(rows)
    diagonals = _get_diagonals(rows)

    return rows, columns, diagonals


def _is_win(board, mark):
    '''
    This might seem baroque, but that's just a consequence of generality.
    All this function does is calculate the rows, columns, and diagonals of
    the board and return whether any of them consist only of the mark.

    (It would be more efficient split up the board once and then check for
    both marks, returning the winning mark or None, but then the caller
    would have to parse the output. It would also make it more complicated
    to deal with the deviant case in which both sides have a win.)
    '''
    return any([
        any([
            all([
                char == mark
                for char in seq
            ])
            for seq in direction
        ])
        for direction in _split_up_board(board)
    ])


# logging

def _log_turn(name, action, space, signer, board, state, player_1, player_2):
    if action == CREATE:
        _display('Player {} created a game.'.format(signer[:6]))

    elif action == TAKE:
        _display(
            'Player {} takes space: {}\n\n'.format(signer[:6], space) +
            _game_data_to_str(board, state, player_1, player_2, name))


def _game_data_to_str(board, state, player_1, player_2, name):
    rows = _get_rows(board.replace('-', ' '))

    game_info = '\n'.join([
        'GAME: {}'.format(name),
        'PLAYER 1: {}'.format(player_1[:6]),
        'PLAYER 2: {}'.format(player_2[:6]),
        'STATE: {}'.format(state),
    ])

    divider = '\n' + '|'.join(['---' for _ in range(SIDE_LENGTH)]) + '\n'

    format_board = divider.join([' | '.join(row) for row in rows])

    return '\n'.join([
        game_info,
        format_board,
    ])


def _display(msg):
    count = msg.count('\n')

    if count > 0:
        msg = msg.split('\n')
        length = max(len(line) for line in msg)
    else:
        length = len(msg)
        msg = [msg]

    LOGGER.info('+' + (length + 2) * '-' + '+')
    for line in msg:
        LOGGER.info('+ ' + line.center(length) + ' +')
    LOGGER.info('+' + (length + 2) * '-' + '+')
