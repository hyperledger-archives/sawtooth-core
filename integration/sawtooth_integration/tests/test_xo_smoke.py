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

import time
import shlex
import logging
import unittest
import subprocess

from sawtooth_cli.rest_client import RestClient
from sawtooth_integration.tests.integration_tools import wait_for_rest_apis


LOGGER = logging.getLogger(__name__)


REST_API = ''

class TestXoSmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = XoClient('http://rest_api:8080')
        wait_for_rest_apis([cls.client.url[len('http://'):]])

    def test_xo_smoke(self):
        game_cmds = (
            'xo init --url {}'.format(self.client.url[len('http://'):]),
            'xo create nunzio',
            'xo take nunzio 1',
            'xo take nunzio 4',
            'xo take nunzio 2',
            'xo take nunzio 2',
            'xo take nunzio 5',
            'xo create tony',
            'xo take tony 9',
            'xo take tony 8',
            'xo take nunzio 3',
            'xo take nunzio 7',
            'xo take tony 6',
        )

        for cmd in game_cmds:
            _send_xo_cmd(cmd)

        # This onerous sleep should be removed once
        # the xo --wait command is fixed.
        time.sleep(30)

        self.verify_game('nunzio', 'XXXOO----', 'P1-WIN')
        self.verify_game('tony', '-----X-OX', 'P2-NEXT')

        LOGGER.info(
            "Verifying that XO CLI commands don't blow up (but nothing else)")

        cli_cmds = (
            'xo list',
            'xo show nunzio',
            'xo show tony',
            'xo reset',
        )

        for cmd in cli_cmds:
            _send_xo_cmd(cmd)

    def verify_game(self, game_name, expected_board, expected_turn):
        LOGGER.info('Verifying game: {}'.format(game_name))

        board, turn, _, _, _ = self.client.get_game(game_name)

        self.assertEqual(
            board,
            expected_board,
            'Wrong board -- expected: {} -- actual: {}'.format(
                expected_board, board))

        self.assertEqual(
            turn,
            expected_turn,
            'Wrong turn -- expected: {} -- actual: {}'.format(
                expected_turn, turn))


def _send_xo_cmd(cmd_str):
    LOGGER.info('Sending {}'.format(cmd_str))

    subprocess.run(
        shlex.split(cmd_str),
        check=True)


class XoClient(RestClient):
    def list_games(self):
        xo_prefix = '5b7349'

        return [
            game.decode().split(',')
            for game in self.get_data(xo_prefix)
        ]

    def get_game(self, name):
        for game in self.list_games():
            if game[4] == name:
                return game
