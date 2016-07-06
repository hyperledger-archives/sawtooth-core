import unittest

import os
import random
import string

from txnintegration.validator_network_manager import defaultValidatorConfig, \
    ValidatorNetworkManager

from sawtooth_battleship import battleship_cli


class TestBattleshipCommands(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.vnm = None
        try:
            if 'TEST_VALIDATOR_URL' in os.environ:
                cls.url = os.environ['TEST_VALIDATOR_URL']
            else:
                vnm_config = defaultValidatorConfig.copy()
                if 'sawtooth_battleship' not in \
                        vnm_config['TransactionFamilies']:
                    vnm_config['TransactionFamilies'].append(
                        'sawtooth_battleship')
                vnm_config['LogLevel'] = 'DEBUG'
                cls.vnm = ValidatorNetworkManager(
                    httpPort=8800, udpPort=9600, cfg=vnm_config)
                cls.vnm.launch_network(5)
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
            cls.vnm.shutdown()
            # currently nose2 offers no way to detect test failure -- so
            # always save the results
            if cls.vnm.create_result_archive(
                    "TestBattleshipCli.tar.gz"):
                print "Validator data and logs preserved in: " \
                      "TestBattleshipCli.tar.gz"
            else:
                print "No Validator data and logs to preserve."

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
