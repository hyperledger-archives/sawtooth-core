import traceback
import unittest
import os

import numpy
import unittest
import time

from txnintegration.integer_key_load_cli import IntKeyLoadTest
from txnintegration.validator_network_manager import get_default_vnm
from txnintegration.utils import sit_rep
from txnintegration.utils import is_convergent
from txnintegration.utils import TimeOut
from txnintegration.utils import Progress


ENABLE_OVERNIGHT_TESTS = False
if os.environ.get("ENABLE_OVERNIGHT_TESTS", False) == "1":
    ENABLE_OVERNIGHT_TESTS = True


class TestValidatorShutdownRestartRestore(unittest.TestCase):
    @unittest.skipUnless(ENABLE_OVERNIGHT_TESTS,
                         "validator shutdown and restart with restore")
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
            timeout = 5

            print "Testing transaction load."
            test = IntKeyLoadTest()
            urls = vnm.urls()
            self.assertEqual(5, len(urls))
            test.setup(vnm.urls(), keys)
            test.run(keys, rounds, txn_intv)
            test.validate()

            to = TimeOut(timeout)
            convergent = False
            with Progress("Checking for validators convergence") as p:
                while convergent is False or not to.is_timed_out():
                    time.sleep(timeout)
                    p.step()
                    convergent = is_convergent(vnm.urls(),
                                               tolerance=2,
                                               standard=5)
            self.assertTrue(convergent, "All validators are "
                                        "not on the same chain.")
            print "all validators are on the same chain"
            sit_rep(vnm.urls(), verbosity=1)
            report_before_shutdown = sit_rep(vnm.urls(), verbosity=1)
            validator_report = report_before_shutdown[2]
            valid_dict_value = validator_report['Status']
            validator_blocks_shutdown = valid_dict_value['Blocks']
            print "validator_blocks", validator_blocks_shutdown

            print "turn off entire validator network"
            vnm.update(node_mat=numpy.zeros(shape=(5, 5)), timeout=8)
            # set InitialConnectivity of individual
            # node to zero before relaunching
            cfg = vnm.get_configuration(2)
            cfg['InitialConnectivity'] = 0
            vnm.set_configuration(2, cfg)
            print "relaunch validator 2"
            vnm.activate_node(2)
            report_after_relaunch = sit_rep(vnm.urls(), verbosity=1)
            validator_report = report_after_relaunch[0]
            valid_dict_value = validator_report['Status']
            validator_blocks_relaunch = valid_dict_value['Blocks']
            print "validator_blocks_relaunch", validator_blocks_relaunch

            # the length of post-shutdown validator blocks might be bigger
            # than the length of pre-shutdown validator blocks
            for i in range(0, len(validator_blocks_shutdown)):
                self.assertEqual(validator_blocks_relaunch[i],
                                 validator_blocks_shutdown[i],
                                 "mismatch in post-shutdown validator blocks. "
                                 "Validator didn't restore fr local db")
                break
                print "relaunched validator restored from local database"

        finally:
            if vnm is not None:
                # Validator network shutting down
                vnm.shutdown(archive_name='TestValidatorShutdownRestore')
