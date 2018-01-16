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
import shlex
import logging
import unittest
import subprocess

from sawtooth_integration.tests.integration_tools import wait_for_rest_apis

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


EXPECTED = {
    0: [1],
    1: [0, 2, 3],
    2: [1, 4],
    3: [1, 4],
    4: [2, 3],
}


class TestPeerList(unittest.TestCase):
    def setUp(self):
        endpoints = ['rest-api-{}:8008'.format(i)
                     for i in range(len(EXPECTED))]

        wait_for_rest_apis(endpoints, tries=10)

    def test_peer_list(self):
        '''
        Five validators are started, peered as described in EXPECTED (see
        the test's associated yaml file for details). `sawtooth peer
        list` is run against each of them and the output is verified.
        '''

        for node_number, peer_numbers in EXPECTED.items():
            actual_peers = _get_peers(node_number)

            expected_peers = {
                'tcp://validator-{}:8800'.format(peer_number)
                for peer_number in peer_numbers
            }

            LOGGER.debug(
                'Actual: %s -- Expected: %s',
                actual_peers,
                expected_peers)

            self.assertEqual(
                actual_peers,
                expected_peers)


def _get_peers(node_number, fmt='json'):
    cmd_output = subprocess.check_output(
        shlex.split(
            'sawtooth peer list --url {} --format {}'.format(
                'http://rest-api-{}:8008'.format(node_number),
                fmt)
        )
    ).decode().replace("'", '"')

    LOGGER.debug('peer list output: %s', cmd_output)

    if fmt == 'json':
        parsed = json.loads(cmd_output)

    elif fmt == 'csv':
        parsed = cmd_output.split(',')

    return set(parsed)
