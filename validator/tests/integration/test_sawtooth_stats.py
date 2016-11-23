import os

import unittest
import logging

from txnintegration.integer_key_load_cli import IntKeyLoadTest
from txnintegration.validator_network_manager import get_default_vnm
from sawtooth.exceptions import MessageException

from sawtooth.cli.stats import run_stats

LOGGER = logging.getLogger(__name__)

ENABLE_OVERNIGHT_TESTS = False
if os.environ.get("ENABLE_OVERNIGHT_TESTS", False) == "1":
    ENABLE_OVERNIGHT_TESTS = True


class TestSawtoothStats(unittest.TestCase):
    @unittest.skipUnless(ENABLE_OVERNIGHT_TESTS,
                         "Auto print all stats views")
    def test_validator_shutdown_restart_restore_ext(self):
        print
        try:
            print "launching a validator network of 5"
            vnm = get_default_vnm(5)
            vnm.do_genesis()
            vnm.launch()

            keys = 10
            rounds = 2
            txn_intv = 0

            print "Testing transaction load."
            test = IntKeyLoadTest()
            urls = vnm.urls()
            self.assertEqual(5, len(urls))
            test.setup(vnm.urls(), keys)
            test.run(keys, rounds, txn_intv)
            test.validate()

            try:
                stats_config_dict = self.stats_config_dict()
                run_stats(vnm.urls()[0], config_opts=None, config_dict=stats_config_dict)

            except MessageException as e:
                raise MessageException('cant run stats print: {0}'.format(e))

        finally:
            if vnm is not None:
                # Validator network shutting down
                vnm.shutdown(archive_name='TestValidatorShutdownRestore')

    def stats_config_dict(self):
        config = {}
        config['SawtoothStats'] = {}
        config['SawtoothStats']['max_loop_count'] = 4
        config['StatsPrint'] = {}
        config['StatsPrint']['print_all'] = True
        return config