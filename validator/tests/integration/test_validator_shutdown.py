import traceback
import unittest
import os

from txnintegration.integer_key_load_cli import IntKeyLoadTest
from txnintegration.validator_network_manager import get_default_vnm

ENABLE_OVERNIGHT_TESTS = False
if os.environ.get("ENABLE_OVERNIGHT_TESTS", False) == "1":
    ENABLE_OVERNIGHT_TESTS = True


class TestValidatorShutdown(unittest.TestCase):
    @unittest.skipUnless(ENABLE_OVERNIGHT_TESTS, "validator shutdown test")
    def test_validator_shutdown_ext(self):
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
            test.validate()
            test.run(keys, rounds, txn_intv)

            test.setup(urls, keys)
            test.validate()
            test.run(keys, rounds, txn_intv)

            print "test validator shutdown w/ SIGINT"
            vnm.deactivate_node(2, sig='SIGINT', timeout=8, force=False)

            print "sending more txns after SIGINT"
            urls = vnm.urls()
            self.assertEqual(4, len(urls))
            test.setup(urls, keys)
            test.validate()
            test.run(keys, rounds, txn_intv)

            print "test validator shutdown w/ SIGINT"
            vnm.deactivate_node(4, sig='SIGTERM', timeout=8, force=False)

            print "sending more txns after SIGTERM"
            urls = vnm.urls()
            self.assertEqual(3, len(urls))
            test.setup(urls, keys)
            test.validate()
            test.run(keys, rounds, txn_intv)

        finally:
            vnm.shutdown(archive_name='TestValidatorShutdown')
