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

import logging
import unittest
import traceback
import time
import subprocess

from sawtooth_integration.tests.integration_tools import wait_for_rest_apis

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)


class TestXoSmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        wait_for_rest_apis(['rest_api:8080'])

    def test_xo_smoke(self):

        cmds = [
            ['xo', 'init', '--url', 'rest_api:8080'],
            ['xo', 'create', 'game0'],
        ]

        for i in (0, 1, 2, 3, 4, 5, 6, 8, 7, 9, 10):
            cmds += [['xo', 'take', 'game0', str(i)]]

        cmds += [
            ['xo', 'show', 'game0'],
            ['xo', 'list'],
            ['xo', 'reset'],
        ]

        for cmd in cmds:
            self._run(cmd)

    def _run(self, args):
        try:
            LOGGER.debug("Running %s", " ".join(args))
            proc = subprocess.run(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            LOGGER.debug(proc.stdout.decode())
        except subprocess.CalledProcessError as err:
            LOGGER.debug(err)
            LOGGER.debug(err.stderr.decode())
            traceback.print_exc()
            self.fail(self.__class__.__name__)
