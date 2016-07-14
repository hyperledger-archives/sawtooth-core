import unittest

import os
import time
import urllib2


from ledger.transaction.endpoint_registry import EndpointRegistryTransaction

from txnintegration.exceptions import ValidatorManagerException, ExitError
from txnintegration.integer_key_client import IntegerKeyClient
from txnintegration.utils import generate_private_key, Progress, TimeOut
from txnintegration.validator_network_manager import ValidatorNetworkManager
from txnintegration.validator_network_manager import defaultValidatorConfig
from txnserver.endpoint_registry_client import EndpointRegistryClient
from sawtooth.client import LedgerWebClient


ENABLE_STARTUP_TESTS = False
if os.environ.get('ENABLE_STARTUP_TESTS') == '1':
    ENABLE_STARTUP_TESTS = True


@unittest.skipUnless(ENABLE_STARTUP_TESTS, "Startup Tests")
class TestBasicStartup(unittest.TestCase):

    def setUp(self):
        self.number_of_daemons = int(os.environ.get("NUMBER_OF_DAEMONS", 5))
        self.vnm = ValidatorNetworkManager(cfg=defaultValidatorConfig.copy())

    def _verify_equality_of_block_lists(self, webclients):
        block_lists = []
        for ledger_client in webclients:
            block_list = []
            node_ids = set(ledger_client.get_store(
                txntype=EndpointRegistryTransaction))
            for b in ledger_client.get_block_list():
                tids_from_blocks = ledger_client.get_block(
                    blockid=b, field='TransactionIDs')
                node_ids_from_blocks = []
                for tid in tids_from_blocks:
                    node = ledger_client.\
                        get_transaction(tid, 'Update').get('NodeIdentifier')
                    node_ids_from_blocks.append(node)

                if len(node_ids.intersection(node_ids_from_blocks)) > 0:
                    block_list.append(b)
            block_lists.append(block_list)
        self.assertEqual(len(max(block_lists, key=len)),
                         len(min(block_lists, key=len)),
                         "The length of the EndpointRegistry "
                         "block lists are the same for all validators")
        zeroth_block_list = block_lists[0]
        for bl in block_lists[1:]:
            self.assertEqual(zeroth_block_list, bl,
                             "The block lists are the same for each validator")

    def _verify_orderly_transactions(self, webclients, node_identifiers):
        for ledger_client in webclients:
            node_ids = []
            for b in ledger_client.get_block_list():
                if not ledger_client.get_block(blockid=b,
                                               field='BlockNum') == 0L:
                    # the genesis block has no transactions
                    tids_from_blocks = ledger_client.get_block(
                        blockid=b, field='TransactionIDs')
                    self.assertEqual(len(tids_from_blocks), 1,
                                     "One transaction per block")
                    node = ledger_client.get_transaction(
                        tids_from_blocks[0],
                        'Update').get('NodeIdentifier')
                    node_ids.append(node)
            node_ids.reverse()
            self.assertEqual(len(node_identifiers), len(node_ids),
                             "The node list lengths are the same")
            self.assertEqual(node_ids, node_identifiers,
                             "The node lists are the same")

    def test_basic_startup(self):
        try:

            self.vnm.launch_network(count=self.number_of_daemons,
                                    others_daemon=True)

            validator_urls = self.vnm.urls()
            # IntegerKeyClient is only needed to send one more transaction
            # so n-1=number of EndpointRegistryTransactions
            integer_key_clients = [
                IntegerKeyClient(baseurl=u,
                                 keystring=generate_private_key())
                for u in validator_urls
            ]
            ledger_web_clients = [
                LedgerWebClient(url=u) for u in validator_urls]
            for int_key_client in integer_key_clients:
                int_key_client.set(key=str(1), value=20)
            self._verify_equality_of_block_lists(ledger_web_clients)

        finally:
            self.vnm.shutdown()
            self.vnm.create_result_archive('TestDaemonStartup.tar.gz')

    def test_join_after_delay_start(self):
        delayed_validator = None
        validator_urls = []
        try:
            self.vnm.launch_network(5)
            validator_urls = self.vnm.urls()

            delayed_validator = self.vnm.launch_node(delay=True)
            time.sleep(5)

            command_url = delayed_validator.Url + '/command'
            request = urllib2.Request(
                url=command_url,
                headers={'Content-Type': 'application/json'})
            response = urllib2.urlopen(request,
                                       data='{"action": "start"}')
            response.close()
            self.assertEqual(response.code, 200,
                             "Successful post to delayed validator")

            validator_urls.append(delayed_validator.Url)
            ledger_web_clients = [
                LedgerWebClient(url=u) for u in validator_urls
            ]

            with Progress("Waiting for registration of 1 validator") as p:
                url = validator_urls[0]
                to = TimeOut(60)
                while not delayed_validator.is_registered(url):
                    if to():
                        raise ExitError(
                            "{} delayed validator failed to register "
                            "within {}S.".format(
                                1, to.WaitTime))
                    p.step()
                    time.sleep(1)
                    try:
                        delayed_validator.check_error()
                    except ValidatorManagerException as vme:
                        delayed_validator.dump_log()
                        delayed_validator.dump_stderr()
                        raise ExitError(str(vme))
            integer_key_clients = [
                IntegerKeyClient(baseurl=u,
                                 keystring=generate_private_key())
                for u in validator_urls
            ]

            for int_key_client in integer_key_clients:
                int_key_client.set(key=str(1), value=20)

            self._verify_equality_of_block_lists(ledger_web_clients)

        finally:
            self.vnm.shutdown()
            if delayed_validator is not None and \
                    validator_urls is not [] and \
                    delayed_validator.Url not in validator_urls:
                delayed_validator.shutdown()
            self.vnm.create_result_archive("TestDelayedStart.tar.gz")

    def test_initial_connectivity_n_minus_1(self):
        try:
            self.vnm.validator_config['LedgerURL'] = "**none**"
            self.vnm.validator_config['Restore'] = False
            validator = self.vnm.launch_node(genesis=True)
            validators = [validator]
            with Progress("Launching validator network") as p:
                self.vnm.validator_config['LedgerURL'] = validator.Url
                self.vnm.validator_config['Restore'] = False
                node_identifiers = [validator.Address]
                for i in range(1, 5):
                    self.vnm.validator_config['InitialConnectivity'] = i
                    v = self.vnm.launch_node(genesis=False, daemon=False)
                    validators.append(v)
                    node_identifiers.append(v.Address)
                    p.step()
            self.vnm.wait_for_registration(validators, validator)
            validator_urls = self.vnm.urls()
            ledger_web_clients = [
                LedgerWebClient(url=u) for u in validator_urls
            ]
            integer_key_clients = [
                IntegerKeyClient(baseurl=u,
                                 keystring=generate_private_key())
                for u in validator_urls
            ]

            for int_key_client in integer_key_clients:
                int_key_client.set(key=str(1), value=20)

            self._verify_equality_of_block_lists(ledger_web_clients)
            self._verify_orderly_transactions(ledger_web_clients,
                                              node_identifiers)
        finally:
            self.vnm.shutdown()
            self.vnm.create_result_archive(
                'TestOrderlyInitialConnectivity.tar.gz')

    def test_adding_node_with_nodelist(self):
        try:
            validators = self.vnm.launch_network(5)
            validator_urls = self.vnm.urls()
            endpoint_client = EndpointRegistryClient(validator_urls[0])
            nodes = []
            for epl in endpoint_client.get_endpoint_list():
                node = {}
                node['Host'] = epl['Host']
                node['Port'] = epl['Port']
                node['Identifier'] = epl['NodeIdentifier']
                node['ShortName'] = epl['Name']
                nodes.append(node)
            peers = [nodes[0]['ShortName'], nodes[2]['ShortName'],
                     'validator-x']
            self.vnm.validator_config['Nodes'] = nodes
            self.vnm.validator_config['Peers'] = peers
            v = self.vnm.launch_node()
            validator_urls.append(v.Url)

            self.vnm.wait_for_registration([v], validators[0])
            ledger_web_clients = [
                LedgerWebClient(url=u) for u in validator_urls
            ]
            integer_key_clients = [
                IntegerKeyClient(baseurl=u,
                                 keystring=generate_private_key())
                for u in validator_urls
            ]

            for int_key_client in integer_key_clients:
                int_key_client.set(key=str(1), value=20)
            self._verify_equality_of_block_lists(ledger_web_clients)

        finally:
            self.vnm.shutdown()
            self.vnm.create_result_archive('TestNodeList.tar.gz')
