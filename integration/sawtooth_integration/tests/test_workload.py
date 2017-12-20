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

from sawtooth_integration.tests.integration_tools import wait_for_rest_apis
from sawtooth_cli.rest_client import RestClient


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


# the appropriateness of these parameters depends on
# the rate at which blocks are published
WORKLOAD_TIME = 5
MINIMUM_BLOCK_COUNT = 3


class TestWorkload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = 'rest-api:8008'
        wait_for_rest_apis([url])
        http = 'http://' + url
        cls.client = RestClient(http)
        cls.client.url = http

    def test_workload(self):
        workload_process = subprocess.Popen(shlex.split(
            'intkey workload -u {}'.format(
                self.client.url)))

        # run workload for WORKLOAD_TIME seconds
        time.sleep(WORKLOAD_TIME)

        subprocess.run(shlex.split(
            'sawtooth block list --url {}'.format(self.client.url)))

        blocks = self.client.list_blocks()

        # if workload is working, expect at least
        # MINIMUM_BLOCK_COUNT blocks to have been created
        self.assertGreaterEqual(
            len(list(blocks)),
            MINIMUM_BLOCK_COUNT,
            'Not enough blocks; something is probably wrong with workload')

        workload_process.terminate()
