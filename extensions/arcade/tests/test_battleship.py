import unittest

import os
import random
import string

from sawtooth_battleship import battleship_cli

RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False


@unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
class TestBattleshipCommands(unittest.TestCase):

    def _clean_data_and_key_files(self, user1, user2):
        home_dir = os.path.expanduser("~")
        key_dir = os.path.join(home_dir, ".sawtooth", "keys")
        data_dir = os.path.join(home_dir, ".sawtooth")
        user1_data = os.path.join(data_dir, "battleship-{}.data".format(user1))
        user2_data = os.path.join(data_dir, "battleship-{}.data".format(user2))
        user1_key = os.path.join(key_dir, "{}.wif".format(user1))
        user2_key = os.path.join(key_dir, "{}.wif".format(user2))
        user1_public_key = os.path.join(key_dir, "{}.addr".format(user1))
        user2_public_key = os.path.join(key_dir, "{}.addr".format(user2))
        files = [user1_data, user2_data, user1_key, user2_key,
                 user1_public_key, user2_public_key]
        for f in files:
            try:
                os.remove(f)
            except OSError as ose:
                print "Could not remove file: {}".format(ose)

    def _call_battleship(self, args):

        battleship_cli.main('battleship', args)

    def test_all_commands(self):
        user1 = "".join([random.choice(string.ascii_letters)
                         for _ in range(10)])
        user2 = "".join([random.choice(string.ascii_letters)
                         for _ in range(10)])
        try:
            self._call_battleship(['init', '--username', user1])
            self._call_battleship(['create', 'game000', '--wait'])
            self._call_battleship(['join', 'game000', '--wait'])
            self._call_battleship(['init', '--username', user2])
            self._call_battleship(['create', 'game001',
                                   "--ships", 'BBB BBB SS SS DDDD', '--wait'])
            self._call_battleship(['join', 'game001', '--wait'])
            self._call_battleship(['join', 'game000', '--wait'])
            self._call_battleship(['init', '--username', user1])
            self._call_battleship(['join', 'game001', '--wait'])
            self._call_battleship(['show', 'game000'])

            self._call_battleship(['list'])
            self._call_battleship(['show', 'game001'])
            self._call_battleship(["fire", 'game000', 'A', '1', '--wait'])
            self._call_battleship(["show", 'game000'])
            self._call_battleship(['init', '--username', user2])
            self._call_battleship(['fire', 'game001', 'E', '5', '--wait'])
            self._call_battleship(['show', 'game001'])
            self._call_battleship(['show', 'game000'])
            self._call_battleship(['genstats', '--count', '10000',
                                   '--size', '10'])
            self._call_battleship(['init', '--username', user1])
            self._call_battleship(['list'])
            self._call_battleship(['show', 'game000'])
            self._call_battleship(['show', 'game001'])
            self._call_battleship(['fire', 'game001', 'A', '7', '--wait'])
        finally:
            self._clean_data_and_key_files(user1, user2)
