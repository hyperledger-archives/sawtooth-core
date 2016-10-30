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
from txnintegration.validator_network_manager import get_default_vnm

ENABLE_INTEGRATION_TESTS = False
if os.environ.get("ENABLE_INTEGRATION_TESTS", False) == "1":
    ENABLE_INTEGRATION_TESTS = True


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


@unittest.skipUnless(ENABLE_INTEGRATION_TESTS, "integration test")
class TestXoCli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vnm = None
        try:
            if 'TEST_VALIDATOR_URL' in os.environ:
                cls.url = os.environ['TEST_VALIDATOR_URL']
            else:
                overrides = {
                    "TransactionFamilies": ['sawtooth_xo'],
                }
                cls.vnm = get_default_vnm(5, overrides=overrides)
                cls.vnm.do_genesis()
                cls.vnm.launch()
                # the url of the initial validator
                cls.url = cls.vnm.urls()[0] + '/'
        except:
            if cls.vnm is not None:
                cls.vnm.shutdown()
                cls.vnm = None
            raise Exception("Validators didn't start up correctly.")

    @classmethod
    def tearDownClass(cls):
        if cls.vnm is not None:
            cls.vnm.shutdown(archive_name='TestXoCli')
        else:
            print "No Validator data and logs to preserve."

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

            self.assertEquals(err.getvalue(), '')

            with std_output() as (out, err):
                xo_cli.main(prog_name='xo', args=['list'])

            self.assertEquals(err.getvalue(), '')

            game_found = False
            for line in out.getvalue().split('\n'):
                if line.startswith("{} ".format(game_name)):
                    print line
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

            self.assertEquals(err.getvalue(), '')

            with std_output() as (out, err):
                xo_cli.main(prog_name='xo', args=['show', game_name])

            self.assertIn('P1-WIN', out.getvalue())
