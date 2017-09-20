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

import shlex
import logging
import unittest
import subprocess

from sawtooth_integration.tests.integration_tools import XoClient
from sawtooth_integration.tests.integration_tools import wait_for_rest_apis


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


WAIT = 300
REST_API = 'rest-api:8080'

class TestXoSmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = XoClient('http://' + REST_API)
        wait_for_rest_apis([REST_API])

    def test_xo_smoke(self):
        game_cmds = (
            'xo init --url {}'.format(REST_API),
            'xo create nunzio --wait {}'.format(WAIT),
            'xo take nunzio 1 --wait {}'.format(WAIT),
            'xo take nunzio 4 --wait {}'.format(WAIT),
            'xo take nunzio 2 --wait {}'.format(WAIT),
            'xo take nunzio 2 --wait {}'.format(WAIT),
            'xo take nunzio 5 --wait {}'.format(WAIT),
            'xo create tony --wait {}'.format(WAIT),
            'xo take tony 9 --wait {}'.format(WAIT),
            'xo take tony 8 --wait {}'.format(WAIT),
            'xo take nunzio 3 --wait {}'.format(WAIT),
            'xo take nunzio 7 --wait {}'.format(WAIT),
            'xo take tony 6 --wait {}'.format(WAIT),
            'xo create wait --wait {}'.format(WAIT),
        )

        for cmd in game_cmds:
            _send_xo_cmd(cmd)

        self.verify_game('nunzio', 'XXXOO----', 'P1-WIN')
        self.verify_game('tony', '-----X-OX', 'P2-NEXT')
        self.verify_game('wait', '---------', 'P1-NEXT')

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
        LOGGER.info('Verifying game: %s', game_name)

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
    LOGGER.info('Sending %s', cmd_str)

    subprocess.run(
        shlex.split(cmd_str),
        check=True)
