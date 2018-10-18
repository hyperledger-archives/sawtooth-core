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

import os
import shlex
import logging
import unittest
import subprocess

from sawtooth_integration.tests.integration_tools import XoClient
from sawtooth_integration.tests.integration_tools import wait_for_rest_apis


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


WAIT = 300
REST_API = 'rest-api:8008'


class TestXoSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = XoClient('http://' + REST_API)
        wait_for_rest_apis([REST_API])

    def test_xo_smoke(self):
        for username in ('nunzio', 'tony'):
            _send_cmd('sawtooth keygen {}'.format(username))

        game_cmds = (
            'xo create game-1 --username nunzio',
            'xo take game-1 1 --username nunzio',
            'xo take game-1 4 --username tony',
            'xo take game-1 2 --username nunzio',
            'xo take game-1 2 --username tony',
            'xo take game-1 5 --username tony',
            'xo create game-2 --username tony',
            'xo take game-2 9 --username nunzio',
            'xo take game-2 8 --username tony',
            'xo take game-1 3 --username tony',
            'xo take game-1 3 --username nunzio',
            'xo take game-1 7 --username tony',
            'xo take game-2 6 --username nunzio',
            'xo create blank --username tony',
        )

        for cmd in game_cmds:
            _send_cmd(
                '{} --url {} --wait {}'.format(
                    cmd,
                    self.client.url,
                    WAIT))

        self.assert_number_of_games(3)

        self.verify_game('game-1', 'XXXOO----', 'P1-WIN')
        self.verify_game('game-2', '-----X-OX', 'P2-NEXT')
        self.verify_game('blank', '---------', 'P1-NEXT')

        LOGGER.info(
            "Verifying that XO CLI commands don't blow up (but nothing else)")

        cli_cmds = (
            'xo list',
            'xo show game-1',
            'xo show game-2',
            'xo show blank',
        )

        for cmd in cli_cmds:
            _send_cmd(
                '{} --url {}'.format(
                    cmd,
                    self.client.url))

        if not _tp_supports_delete():
            LOGGER.warning('TP does not support state delete')
            return

        delete_cmds = (
            'xo delete game-1 --username nunzio',
            'xo delete blank --username tony',
        )

        for cmd in delete_cmds:
            _send_cmd(
                '{} --url {} --wait {}'.format(
                    cmd,
                    self.client.url,
                    WAIT))

        _send_cmd('xo list --url {}'.format(self.client.url))

        self.assert_number_of_games(1)

        self.verify_game('game-2', '-----X-OX', 'P2-NEXT')

        self.assert_no_game('game-1')
        self.assert_no_game('blank')

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

    def assert_number_of_games(self, number):
        self.assertEqual(
            len(self.client.get_data()),
            number)

    def assert_no_game(self, game_name):
        with self.assertRaises(Exception):
            self.client.get_game(game_name)


def _send_cmd(cmd_str):
    LOGGER.info('Sending %s', cmd_str)

    subprocess.run(
        shlex.split(cmd_str),
        check=True)


def _tp_supports_delete():
    supported_langs = ['python', 'go']

    lang = os.getenv('TP_LANG', None)
    if lang is not None:
        return lang in supported_langs

    return False
