import traceback
import unittest
import os
import time
import numpy

from txnintegration.integer_key_load_cli import IntKeyLoadTest
from txnintegration.validator_network_manager import get_default_vnm
from txnintegration.utils import sit_rep
from txnintegration.utils import is_convergent
from txnintegration.utils import TimeOut
from txnintegration.utils import Progress

ENABLE_OVERNIGHT_TESTS = False
if os.environ.get("ENABLE_OVERNIGHT_TESTS", False) == "1":
    ENABLE_OVERNIGHT_TESTS = True


class TestValidatorShutdownSigKillRestart(unittest.TestCase):
    @unittest.skipUnless(ENABLE_OVERNIGHT_TESTS,
                         "validator shutdown with sigkill"
                         " and restart using the database to "
                         "restore state")
    def test_validator_shutdown_sigkill_restart_ext(self):
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
            validator_report = report_before_shutdown[4]
            valid_dict_value = validator_report['Status']
            validator_blocks_shutdown = valid_dict_value['Blocks']
            print "validator_blocks", validator_blocks_shutdown

            print "shutdown validator 4 w/ SIGKILL"
            vnm.deactivate_node(4, sig='SIGKILL', timeout=8)
            print 'check state of validators:'
            sit_rep(vnm.urls(), verbosity=2)

            print "sending more txns after SIGKILL"
            urls = vnm.urls()
            self.assertEqual(4, len(urls))
            test.setup(urls, keys)
            test.run(keys, rounds, txn_intv)
            test.validate()

            print "turn off entire validator network"
            for i in range(0, 4):
                vnm.deactivate_node(i, sig='SIGINT', timeout=8, force=False)
            print 'check state of validators after graceful shutdown:'
            sit_rep(vnm.urls(), verbosity=2)

            # set InitialConnectivity of individual
            # node to zero before relaunching
            cfg = vnm.get_configuration(4)
            cfg['InitialConnectivity'] = 0
            vnm.set_configuration(4, cfg)
            print "relaunch validator 4"
            vnm.activate_node(4)
            report_after_relaunch = sit_rep(vnm.urls(), verbosity=1)
            validator_report = report_after_relaunch[0]
            valid_dict_value = validator_report['Status']
            validator_blocks_relaunch = valid_dict_value['Blocks']
            print "validator_blocks_relaunch", validator_blocks_relaunch

            if len(validator_blocks_relaunch) == \
                    len(validator_blocks_shutdown):
                if validator_blocks_shutdown == validator_blocks_relaunch:
                    print "relaunched validator restored from local db"
            else:
                for i in range(0, len(validator_blocks_shutdown)):
                    self.assertEqual(validator_blocks_relaunch[i],
                                     validator_blocks_shutdown[i],
                                     "relaunched validator didn't"
                                     " restore fr local db")
                    break
                print "relaunched validator restored from local database"

        finally:
            if vnm is not None:
                # shutting down validator network
                vnm.shutdown(archive_name='TestValidatorShutdownRestore')
