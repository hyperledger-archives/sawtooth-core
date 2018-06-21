# Copyright 2017 Intel Corporation
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
import json

from sawtooth_sdk.protobuf.validator_pb2 import Message
from sawtooth_processor_test.transaction_processor_test_case \
    import TransactionProcessorTestCase
from sawtooth_battleship_test.battleship_message_factory \
    import BattleshipMessageFactory

from sawtooth_battleship.battleship_board import BoardLayout
from sawtooth_battleship.battleship_board import create_nonces
from sawtooth_battleship.battleship_board import ShipPosition

LOGGER = logging.getLogger(__name__)


class TestBattleship(TransactionProcessorTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.player_1 = BattleshipMessageFactory()
        cls.public_key_1 = cls.player_1.get_public_key()

        cls.player_2 = BattleshipMessageFactory()
        cls.public_key_2 = cls.player_2.get_public_key()

        cls.test_ships = ["AAAAA", "BBBB", "CCC", "DD", "DD", "SSS", "SSS"]
        cls.validator.register_comparator(
            Message.TP_STATE_SET_REQUEST, compare_set_request)

    # invalid inputs

    def test_no_action(self):
        payload = {
            'Name': 'noActionGame',
            'Action': None
        }

        self.validator.send(
            self.player_1.create_tp_process_request(payload)
        )

        self.send_state_to_tp('noActionGame')

        self.expect_invalid()

    def test_invalid_action(self):
        payload = {
            'Name': 'invalidAction',
            'Action': 'MAKE_TACOS'
        }

        self.validator.send(
            self.player_1.create_tp_process_request(payload)
        )

        self.send_state_to_tp('invalidAction')

        self.expect_invalid()

    def test_no_name(self):
        payload = {
            'Name': '',
            'Action': 'CREATE'
        }

        self.validator.send(
            self.player_1.create_tp_process_request(payload)
        )

        self.send_state_to_tp('')

        self.expect_invalid()

    def test_invalid_name(self):
        payload = {
            'Name': 'invalid-name',
            'Action': 'CREATE'
        }

        self.validator.send(
            self.player_1.create_tp_process_request(payload)
        )

        self.send_state_to_tp('invalid-name')

        self.expect_invalid()

    # create

    def test_create_game_valid(self):
        self.create_game('createGame')

        self.send_state_to_tp('createGame')

        self.update_state('createGame', {
            'Ships': self.test_ships,
            'State': 'NEW'
        })

        self.expect_ok()

    def test_create_already_exists(self):
        self.create_game('alreadyExists')

        self.send_state_to_tp('alreadyExists', {
            'Ships': self.test_ships,
            'State': 'NEW'
        })

        self.expect_invalid()

    # join

    def test_join_game_valid(self):
        layout = BoardLayout.generate(self.test_ships)
        nonces = create_nonces(10)

        # Send join payload to tp

        join_req = create_join_payload('join_game', layout, nonces)
        self.validator.send(
            self.player_1.create_tp_process_request(join_req)
        )

        # give state back to tp

        self.send_state_to_tp('join_game', {
            'Ships': self.test_ships,
            'State': 'NEW'
        })

        # mock state set
        LOGGER.debug('state update')
        self.update_state('join_game', {
            'Ships': self.test_ships,
            'TargetBoard1': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'HashedBoard1': layout.render_hashed(nonces),
            'State': 'NEW'
        })

        self.expect_ok()

    def test_join_game_too_many_players(self):
        layout = BoardLayout.generate(self.test_ships)
        nonces = create_nonces(10)

        # Send join payload to tp
        join_req = create_join_payload('full_game', layout, nonces)
        self.validator.send(
            self.player_1.create_tp_process_request(join_req)
        )

        # give state back to tp

        self.send_state_to_tp('full_game', {
            'Ships': self.test_ships,
            'TargetBoard1': [['?'] * 10 for _ in range(10)],
            'TargetBoard2': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'Player2': self.public_key_2,
            'HashedBoard1': layout.render_hashed(nonces),
            'HashedBoard2': layout.render_hashed(nonces),
            'State': 'P1-NEXT'
        })

        self.expect_invalid()

    def test_join_nonexistent_game(self):
        layout = BoardLayout.generate(self.test_ships)
        nonces = create_nonces(10)

        # Send join payload to tp
        join_req = create_join_payload('nonexistent_game', layout, nonces)
        self.validator.send(
            self.player_1.create_tp_process_request(join_req)
        )

        # give state back to tp

        self.send_state_to_tp('nonexistent_game')

        self.expect_invalid()

    # fire

    def test_fire_first_move(self):
        # Create test board
        layout = BoardLayout(10)
        layout.append(
            ShipPosition(text='AA', row=0, column=0, orientation='horizontal'))
        nonces = create_nonces(10)

        # Player 1 fires
        fire_req = create_fire_payload('fire_game', '1', 'B')

        self.validator.send(
            self.player_1.create_tp_process_request(fire_req))

        self.send_state_to_tp('fire_game', {
            'Ships': ['AA'],
            'TargetBoard1': [['?'] * 10 for _ in range(10)],
            'TargetBoard2': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'Player2': self.public_key_2,
            'HashedBoard1': layout.render_hashed(nonces),
            'HashedBoard2': layout.render_hashed(nonces),
            'State': 'P1-NEXT'
        })

        self.update_state('fire_game', {
            'Ships': ['AA'],
            'TargetBoard1': [['?'] * 10 for _ in range(10)],
            'TargetBoard2': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'Player2': self.public_key_2,
            'HashedBoard1': layout.render_hashed(nonces),
            'HashedBoard2': layout.render_hashed(nonces),
            'LastFireRow': '1',
            'LastFireColumn': 'B',
            'State': 'P2-NEXT'
        })

        self.expect_ok()

    def test_fire_hit_ship(self):
        # Create test board
        layout = BoardLayout(10)
        layout.append(
            ShipPosition(text='AA', row=0, column=0, orientation='horizontal'))
        nonces = create_nonces(10)

        # Player 2 fires
        fire_req = \
            create_fire_payload('fire_game', '1', 'A', 'A', nonces[0][0])

        self.validator.send(
            self.player_2.create_tp_process_request(fire_req))

        self.send_state_to_tp('fire_game', {
            'Ships': ['AA'],
            'TargetBoard1': [['?'] * 10 for _ in range(10)],
            'TargetBoard2': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'Player2': self.public_key_2,
            'HashedBoard1': layout.render_hashed(nonces),
            'HashedBoard2': layout.render_hashed(nonces),
            'State': 'P2-NEXT',
            'LastFireRow': '1',
            'LastFireColumn': 'A'
        }, self.player_2)

        target_board1 = [['?'] * 10 for _ in range(10)]
        target_board1[0][0] = 'H'

        self.update_state('fire_game', {
            'Ships': ['AA'],
            'TargetBoard1': target_board1,
            'TargetBoard2': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'Player2': self.public_key_2,
            'HashedBoard1': layout.render_hashed(nonces),
            'HashedBoard2': layout.render_hashed(nonces),
            'LastFireRow': '1',
            'LastFireColumn': 'A',
            'State': 'P1-NEXT'
        }, self.player_2)

        self.expect_ok()

    def test_fire_miss_ship(self):
        # Create test board
        layout = BoardLayout(10)
        layout.append(
            ShipPosition(text='AA', row=0, column=0, orientation='horizontal'))
        nonces = create_nonces(10)

        # Player 2 fires
        fire_req = \
            create_fire_payload('fire_game', '2', 'A', '-', nonces[1][0])

        self.validator.send(
            self.player_2.create_tp_process_request(fire_req))

        self.send_state_to_tp('fire_game', {
            'Ships': ['AA'],
            'TargetBoard1': [['?'] * 10 for _ in range(10)],
            'TargetBoard2': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'Player2': self.public_key_2,
            'HashedBoard1': layout.render_hashed(nonces),
            'HashedBoard2': layout.render_hashed(nonces),
            'State': 'P2-NEXT',
            'LastFireRow': '2',
            'LastFireColumn': 'A'
        }, self.player_2)

        target_board1 = [['?'] * 10 for _ in range(10)]
        target_board1[1][0] = 'M'

        self.update_state('fire_game', {
            'Ships': ['AA'],
            'TargetBoard1': target_board1,
            'TargetBoard2': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'Player2': self.public_key_2,
            'HashedBoard1': layout.render_hashed(nonces),
            'HashedBoard2': layout.render_hashed(nonces),
            'LastFireRow': '2',
            'LastFireColumn': 'A',
            'State': 'P1-NEXT'
        }, self.player_2)

        self.expect_ok()

    def test_fire_game_won(self):
        # Create test board
        layout = BoardLayout(10)
        layout.append(
            ShipPosition(text='AA', row=0, column=0, orientation='horizontal'))
        nonces = create_nonces(10)

        # Player 2 fires
        fire_req = \
            create_fire_payload('fire_game', '1', 'B', 'A', nonces[0][1])

        self.validator.send(
            self.player_2.create_tp_process_request(fire_req))

        target_board1 = [['?'] * 10 for _ in range(10)]
        target_board1[0][0] = 'H'

        self.send_state_to_tp('fire_game', {
            'Ships': ['AA'],
            'TargetBoard1': target_board1,
            'TargetBoard2': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'Player2': self.public_key_2,
            'HashedBoard1': layout.render_hashed(nonces),
            'HashedBoard2': layout.render_hashed(nonces),
            'State': 'P2-NEXT',
            'LastFireRow': '1',
            'LastFireColumn': 'B'
        }, self.player_2)

        target_board1[0][1] = 'H'

        self.update_state('fire_game', {
            'Ships': ['AA'],
            'TargetBoard1': target_board1,
            'TargetBoard2': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'Player2': self.public_key_2,
            'HashedBoard1': layout.render_hashed(nonces),
            'HashedBoard2': layout.render_hashed(nonces),
            'LastFireRow': '1',
            'LastFireColumn': 'B',
            'State': 'P1-WIN'
        }, self.player_2)

        self.expect_ok()

    def test_fire_nonexistent_game(self):
        # Send join payload to tp

        fire_req = create_fire_payload('nonexistent_game', '1', 'A')

        self.validator.send(
            self.player_1.create_tp_process_request(fire_req)
        )

        # give state back to tp

        self.send_state_to_tp('nonexistent_game')

        self.expect_invalid()

    def test_fire_invalid_row(self):
        layout = BoardLayout(10)
        layout.append(
            ShipPosition(text='AA', row=0, column=0, orientation='horizontal'))
        nonces = create_nonces(10)

        # Send join payload to tp

        fire_req = create_fire_payload('invalid_row', '100', 'A')

        self.validator.send(
            self.player_1.create_tp_process_request(fire_req)
        )

        # give state back to tp

        self.send_state_to_tp('invalid_row', {
            'Ships': ['AA'],
            'TargetBoard1': [['?'] * 10 for _ in range(10)],
            'TargetBoard2': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'Player2': self.public_key_2,
            'HashedBoard1': layout.render_hashed(nonces),
            'HashedBoard2': layout.render_hashed(nonces),
            'State': 'P1-NEXT'
        })

        self.expect_invalid()

    def test_fire_invalid_column(self):
        layout = BoardLayout(10)
        layout.append(
            ShipPosition(text='AA', row=0, column=0, orientation='horizontal'))
        nonces = create_nonces(10)

        # Send join payload to tp
        fire_req = create_fire_payload('invalid_row', '1', 'Z')

        self.validator.send(
            self.player_1.create_tp_process_request(fire_req)
        )

        # give state back to tp

        self.send_state_to_tp('invalid_row', {
            'Ships': ['AA'],
            'TargetBoard1': [['?'] * 10 for _ in range(10)],
            'TargetBoard2': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'Player2': self.public_key_2,
            'HashedBoard1': layout.render_hashed(nonces),
            'HashedBoard2': layout.render_hashed(nonces),
            'State': 'P1-NEXT'
        })

        self.expect_invalid()

    def test_fire_game_over(self):
        layout = BoardLayout(10)
        layout.append(
            ShipPosition(text='AA', row=0, column=0, orientation='horizontal'))
        nonces = create_nonces(10)

        # Send join payload to tp
        fire_req = create_fire_payload('invalid_row', '1', 'A')

        self.validator.send(
            self.player_1.create_tp_process_request(fire_req)
        )

        # give state back to tp

        self.send_state_to_tp('invalid_row', {
            'Ships': ['AA'],
            'TargetBoard1': [['?'] * 10 for _ in range(10)],
            'TargetBoard2': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'Player2': self.public_key_2,
            'HashedBoard1': layout.render_hashed(nonces),
            'HashedBoard2': layout.render_hashed(nonces),
            'State': 'P1-WIN'
        })

        self.expect_invalid()

    def test_fire_wrong_turn(self):
        layout = BoardLayout(10)
        layout.append(
            ShipPosition(text='AA', row=0, column=0, orientation='horizontal'))
        nonces = create_nonces(10)

        # Send join payload to tp
        fire_req = create_fire_payload('invalid_row', '1', 'Z')

        self.validator.send(
            self.player_1.create_tp_process_request(fire_req)
        )

        # give state back to tp

        self.send_state_to_tp('invalid_row', {
            'Ships': ['AA'],
            'TargetBoard1': [['?'] * 10 for _ in range(10)],
            'TargetBoard2': [['?'] * 10 for _ in range(10)],
            'Player1': self.public_key_1,
            'Player2': self.public_key_2,
            'HashedBoard1': layout.render_hashed(nonces),
            'HashedBoard2': layout.render_hashed(nonces),
            'State': 'P2-NEXT'
        })

        self.expect_invalid()

    # Helper methods

    def create_game(self, name, ships=None, player=None):
        ships = ships if ships else self.test_ships

        player = player if player else self.player_1

        req_to_tp = player.create_tp_process_request({
            'Action': 'CREATE',
            'Name': name,
            'Ships': ships
        })
        self.validator.send(req_to_tp)

    def send_state_to_tp(self, name, state=None, player=None):
        state = state if state else {}
        player = player if player else self.player_1

        get_req_from_tp = self.validator.expect(
            player.create_get_request(name))
        get_res_from_validator = player.create_get_response(name, state)
        self.validator.respond(get_res_from_validator, get_req_from_tp)

    def update_state(self, name, state=None, player=None):
        state = state if state else {}
        player = player if player else self.player_1
        LOGGER.debug('expecing set')
        set_req_from_tp = self.validator.expect(
            player.create_set_request(name, state))
        self.validator.respond(
            player.create_set_response(name), set_req_from_tp)

    def expect_ok(self):
        self.expect_tp_response('OK')

    def expect_invalid(self):
        self.expect_tp_response('INVALID_TRANSACTION')

    def expect_tp_response(self, response):
        self.validator.expect(
            self.player_1.create_tp_response(
                response))


def compare_set_request(req1, req2):
    if len(req1.entries) != len(req2.entries):
        return False

    entries1 = sorted(
        [(e.address, json.loads(e.data.decode(), encoding="utf-8"))
            for e in req1.entries])
    entries2 = sorted(
        [(e.address, json.loads(e.data.decode(), encoding="utf-8"))
            for e in req2.entries])
    if entries1 != entries2:
        return False

    return True


def create_join_payload(name, board_layout, nonces):
    return {
        'Action': 'JOIN',
        'Name': name,
        'Board': board_layout.render_hashed(nonces)
    }


def create_fire_payload(
        name,
        row,
        column,
        reveal_space=None,
        reveal_nonce=None):
    return {
        'Action': 'FIRE',
        'Name': name,
        'Row': row,
        'Column': column,
        'RevealSpace': reveal_space,
        'RevealNonce': reveal_nonce
    }
