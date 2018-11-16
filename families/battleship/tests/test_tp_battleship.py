# Copyright 2017 Intel Corporation
# Copyright 2018 Bitwise IO, Inc.
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
from sawtooth_processor_test.transaction_processor_test_case import TransactionProcessorTestCase
from battleship_message_factory import BattleshipMessageFactory
from battleship_board import BoardLayout
from battleship_board import create_nonces
from battleship_board import ShipPosition

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


class TestBattleship(TransactionProcessorTestCase):
    """Tests the Battleship transaction processor.

    Spins up a local mock validator that the transaction processor running in another process and/or
    Docker container connects to. In this class, we send normal requests such as joining games, etc
    through `self.validator.send`, and then also manage the responses that the transaction processor
    gets for retrieving/setting state with `self.validator.respond`.

    Tests may hang for 10 minutes if something goes wrong and e.g. the validator waits and wrongly
    expects a response from the transaction processor. The hang will often occur in a different test
    method than the one that caused the issue. If that happens, you may want to add the line
    `test-method-prefix = NAME_OF_METHOD` to `nose2.cfg` to run only that failing test method.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.player_1 = BattleshipMessageFactory()
        cls.public_key_1 = cls.player_1.get_public_key()

        cls.player_2 = BattleshipMessageFactory()
        cls.public_key_2 = cls.player_2.get_public_key()

        cls.test_ships = ["AAAAA", "BBBB", "CCC", "DD", "DD", "SSS", "SSS"]
        cls.validator.register_comparator(
            Message.TP_STATE_SET_REQUEST, TestBattleship.compare_set_request
        )

        cls.layout = BoardLayout(10)
        cls.layout.append(ShipPosition(text="AA", row=0, column=0, orientation="horizontal"))

    @staticmethod
    def compare_set_request(req1, req2):
        if len(req1.entries) != len(req2.entries):
            return False

        def loads(entries):
            """Converts a list of entries of stringified JSON to sorted address -> dict pairs."""

            return sorted(
                (e.address, json.loads(e.data.decode(), encoding="utf-8")) for e in entries
            )

        return loads(req1.entries) == loads(req2.entries)

    ##################
    # Invalid Inputs #
    ##################

    def test_no_action(self):
        self.validator.send(
            self.player_1.create_tp_process_request({"Name": "noActionGame", "Action": None})
        )

        self.validator.expect(self.player_1.create_tp_response("INVALID_TRANSACTION"))

        self.validator.send(self.player_1.create_tp_process_request({"Name": "noActionGame"}))

        self.validator.expect(self.player_1.create_tp_response("INVALID_TRANSACTION"))

    def test_invalid_action(self):
        self.validator.send(
            self.player_1.create_tp_process_request(
                {"Name": "invalidAction", "Action": "MAKE_TACOS"}
            )
        )

        self.validator.expect(self.player_1.create_tp_response("INVALID_TRANSACTION"))

    def test_no_name(self):
        self.validator.send(
            self.player_1.create_tp_process_request({"Name": "", "Action": "CREATE", "Ships": []})
        )

        self.validator.expect(self.player_1.create_tp_response("INVALID_TRANSACTION"))

    def test_invalid_name(self):
        self.validator.send(
            self.player_1.create_tp_process_request(
                {"Name": "invalid-name", "Action": "CREATE", "Ships": []}
            )
        )

        self.validator.expect(self.player_1.create_tp_response("INVALID_TRANSACTION"))

    ####################
    # Create Game Tests#
    ####################

    def test_create_game_valid(self):
        game_name = "createGame"

        self.validator.send(
            self.player_1.create_tp_process_request(
                {"Name": game_name, "Action": "CREATE", "Ships": self.test_ships}
            )
        )

        self.respond_to_get_with_state(game_name, None)

        self.respond_to_set_with_state(
            game_name,
            {
                "State": "NEW",
                "Ships": ["AAAAA", "BBBB", "CCC", "DD", "DD", "SSS", "SSS"],
                "Player1": None,
                "HashedBoard1": [],
                "TargetBoard1": [],
                "Player2": None,
                "HashedBoard2": [],
                "TargetBoard2": [],
                "LastFireColumn": None,
                "LastFireRow": None,
            },
        )

        self.validator.expect(self.player_1.create_tp_response("OK"))

    def test_create_already_exists(self):
        game_name = "alreadyExists"

        self.validator.send(
            self.player_1.create_tp_process_request(
                {"Name": game_name, "Action": "CREATE", "Ships": []}
            )
        )

        self.respond_to_get_with_state(
            game_name,
            {
                "Ships": self.test_ships,
                "TargetBoard1": [],
                "TargetBoard2": [],
                "HashedBoard1": [],
                "HashedBoard2": [],
                "State": "NEW",
            },
        )

        self.validator.expect(self.player_1.create_tp_response("INVALID_TRANSACTION"))

    ###################
    # Join Game Tests #
    ###################

    def test_join_game_valid(self):
        game_name = "join_game"
        nonces = create_nonces(10)

        # Send join payload to tp
        self.validator.send(
            self.player_1.create_tp_process_request(
                {"Action": "JOIN", "Name": game_name, "Board": self.layout.render_hashed(nonces)}
            )
        )

        self.respond_to_get_with_state(
            game_name,
            {
                "HashedBoard1": [],
                "HashedBoard2": [],
                "Ships": ["AA"],
                "State": "NEW",
                "TargetBoard1": [],
                "TargetBoard2": [],
            },
        )

        self.respond_to_set_with_state(
            game_name,
            {
                "HashedBoard1": self.layout.render_hashed(nonces),
                "HashedBoard2": [],
                "LastFireColumn": None,
                "LastFireRow": None,
                "Player1": self.public_key_1,
                "Player2": None,
                "Ships": ["AA"],
                "State": "NEW",
                "TargetBoard1": [["?"] * 10 for _ in range(10)],
                "TargetBoard2": [],
            },
        )

        self.validator.expect(self.player_1.create_tp_response("OK"))

    def test_join_game_too_many_players(self):
        game_name = "full_game"
        nonces = create_nonces(10)

        self.validator.send(
            self.player_1.create_tp_process_request(
                {"Action": "JOIN", "Name": game_name, "Board": self.layout.render_hashed(nonces)}
            )
        )

        self.respond_to_get_with_state(
            game_name,
            {
                "Ships": self.test_ships,
                "TargetBoard1": [["?"] * 10 for _ in range(10)],
                "TargetBoard2": [["?"] * 10 for _ in range(10)],
                "Player1": self.public_key_1,
                "Player2": self.public_key_2,
                "HashedBoard1": self.layout.render_hashed(nonces),
                "HashedBoard2": self.layout.render_hashed(nonces),
                "State": "P1-NEXT",
            },
        )

        self.validator.expect(self.player_1.create_tp_response("INVALID_TRANSACTION"))

    def test_join_nonexistent_game(self):
        game_name = "nonexistent_game"
        nonces = create_nonces(10)

        self.validator.send(
            self.player_1.create_tp_process_request(
                {"Action": "JOIN", "Name": game_name, "Board": self.layout.render_hashed(nonces)}
            )
        )

        self.respond_to_get_with_state(game_name, None)

        self.validator.expect(self.player_1.create_tp_response("INVALID_TRANSACTION"))

    ###################
    # Fire Game Tests #
    ###################

    def test_fire_first_move(self):
        game_name = "fire_game"
        nonces = create_nonces(10)

        # Player 1 fires
        self.validator.send(
            self.player_1.create_tp_process_request(
                {"Action": "FIRE", "Name": game_name, "Row": "B", "Column": "1"}
            )
        )

        self.respond_to_get_with_state(
            game_name,
            {
                "Ships": ["AA"],
                "TargetBoard1": [["?"] * 10 for _ in range(10)],
                "TargetBoard2": [["?"] * 10 for _ in range(10)],
                "Player1": self.public_key_1,
                "Player2": self.public_key_2,
                "HashedBoard1": self.layout.render_hashed(nonces),
                "HashedBoard2": self.layout.render_hashed(nonces),
                "State": "P1-NEXT",
            },
        )

        self.respond_to_set_with_state(
            game_name,
            {
                "Ships": ["AA"],
                "TargetBoard1": [["?"] * 10 for _ in range(10)],
                "TargetBoard2": [["?"] * 10 for _ in range(10)],
                "Player1": self.public_key_1,
                "Player2": self.public_key_2,
                "HashedBoard1": self.layout.render_hashed(nonces),
                "HashedBoard2": self.layout.render_hashed(nonces),
                "LastFireRow": "B",
                "LastFireColumn": "1",
                "State": "P2-NEXT",
            },
        )

        self.validator.expect(self.player_1.create_tp_response("OK"))

    def test_fire_hit_ship(self):
        game_name = "fire_game"
        nonces = create_nonces(10)

        # Player 2 fires
        self.validator.send(
            self.player_2.create_tp_process_request(
                {
                    "Action": "FIRE",
                    "Column": "1",
                    "Name": game_name,
                    "RevealNonce": nonces[0][0],
                    "RevealSpace": "A",
                    "Row": "A",
                }
            )
        )

        self.respond_to_get_with_state(
            game_name,
            {
                "HashedBoard1": self.layout.render_hashed(nonces),
                "HashedBoard2": self.layout.render_hashed(nonces),
                "LastFireColumn": "1",
                "LastFireRow": "A",
                "Player1": self.public_key_1,
                "Player2": self.public_key_2,
                "Ships": ["AA"],
                "State": "P2-NEXT",
                "TargetBoard1": [["?"] * 10 for _ in range(10)],
                "TargetBoard2": [["?"] * 10 for _ in range(10)],
            },
        )

        target_board1 = [["?"] * 10 for _ in range(10)]
        target_board1[0][0] = "H"

        self.respond_to_set_with_state(
            game_name,
            {
                "HashedBoard1": self.layout.render_hashed(nonces),
                "HashedBoard2": self.layout.render_hashed(nonces),
                "LastFireColumn": "1",
                "LastFireRow": "A",
                "Player1": self.public_key_1,
                "Player2": self.public_key_2,
                "Ships": ["AA"],
                "State": "P1-NEXT",
                "TargetBoard1": target_board1,
                "TargetBoard2": [["?"] * 10 for _ in range(10)],
            },
            self.player_2,
        )

        self.validator.expect(self.player_1.create_tp_response("OK"))

    def test_fire_miss_ship(self):
        game_name = "fire_game"
        nonces = create_nonces(10)

        self.validator.send(
            self.player_2.create_tp_process_request(
                {
                    "Action": "FIRE",
                    "Name": "fire_game",
                    "Row": "B",
                    "Column": "1",
                    "RevealSpace": "-",
                    "RevealNonce": nonces[1][0],
                }
            )
        )

        self.respond_to_get_with_state(
            game_name,
            {
                "Ships": ["AA"],
                "TargetBoard1": [["?"] * 10 for _ in range(10)],
                "TargetBoard2": [["?"] * 10 for _ in range(10)],
                "Player1": self.public_key_1,
                "Player2": self.public_key_2,
                "HashedBoard1": self.layout.render_hashed(nonces),
                "HashedBoard2": self.layout.render_hashed(nonces),
                "State": "P2-NEXT",
                "LastFireRow": "B",
                "LastFireColumn": "1",
            },
        )

        target_board1 = [["?"] * 10 for _ in range(10)]
        target_board1[1][0] = "M"

        self.respond_to_set_with_state(
            game_name,
            {
                "Ships": ["AA"],
                "TargetBoard1": target_board1,
                "TargetBoard2": [["?"] * 10 for _ in range(10)],
                "Player1": self.public_key_1,
                "Player2": self.public_key_2,
                "HashedBoard1": self.layout.render_hashed(nonces),
                "HashedBoard2": self.layout.render_hashed(nonces),
                "LastFireRow": "B",
                "LastFireColumn": "1",
                "State": "P1-NEXT",
            },
        )

        self.validator.expect(self.player_1.create_tp_response("OK"))

    def test_fire_game_won(self):
        game_name = "fire_game"
        nonces = create_nonces(10)

        # Player 2 fires
        self.validator.send(
            self.player_2.create_tp_process_request(
                {
                    "Action": "FIRE",
                    "Name": game_name,
                    "Row": "A",
                    "Column": "2",
                    "RevealSpace": "A",
                    "RevealNonce": nonces[0][1],
                }
            )
        )

        target_board1 = [["?"] * 10 for _ in range(10)]
        target_board1[0][0] = "H"

        for _ in range(1):
            self.respond_to_get_with_state(
                game_name,
                {
                    "Ships": ["AA"],
                    "TargetBoard1": target_board1,
                    "TargetBoard2": [["?"] * 10 for _ in range(10)],
                    "Player1": self.public_key_1,
                    "Player2": self.public_key_2,
                    "HashedBoard1": self.layout.render_hashed(nonces),
                    "HashedBoard2": self.layout.render_hashed(nonces),
                    "State": "P2-NEXT",
                    "LastFireRow": "A",
                    "LastFireColumn": "2",
                },
                self.player_2,
            )

        target_board1[0][1] = "H"

        self.respond_to_set_with_state(
            game_name,
            {
                "HashedBoard1": self.layout.render_hashed(nonces),
                "HashedBoard2": self.layout.render_hashed(nonces),
                "LastFireColumn": "2",
                "LastFireRow": "A",
                "Player1": self.public_key_1,
                "Player2": self.public_key_2,
                "Ships": ["AA"],
                "State": "P2-WIN",
                "TargetBoard1": target_board1,
                "TargetBoard2": [["?"] * 10 for _ in range(10)],
            },
            self.player_2,
        )

        self.validator.expect(self.player_1.create_tp_response("OK"))

    def test_fire_nonexistent_game(self):
        game_name = "nonexistent_game"

        self.validator.send(
            self.player_1.create_tp_process_request(
                {"Action": "FIRE", "Name": game_name, "Row": "A", "Column": "1"}
            )
        )

        self.respond_to_get_with_state(game_name, None)

        self.validator.expect(self.player_1.create_tp_response("INVALID_TRANSACTION"))

    def test_fire_invalid_row(self):
        game_name = "invalid_row"

        self.validator.send(
            self.player_1.create_tp_process_request(
                {"Action": "FIRE", "Name": game_name, "Row": "A", "Column": "100"}
            )
        )

        self.respond_to_get_with_state(
            game_name,
            {
                "HashedBoard1": [],
                "HashedBoard2": [],
                "Ships": [],
                "State": "NEW",
                "TargetBoard1": [],
                "TargetBoard2": [],
            },
        )

        self.validator.expect(self.player_1.create_tp_response("INVALID_TRANSACTION"))

    def test_fire_invalid_column(self):
        game_name = "invalid_column"

        self.validator.send(
            self.player_1.create_tp_process_request(
                {"Action": "FIRE", "Name": game_name, "Row": "Z", "Column": "1"}
            )
        )

        self.respond_to_get_with_state(
            game_name,
            {
                "HashedBoard1": [],
                "HashedBoard2": [],
                "Ships": [],
                "State": "NEW",
                "TargetBoard1": [],
                "TargetBoard2": [],
            },
        )

        self.validator.expect(self.player_1.create_tp_response("INVALID_TRANSACTION"))

    def test_fire_game_over(self):
        game_name = "game_over"
        nonces = create_nonces(10)

        self.validator.send(
            self.player_1.create_tp_process_request(
                {"Action": "FIRE", "Name": game_name, "Row": "A", "Column": "1"}
            )
        )

        self.respond_to_get_with_state(
            game_name,
            {
                "Ships": ["AA"],
                "TargetBoard1": [["?"] * 10 for _ in range(10)],
                "TargetBoard2": [["?"] * 10 for _ in range(10)],
                "Player1": self.public_key_1,
                "Player2": self.public_key_2,
                "HashedBoard1": self.layout.render_hashed(nonces),
                "HashedBoard2": self.layout.render_hashed(nonces),
                "State": "P1-WIN",
            },
        )

        self.validator.expect(self.player_1.create_tp_response("INVALID_TRANSACTION"))

    def test_fire_wrong_turn(self):
        game_name = "wrong_turn"
        nonces = create_nonces(10)

        self.validator.send(
            self.player_1.create_tp_process_request(
                {"Action": "FIRE", "Name": game_name, "Row": "A", "Column": "1"}
            )
        )

        self.respond_to_get_with_state(
            game_name,
            {
                "Ships": ["AA"],
                "TargetBoard1": [["?"] * 10 for _ in range(10)],
                "TargetBoard2": [["?"] * 10 for _ in range(10)],
                "Player1": self.public_key_1,
                "Player2": self.public_key_2,
                "HashedBoard1": self.layout.render_hashed(nonces),
                "HashedBoard2": self.layout.render_hashed(nonces),
                "State": "P2-NEXT",
            },
        )

        self.validator.expect(self.player_1.create_tp_response("INVALID_TRANSACTION"))

    ##################
    # Helper methods #
    ##################

    def create_game(self, name, ships=None, player=None):
        ships = ships or self.test_ships

        player = player or self.player_1

        req_to_tp = player.create_tp_process_request(
            {"Action": "CREATE", "Name": name, "Ships": ships}
        )
        self.validator.send(req_to_tp)

    def respond_to_get_with_state(self, name, state, player=None):
        """Responds to a TpStateGetRequest with the given state."""

        player = player or self.player_1

        self.validator.respond(
            player.create_get_response(name, state),
            self.validator.expect(player.create_get_request(name)),
        )

    def respond_to_set_with_state(self, name, state, player=None):
        """Responds to a TpStateSetRequest with the given state."""

        player = player or self.player_1

        self.validator.respond(
            player.create_set_response(name),
            self.validator.expect(player.create_set_request(name, state)),
        )
