import os

import unittest
import logging

from txnintegration.integer_key_load_cli import IntKeyLoadTest

LOGGER = logging.getLogger(__name__)


RUN_TEST_SUITES = True \
    if os.environ.get("RUN_TEST_SUITES", False) == "1" else False


@unittest.skipUnless(RUN_TEST_SUITES, "Must be run in a test suites")
class TestPoet1IntLoad(unittest.TestCase):
    def __init__(self, test_name, urls=None):
        super(TestPoet1IntLoad, self).__init__(test_name)
        self.urls = urls

    def test_poet1_int_load(self):
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


        finally:
            print "No Validators need to be stopped"
