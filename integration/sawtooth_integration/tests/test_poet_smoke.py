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
import subprocess
import shlex
import time
import logging

from sawtooth_integration.tests.integration_tools import wait_for_rest_apis
from sawtooth_intkey.client_cli.intkey_client import IntkeyClient

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

# This needs to be coordinated with the test's yaml file.
VALIDATOR_COUNT = 3

# Wait times and batch count can be increased for more rigor.
INITIAL_WAIT_TIME = 30
CATCH_UP_TIME = 30
TRY_AGAIN_TIME = 60

BATCH_COUNT = 20
WAIT = 300

class TestPoetSmoke(unittest.TestCase):
    def setUp(self):
        endpoints = ['rest-api-{}:8080'.format(i)
                     for i in range(VALIDATOR_COUNT)]

        wait_for_rest_apis(endpoints, tries=10)

        self.clients = [IntkeyClient('http://' + endpoint, WAIT)
                        for endpoint in endpoints]

    def test_poet_smoke(self):
        '''
        $VALIDATOR_COUNT validators are started, each with config,
        intkey, and validator registry transaction processors. After
        waiting for the validators to register, do the following:

        1) Send a batch of intkey 'set' transactions to one validator.

        2) Send one batch of intkey 'inc' transactions to each validator
           one after the other $BATCH_COUNT times.

        3) Loop through the validators, sending each one $BATCH_COUNT
           batches of intkey 'inc' transactions.

        4) Assert that the validators are in consensus with each.
        '''
        populate, increment = _make_txns()

        # wait for validators to get genesis block
        time.sleep(INITIAL_WAIT_TIME)

        self.assert_consensus()

        LOGGER.info('Sending populate txns')
        self.clients[0].send_txns(populate)

        # send txns to each validator in succession
        for i in range(BATCH_COUNT):
            for client in self.clients:
                LOGGER.info('Sending batch {} @ {}'.format(i, client.url))
                client.send_txns(increment)

        # send txns to one validator at a time
        for client in self.clients:
            for i in range(BATCH_COUNT):
                LOGGER.info('Sending batch {} @ {}'.format(i, client.url))
                client.send_txns(increment)

        # wait for validators to catch up
        time.sleep(CATCH_UP_TIME)

        self.assert_consensus()

    # if the validators aren't in consensus, wait and try again
    def assert_consensus(self):
        try:
            self._assert_consensus()
        except AssertionError:
            time.sleep(TRY_AGAIN_TIME)
            self._assert_consensus()

    def _assert_consensus(self):
        tolerance = self.clients[0].calculate_tolerance()

        LOGGER.info('Verifying consensus @ tolerance {}'.format(tolerance))

        # for convenience, list the blocks
        for client in self.clients:
            url = client.url
            LOGGER.info('Blocks @ {}'.format(url))
            subprocess.run(shlex.split(
                'sawtooth block list --url {}'.format(url)))

        list_of_sig_lists = [
            client.recent_block_signatures(tolerance)
            for client in self.clients
        ]

        sig_list_0 = list_of_sig_lists[0]

        for sig_list in list_of_sig_lists[1:]:
            self.assertTrue(
                any(sig in sig_list for sig in sig_list_0),
                'Validators are not in consensus')

def _make_txns():
    fruits = 'fig', 'quince', 'medlar', 'cornel', 'pomegranate'
    populate = [('set', fruit, 10000) for fruit in fruits]
    increment = [('inc', fruit, 1) for fruit in fruits]
    return populate, increment
