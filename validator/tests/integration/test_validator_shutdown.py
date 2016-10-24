import random
import traceback
import unittest
import os
import time
from twisted.web import http

from txnintegration.integer_key_load_cli import IntKeyLoadTest
from txnintegration.utils import generate_private_key
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.validator_network_manager import defaultValidatorConfig
from txnintegration.validator_network_manager import ValidatorNetworkManager

ENABLE_OVERNIGHT_TESTS = False
if os.environ.get("ENABLE_OVERNIGHT_TESTS", False) == "1":
    ENABLE_OVERNIGHT_TESTS = True


class TestValidatorShutdown(unittest.TestCase):
    @unittest.skipUnless(ENABLE_OVERNIGHT_TESTS, "validator shutdown test")
    def test_validator_shutdown_ext(self):
        urls = []
        validators = []
        vnm = None
        try:
            print "Launching validator network."
            vnm_config = defaultValidatorConfig.copy()

            vnm = ValidatorNetworkManager(http_port=9000, udp_port=9100,
                                          cfg=vnm_config)

            firstwavevalidators = vnm.launch_network(5)

            urls = vnm.urls()
            for i in range(0, len(urls)):
                validators.append(vnm.validator(i))

            keys = 10
            rounds = 2
            txn_intv = 0

            print "Testing transaction load."
            test = IntKeyLoadTest()
            test.setup(urls, keys)
            test.validate()
            test.run(keys, rounds, txn_intv)

            validator_to_be_removed = 4
            print ("shutting down validator ", validator_to_be_removed)
            vnm.validator_shutdown(validator_to_be_removed,
                                   force=True,
                                   archive=None
                                   )

            print "sending more txns after SIGKILL"
            urls.pop(validator_to_be_removed)
            test.setup(urls, keys)
            test.validate()
            test.run(keys, rounds, txn_intv)

            validator_to_be_removed = 2
            print "now validator shutdown w/ SIGINT"
            print ("shutdown(SIGINT) of validator ", validator_to_be_removed)
            vnm.validator_shutdown(validator_to_be_removed,
                                   force=False,
                                   archive=None
                                   )

            print "sending more txns after SIGINT"
            urls = []
            urls = vnm.urls()
            test.setup(urls, keys)
            test.validate()
            test.run(keys, rounds, txn_intv)

            vnm.shutdown()
        except Exception as e:
            print "Exception encountered in test case."
            traceback.print_exc()
            if vnm:
                vnm.shutdown()
            vnm.create_result_archive("TestValidatorShutdown.tar.gz")
            print "Validator data and logs preserved in: " \
                  "TestValidatorShutdown.tar.gz"
            raise e
