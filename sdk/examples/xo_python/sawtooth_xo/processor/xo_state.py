# Copyright 2018 Intel Corporation
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
# -----------------------------------------------------------------------------

import hashlib

from sawtooth_sdk.processor.exceptions import InternalError


XO_NAMESPACE = hashlib.sha512('xo'.encode("utf-8")).hexdigest()[0:6]


def _make_xo_address(name):
    return XO_NAMESPACE + \
        hashlib.sha512(name.encode('utf-8')).hexdigest()[:64]


class Game:
    def __init__(self, name, board, state, player1, player2):
        self.name = name
        self.board = board
        self.state = state
        self.player1 = player1
        self.player2 = player2


class XoState:

    TIMEOUT = 3

    def __init__(self, context):
        """Constructor.

        Args:
            context (sawtooth_sdk.processor.context.Context): Access to
                validator state from within the transaction processor.
        """

        self._context = context
        self._address_cache = {}

    def delete_game(self, game_name):
        """Delete the Game named game_name from state.

        Args:
            game_name (str): The name.

        Raises:
            KeyError: The Game with game_name does not exist.
        """

        games = self._load_games(game_name=game_name)

        del games[game_name]
        if games:
            self._store_game(game_name, games=games)
        else:
            self._delete_game(game_name)

    def set_game(self, game_name, game):
        """Store the game in the validator state.

        Args:
            game_name (str): The name.
            game (Game): The information specifying the current game.
        """

        games = self._load_games(game_name=game_name)

        games[game_name] = game

        self._store_game(game_name, games=games)

    def get_game(self, game_name):
        """Get the game associated with game_name.

        Args:
            game_name (str): The name.

        Returns:
            (Game): All the information specifying a game.
        """

        return self._load_games(game_name=game_name).get(game_name)

    def _store_game(self, game_name, games):
        address = _make_xo_address(game_name)

        state_data = self._serialize(games)

        self._address_cache[address] = state_data

        self._context.set_state(
            {address: state_data},
            timeout=self.TIMEOUT)

    def _delete_game(self, game_name):
        address = _make_xo_address(game_name)

        self._context.delete_state(
            [address],
            timeout=self.TIMEOUT)

        self._address_cache[address] = None

    def _load_games(self, game_name):
        address = _make_xo_address(game_name)

        if address in self._address_cache:
            if self._address_cache[address]:
                serialized_games = self._address_cache[address]
                games = self._deserialize(serialized_games)
            else:
                games = {}
        else:
            state_entries = self._context.get_state(
                [address],
                timeout=self.TIMEOUT)
            if state_entries:

                self._address_cache[address] = state_entries[0].data

                games = self._deserialize(data=state_entries[0].data)

            else:
                self._address_cache[address] = None
                games = {}

        return games

    def _deserialize(self, data):
        """Take bytes stored in state and deserialize them into Python
        Game objects.

        Args:
            data (bytes): The UTF-8 encoded string stored in state.

        Returns:
            (dict): game name (str) keys, Game values.
        """

        games = {}
        try:
            for game in data.decode().split("|"):
                name, board, state, player1, player2 = game.split(",")

                games[name] = Game(name, board, state, player1, player2)
        except ValueError:
            raise InternalError("Failed to deserialize game data")

        return games

    def _serialize(self, games):
        """Takes a dict of game objects and serializes them into bytes.

        Args:
            games (dict): game name (str) keys, Game values.

        Returns:
            (bytes): The UTF-8 encoded string stored in state.
        """

        game_strs = []
        for name, g in games.items():
            game_str = ",".join(
                [name, g.board, g.state, g.player1, g.player2])
            game_strs.append(game_str)

        return "|".join(sorted(game_strs)).encode()
