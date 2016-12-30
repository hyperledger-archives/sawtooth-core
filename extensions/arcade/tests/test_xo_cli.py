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

from __future__ import print_function

import os
import random
import shutil
import string
import sys
import tempfile
import unittest

from contextlib import contextmanager
from StringIO import StringIO

from sawtooth.exceptions import ClientException
from sawtooth_xo import xo_cli

RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False


@contextmanager
def clean_home_directory():
    if os.name == 'nt':
        os.environ['HOME'] = os.path.expanduser("~")
    saved_home = os.environ['HOME']
    tmp_home = tempfile.mkdtemp(prefix='xo_test_home_')
    os.environ['HOME'] = tmp_home
    try:
        yield
    finally:
        shutil.rmtree(tmp_home)
        os.environ['HOME'] = saved_home


@contextmanager
def std_output():
    saved_out = sys.stdout
    saved_err = sys.stderr
    try:
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout = saved_out
        sys.stderr = saved_err


@unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
class TestXoCli(unittest.TestCase):
    def _game_name(self):
        return 'game' + \
               ''.join(random.choice(string.digits) for i in range(10))

    def test_xo_create_no_keyfile(self):
        game_name = self._game_name()

        with clean_home_directory():
            self.assertRaisesRegexp(ClientException,
                                    'Failed to load key file.*',
                                    xo_cli.main,
                                    prog_name='xo',
                                    args=['create', game_name])

    def test_xo_create(self):
        game_name = self._game_name()

        with clean_home_directory():
            with std_output() as (out, err):
                xo_cli.main(prog_name='xo', args=['init'])
                xo_cli.main(prog_name='xo',
                            args=['create', game_name, '--wait'])

            self.assertEqual(err.getvalue(), '')

            with std_output() as (out, err):
                xo_cli.main(prog_name='xo', args=['list'])

            self.assertEqual(err.getvalue(), '')

            game_found = False
            for line in out.getvalue().split('\n'):
                if line.startswith("{} ".format(game_name)):
                    print(line)
                    game_found = True
            self.assertTrue(game_found)

    def test_xo_p1_win(self):
        game_name = self._game_name()

        with clean_home_directory():
            with std_output() as (out, err):
                xo_cli.main(prog_name='xo',
                            args=['init', '--username=player1'])
                xo_cli.main(prog_name='xo',
                            args=['create', game_name, '--wait'])
                xo_cli.main(prog_name='xo',
                            args=['take', game_name, '3'])
                xo_cli.main(prog_name='xo',
                            args=['init', '--username=player2'])
                xo_cli.main(prog_name='xo',
                            args=['take', game_name, '1'])
                xo_cli.main(prog_name='xo',
                            args=['init', '--username=player1'])
                xo_cli.main(prog_name='xo',
                            args=['take', game_name, '5'])
                xo_cli.main(prog_name='xo',
                            args=['init', '--username=player2'])
                xo_cli.main(prog_name='xo',
                            args=['take', game_name, '2'])
                xo_cli.main(prog_name='xo',
                            args=['init', '--username=player1'])
                xo_cli.main(prog_name='xo',
                            args=['take', game_name, '7', '--wait'])

            self.assertEqual(err.getvalue(), '')

            with std_output() as (out, err):
                xo_cli.main(prog_name='xo', args=['show', game_name])

            self.assertIn('P1-WIN', out.getvalue())
