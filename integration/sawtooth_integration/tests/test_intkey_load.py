# Copyright 2016 Intel Corporation
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

from subprocess import run, PIPE

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)


class TestIntkeyLoad(unittest.TestCase):

    def test_intkey_load(self):
        url = ['-U', 'validator:40000']

        populate = ['intkey', 'populate', '-o', 'pop', '-P', '10']

        generate = ['intkey', 'generate', '-o', 'gen', '-c', '30']

        load_populate = ['intkey', 'load', '-f', 'pop'] + url

        load_generate = ['intkey', 'load', '-f', 'gen'] + url

        cleanup = ['rm', '-f', 'gen', 'pop']

        _run(populate)
        _run(load_populate)
        _run(generate)
        _run(load_generate)
        _run(cleanup)


def _run(args):
    proc = run(args, stdout=PIPE, stderr=PIPE)
    LOGGER.debug(proc.stdout.decode())
    LOGGER.debug(proc.stderr.decode())
