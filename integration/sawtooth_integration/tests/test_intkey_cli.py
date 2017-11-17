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

import unittest
import logging
import subprocess
import shlex

import cbor

from sawtooth_integration.tests.integration_tools import wait_for_rest_apis
from sawtooth_integration.tests.integration_tools import RestClient


LOGGER = logging.getLogger(__name__)


URL = 'http://rest-api:8008'
WAIT = 300


class IntkeyClient(RestClient):
    def __init__(self, url):
        super().__init__(
            url=url,
            namespace='1cf126')

    def get_keys(self):
        return {
            key: value
            for entry in self.get_data()
            for key, value in cbor.loads(entry).items()
        }


class TestInkeyCli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wait_for_rest_apis([URL])

        cls.client = IntkeyClient(url=URL)

    def test_intkey_cli(self):
        _send_command('sawtooth keygen')

        commands = (
            'set cat 5',  # cat = 5
            'inc cat 3',  # cat = 8
            'inc not-set 6',  # invalid
            'set dog 8',  # dog = 8
            'dec cat 4',  # cat = 4
            'dec dog 10',  # invalid (can't go below 0)
            'inc dog 100000000000',  # invalid (can't go above 2**32)
            'inc dog 3',  # dog = 11
        )

        for command in commands:
            _send_command(
                'intkey {} --url {} --wait {}'.format(
                    command, URL, WAIT))

        display = (
            'show cat',
            'show dog',
            'show not-set',
            'list'
        )

        for command in display:
            _send_command(
                'intkey {} --url {}'.format(
                    command, URL))

        self.assertEqual(
            self.client.get_keys(),
            {
                'cat': 4,
                'dog': 11
            })


def _send_command(command):
    return subprocess.run(
        shlex.split(
            command))
