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
import time
import logging
import subprocess
import shlex

from sawtooth_integration.tests.integration_tools \
    import wait_for_rest_apis, RestClient


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


# The appropriateness of these parameters depends on
# the rate at which blocks are published. For instance,
# if blocks take a long time to be published, WAIT_TIME
# will have to be increased.
WAIT_TIME = 5
MINIMUM_BLOCK_COUNT = 3
LOAD_COUNT = 3
BATCH_COUNT = 10

REST_API = 'rest_api:8080'
URL = 'http://' + REST_API

class TestIntkeyCLI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        wait_for_rest_apis([REST_API])
        cls.client = RestClient(URL)

    def test_intkey_cli(self):
        '''
        This test creates BATCH_COUNT batches, loads them, then sleeps
        WAIT_TIME seconds, and repeats this LOAD_COUNT times. Then it
        verifies that at least MINIMUM_BLOCK_COUNT blocks have been
        published. This is a crude metric, but because the batches are
        randomly generated, it's not possible to verify state.
        '''
        for _ in range(LOAD_COUNT):
            _execute(
                'intkey create_batch -v -c {} -o intkey.batch'.format(
                    BATCH_COUNT))
            _execute(
                'intkey load -v -f intkey.batch -U {}'.format(URL))
            time.sleep(WAIT_TIME)

        _execute('sawtooth block list --url {}'.format(URL))

        # If the cli commands are working, expect at least
        # MINIMUM_BLOCK_COUNT blocks to have been created.
        self.assertGreaterEqual(
            self.client.count_blocks(),
            MINIMUM_BLOCK_COUNT,
            'Not enough blocks; something is probably wrong with intkey cli')


def _execute(cmd):
    subprocess.run(
        shlex.split(
            cmd))
