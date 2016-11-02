import traceback
import unittest
import os

from txnintegration.integer_key_load_cli import IntKeyLoadTest
from txnintegration.validator_network_manager import get_default_vnm
from txnintegration.utils import sit_rep
from txnintegration.utils import is_convergent

ENABLE_OVERNIGHT_TESTS = False
if os.environ.get("ENABLE_OVERNIGHT_TESTS", False) == "1":
    ENABLE_OVERNIGHT_TESTS = True


class TestValidatorShutdownRestart(unittest.TestCase):
    @unittest.skipUnless(ENABLE_OVERNIGHT_TESTS,
                         "validator shutdown and restart test")
    def test_validator_shutdown_restart_ext(self):
        vnm = None
        print
        try:
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

            print "test validator shutdown w/ SIGINT"
            vnm.deactivate_node(2, sig='SIGINT', timeout=8, force=False)
            print 'check state of validators:'
            sit_rep(vnm.urls(), verbosity=2)

            print "sending more txns after SIGINT"
            urls = vnm.urls()
            self.assertEqual(4, len(urls))
            test.setup(urls, keys)
            test.run(keys, rounds, txn_intv)
            test.validate()

            print ("relaunching removed_validator", 2)
            vnm.activate_node(2)
            print 'check state of validators:'
            sit_rep(vnm.urls(), verbosity=2)
            if is_convergent(vnm.urls(), tolerance=2, standard=5) is True:
                print "all validators are on the same chain"
            else:
                print "all validators are not on the same chain"

            print "sending more txns after relaunching validator 2"
            urls = vnm.urls()
            self.assertEqual(5, len(urls))
            test.setup(urls, keys)
            test.run(keys, rounds, txn_intv)
            test.validate()

            print "test validator shutdown w/ SIGTERM"
            vnm.deactivate_node(4, sig='SIGTERM', timeout=8, force=False)
            print 'check state of validators:'
            sit_rep(vnm.urls(), verbosity=2)

            print "sending more txns after SIGTERM"
            urls = vnm.urls()
            self.assertEqual(4, len(urls))
            test.setup(urls, keys)
            test.run(keys, rounds, txn_intv)
            test.validate()

            print ("relaunching removed_validator", 4)
            vnm.activate_node(4)
            print 'check state of validators:'
            sit_rep(vnm.urls(), verbosity=2)
            if is_convergent(vnm.urls(), tolerance=2, standard=5) is True:
                print "all validators are on the same chain"
            else:
                print "all validators are not on the same chain"

            print "sending more txns after relaunching validator 4"
            urls = vnm.urls()
            self.assertEqual(5, len(urls))
            test.setup(urls, keys)
            test.run(keys, rounds, txn_intv)
            test.validate()

        finally:
            vnm.shutdown(archive_name='TestValidatorShutdown')
