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

from sawtooth_processor_test.transaction_processor_test_case \
    import TransactionProcessorTestCase
from sawtooth_xo.xo_message_factory import XoMessageFactory


LOGGER = logging.getLogger(__name__)


class TestXo(TransactionProcessorTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.player_1 = XoMessageFactory()
        cls.public_key_1 = cls.player_1.get_public_key()

        cls.player_2 = XoMessageFactory()
        cls.public_key_2 = cls.player_2.get_public_key()

    # invalid inputs

    def test_no_action(self):
        self.send_transaction('', 'no-action', 9)

        self.expect_invalid()

    def test_invalid_action(self):
        self.send_transaction('blorp', 'invalid-action', 8)

        self.expect_invalid()

    def test_no_name(self):
        self.send_transaction('take', '', 4)

        self.expect_invalid()

    def test_bar_name(self):
        self.create_game('bar|name')

        self.expect_invalid()

    # create

    def test_create_game_valid(self):
        self.create_game('create-game')

        self.send_get_response(
            game='create-game',
            board=None,
            state=None,
            player_1=None,
            player_2=None)

        self.expect_set_request(
            game='create-game',
            board='---------',
            state='P1-NEXT',
            player_1='',
            player_2='')

    def test_create_already_created(self):
        self.create_game('already-created')

        self.send_get_response(
            game='already-created',
            board='---------')

        self.expect_invalid()

    # take

    def test_take_space(self):
        # player 1 takes a space
        self.take_space('take-space', 3, signer=1)

        self.send_get_response(
            game='take-space',
            board='---------',
            state='P1-NEXT',
            player_1='',
            player_2='')

        self.expect_set_request(
            game='take-space',
            board='--X------',
            state='P2-NEXT',
            player_1=self.public_key_1,
            player_2='')

        # player 2 takes a space
        self.take_space('take-space', 7, signer=2)

        self.send_get_response(
            game='take-space',
            board='--X------',
            state='P2-NEXT',
            player_1=self.public_key_1,
            player_2='')

        self.expect_set_request(
            game='take-space',
            board='--X---O--',
            state='P1-NEXT',
            player_1=self.public_key_1,
            player_2=self.public_key_2)

        # player 1 goes again
        self.take_space('take-space', 9, signer=1)

        self.send_get_response(
            game='take-space',
            board='--X---O--',
            state='P1-NEXT',
            player_1=self.public_key_1,
            player_2=self.public_key_2)

        self.expect_set_request(
            game='take-space',
            board='--X---O-X',
            state='P2-NEXT',
            player_1=self.public_key_1,
            player_2=self.public_key_2)

        # player 2 goes again
        self.take_space('take-space', 1, signer=2)

        self.send_get_response(
            game='take-space',
            board='--X---O-X',
            state='P2-NEXT',
            player_1=self.public_key_1,
            player_2=self.public_key_2)

        self.expect_set_request(
            game='take-space',
            board='O-X---O-X',
            state='P1-NEXT',
            player_1=self.public_key_1,
            player_2=self.public_key_2)

    def test_take_win(self):
        moves_1 = (
            (3, 'XX-----OO', 'XXX----OO'), (5, 'O--X-X--O', 'O--XXX--O'),
            (7, 'OO-----XX', 'OO----XXX'), (1, '-O-XO-X--', 'XO-XO-X--'),
            (5, 'OX----OX-', 'OX--X-OX-'), (9, '-OX-OX---', '-OX-OX--X'),
            (5, 'X-O---O-X', 'X-O-X-O-X'), (5, 'O-X---X-O', 'O-X-X-X-O'),
        )

        moves_2 = (
            (2, 'O-O-X-X-X', 'OOO-X-X-X'), (4, 'OX---XO-X', 'OX-O-XO-X'),
            (6, 'XX-OO---X', 'XX-OOO--X'), (8, 'XO-XO---X', 'XO-XO--OX'),
        )

        for signer in (1, 2):
            moves = moves_1 if signer == 1 else moves_2
            for space, board, winner in moves:
                self.take_space('win', space, signer=signer)

                self.send_get_response(
                    game='win',
                    board=board,
                    state=('P1-NEXT' if signer == 1 else 'P2-NEXT'),
                    player_1=self.public_key_1,
                    player_2=self.public_key_2)

                self.expect_set_request(
                    game='win',
                    board=winner,
                    state=('P1-WIN' if signer == 1 else 'P2-WIN'),
                    player_1=self.public_key_1,
                    player_2=self.public_key_2)

    def test_take_tie(self):
        self.take_space('tie', 8, signer=1)

        self.send_get_response(
            game='tie',
            board='XOXOOXX-O',
            state='P1-NEXT',
            player_1=self.public_key_1,
            player_2=self.public_key_2)

        self.expect_set_request(
            game='tie',
            board='XOXOOXXXO',
            state='TIE',
            player_1=self.public_key_1,
            player_2=self.public_key_2)

    def test_take_space_already_taken(self):
        self.take_space('already-taken', 4)

        self.send_get_response(
            game='already-taken',
            board='---X-----')

        self.expect_invalid()

    def test_take_wrong_turn(self):
        '''
        If the signer's public key matches player_1 and
        the state is P2-NEXT, the transaction is invalid,
        and vice versa.
        '''

        # player 2 going on player 1's turn
        self.take_space('wrong-turn-1', 4, signer=2)

        self.send_get_response(
            game='wrong-turn-1',
            board='--X---O--',
            state='P1-NEXT',
            player_1=self.public_key_1,
            player_2=self.public_key_2)

        self.expect_invalid()

        # player 1 going on player 2's turn
        self.take_space('wrong-turn-2', 4, signer=1)

        self.send_get_response(
            game='wrong-turn-2',
            board='--X---O--',
            state='P2-NEXT',
            player_1=self.public_key_1,
            player_2=self.public_key_2)

        self.expect_invalid()

    def test_take_game_ended(self):
        for state in 'P1-WIN', 'P2-WIN', 'TIE':
            self.take_space('game-ended', 9, signer=1)

            self.send_get_response(
                game='game-ended',
                board='XXXOO----',
                state=state)

            self.expect_invalid()

    # message functions (gamed from the perspective of the validator)

    def create_game(self, game, signer=1):
        self.send_transaction('create', game, signer=signer)

    def take_space(self, game, space, signer=1):
        self.send_transaction('take', game, space, signer=signer)

    def send_transaction(self, action, game, space='', signer=1):
        factory = self.player_1 if signer == 1 else self.player_2

        self.validator.send(
            factory.create_tp_process_request(
                action, game, space))

    def try_transaction_with_all_actions(self, game, space=''):
        for action in ('create', 'take'):
            self.send_transaction(action, game, space)

            self.expect_invalid()

    # low-level message functions

    def send_get_response(self, game, board,
                          state='P1-NEXT',
                          player_1='', player_2=''):

        received = self.validator.expect(
            self.player_1.create_get_request(
                game))

        self.validator.respond(
            self.player_1.create_get_response(
                game, board, state, player_1, player_2),
            received)

    def expect_set_request(self, game,
                           board='---------',
                           state='P1-NEXT',
                           player_1='',
                           player_2=''):

        received = self.validator.expect(
            self.player_1.create_set_request(
                game, board, state, player_1, player_2))

        self.validator.respond(
            self.player_1.create_set_response(
                game),
            received)

        self.expect_ok()

    def expect_ok(self):
        self.expect_tp_response('OK')

    def expect_invalid(self):
        self.expect_tp_response('INVALID_TRANSACTION')

    def expect_tp_response(self, response):
        self.validator.expect(
            self.player_1.create_tp_response(
                response))
