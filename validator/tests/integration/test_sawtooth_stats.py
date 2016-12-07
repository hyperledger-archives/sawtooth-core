import os

import unittest
import logging

from txnintegration.integer_key_load_cli import IntKeyLoadTest
from txnintegration.validator_network_manager import get_default_vnm
from sawtooth.exceptions import MessageException

from sawtooth.cli.stats import run_stats

LOGGER = logging.getLogger(__name__)


RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False


@unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
class TestSawtoothStats(unittest.TestCase):
    def __init__(self, test_name, urls=None):
        super(TestSawtoothStats, self).__init__(test_name)
        self.urls = urls

    def test_sawtooth_stats(self):
        try:

            keys = 10
            rounds = 2
            txn_intv = 0

            print "Testing transaction load."
            test = IntKeyLoadTest()
            urls = self.urls
            self.assertEqual(5, len(urls))
            test.setup(self.urls, keys)
            test.run(keys, rounds, txn_intv)
            test.validate()

            try:
                stats_config_dict = self.stats_config_dict()
                run_stats(self.urls[0], config_opts=None,
                         config_dict=stats_config_dict)

            except MessageException as e:
                raise MessageException('cant run stats print: {0}'.format(e))

        finally:
            print "No Validators need to be stopped"

    def stats_config_dict(self):
        config = {}
        config['SawtoothStats'] = {}
        config['SawtoothStats']['max_loop_count'] = 4
        config['StatsPrint'] = {}
        config['StatsPrint']['print_all'] = True
        return config
