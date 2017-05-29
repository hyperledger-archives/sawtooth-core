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

import json
import time
import shlex
import logging
import unittest
import subprocess

from sawtooth_cli.rest_client import RestClient
from sawtooth_integration.tests.integration_tools import wait_for_rest_apis


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

REST_API = 'rest_api:8080'

class TestXoSmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        wait_for_rest_apis([REST_API])
        cls.client = XoClient('http://' + REST_API)

    def test_xo_smoke(self):
        game_cmds = (
            'xo init --url {}'.format(REST_API),
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

        # This test often passes without this sleep statement, but
        # every so often it doesn't. Better safe than sorry?
        time.sleep(1)

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

        board, turn, _, _ = self.client.get_game(game_name)

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
        game_list = [
            json.loads(entry.decode())
            for entry in self.get_data()
        ]

        return {
            name: game_data
            for game in game_list
            for name, game_data in game.items()
        }

    def get_game(self, game_name):
        return self.list_games()[game_name].split(',')
