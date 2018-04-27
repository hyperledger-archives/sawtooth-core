# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# --------------------------------------------------------------------------

import unittest
import time
import logging
import subprocess
import shlex
from tempfile import mkdtemp

from sawtooth_integration.tests.integration_tools import SetSawtoothHome
from sawtooth_integration.tests import node_controller as NodeController
from sawtooth_integration.tests.intkey_client import IntkeyClient

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
WAIT = 120
ASSERT_CONSENSUS_TIMEOUT = 90


class TestDynamicNetwork(unittest.TestCase):
    def setUp(self):
        self.nodes = {}
        self.clients = {}
        self.populate, self.increment = make_txns()

    def test_dynamic_network(self):
        '''
        For three rounds, two validators are started per round and
        transactions are sent to all validators. As of 05/05/17,
        shutting down validators causes problems, so none are
        shut down. Once that problem is fixed, the test parameter
        `stop_nodes_per_round` should be set to 1.
        '''
        self._run_dynamic_network_test(**{
            'processors': NodeController.intkey_config_registry,
            'peering': NodeController.peer_to_preceding_only,
            'schedulers': NodeController.even_parallel_odd_serial,
            'rounds': 3,
            'start_nodes_per_round': 2,
            'stop_nodes_per_round': 0,
            'batches': 3,
            'time_between_batches': 0,
            'poet_kwargs': {
                'minimum_wait_time': 1.0,
                'initial_wait_time': 100.0,
                'target_wait_time': 30.0,
                'block_claim_delay': 1,
                'key_block_claim_limit': 25,
                'population_estimate_sample_size': 50,
                'signup_commit_maximum_delay': 0,
                'ztest_maximum_win_deviation': 3.075,
                'ztest_minimum_win_count': 3,
            }})

    def test_poet_smoke(self):
        '''
        The existing PoET smoke test is a degenerate case of the
        dynamic network test: three nodes are started and none
        are stopped for just one round.
        '''
        self._run_dynamic_network_test(**{
            'processors': NodeController.intkey_config_registry,
            'peering': NodeController.everyone_peers_with_everyone,
            'schedulers': NodeController.all_serial,
            'rounds': 1,
            'start_nodes_per_round': 3,
            'stop_nodes_per_round': 0,
            'batches': 5,
            'time_between_batches': 1,
        })

    def _run_dynamic_network_test(
            self,
            processors=NodeController.intkey_config_registry,
            peering=NodeController.peer_to_preceding_only,
            schedulers=NodeController.even_parallel_odd_serial,
            rounds=2,
            start_nodes_per_round=3,
            stop_nodes_per_round=1,
            batches=10,
            time_between_batches=1,
            poet_kwargs=None):
        '''
        The tests that actually run are just wrappers around
        this function. The intent is to make it easy to tweak
        test parameters without having to poke around in the
        test logic.

        In each round,
            1) some nodes are started,
            2) transactions are sent around in various ways,
            3) block consensus is checked, and
            4) some nodes are (possibly) stopped.
        '''

        poet_kwargs = {} if poet_kwargs is None else poet_kwargs

        for round_ in range(rounds):
            self.start_new_nodes(
                processors, peering, schedulers,
                start_nodes_per_round, round_, poet_kwargs)
            self.send_populate_batch(time_between_batches)
            self.send_txns_alternating(batches, time_between_batches)
            self.send_txns_all_at_once(batches, time_between_batches)
            self.assert_consensus()
            self.stop_nodes(stop_nodes_per_round)

        # Attempt to cleanly shutdown all processes
        for node_num in self.nodes:
            for proc in self.nodes[node_num]:
                proc.terminate()

        for node_num in self.nodes:
            for proc in self.nodes[node_num]:
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # If the process doesn't shut down cleanly, kill it
                    proc.kill()

    # utilities

    def send_txns_all_at_once(self, batches, time_between_batches):
        for client in self.clients.values():
            batch_ids = []
            for batch_num in range(batches):
                batch_id = self.send_increment_batch(
                    client, batch_num, time_between_batches)
                batch_ids.append(batch_id)
            client.poll_for_batches(batch_ids)

    def send_txns_alternating(self, batches, time_between_batches):
        batch_ids = []
        for batch_num in range(batches):
            for client in self.clients.values():
                batch_id = self.send_increment_batch(
                    client, batch_num, time_between_batches)
                batch_ids.append((client, batch_id))

        for client, batch_id in batch_ids:
            client.poll_for_batches([batch_id])

    def send_increment_batch(self, client, batch_num, time_between_batches):
        LOGGER.info('Sending batch %s @ %s', batch_num, client.url)
        return client.send_txns(self.increment)

    def send_populate_batch(self, time_between_batches):
        LOGGER.info('Sending populate txns')
        self.earliest_client().send_txns(self.populate)
        time.sleep(time_between_batches)

    def start_new_nodes(self,
                        processors,
                        peering,
                        schedulers,
                        start_nodes_per_round,
                        round_,
                        poet_kwargs):
        start = round_ * start_nodes_per_round
        for num in range(start, start + start_nodes_per_round):
            self.start_node(num, processors, peering, schedulers, poet_kwargs)

    def start_node(self, num,
                   processors,
                   peering,
                   schedulers,
                   poet_kwargs):
        LOGGER.info('Starting node %s', num)
        sawtooth_home = mkdtemp()
        with SetSawtoothHome(sawtooth_home):
            processes = NodeController.start_node(
                num, processors, peering, schedulers,
                sawtooth_home, NodeController.validator_cmds, poet_kwargs)

        # Check that none of the processes have returned
        for proc in processes:
            if proc.returncode is not None:
                raise subprocess.CalledProcessError(proc.pid, proc.returncode)

        self.nodes[num] = processes
        self.clients[num] = IntkeyClient(
            NodeController.http_address(num), WAIT)
        time.sleep(1)

    # nodes are stopped in FIFO order
    def stop_nodes(self, stop_nodes_per_round):
        stop_node_nums = list(self.nodes.keys())[:stop_nodes_per_round]
        for num in stop_node_nums:
            self.stop_node(num)
            self.nodes.pop(num)
            self.clients.pop(num)

    def stop_node(self, num):
        LOGGER.info('Stopping node %s', num)
        processes = self.nodes[num]
        NodeController.stop_node(processes)
        time.sleep(1)

    # if the validators aren't in consensus, wait and try again
    def assert_consensus(self):
        timeout = ASSERT_CONSENSUS_TIMEOUT + time.time()
        in_consensus = False

        while not in_consensus and time.time() < timeout:
            in_consensus = self.in_consensus()
        self.assertTrue(in_consensus)

    def in_consensus(self):
        tolerance = self.earliest_client().calculate_tolerance()

        LOGGER.info('Verifying consensus @ tolerance %s', tolerance)

        # for convenience, list the blocks
        for client in self.clients.values():
            url = client.url
            LOGGER.info('Blocks @ %s', url)
            subprocess.run(
                shlex.split(
                    'sawtooth block list --url {}'.format(url)),
                check=True)

        list_of_sig_lists = [
            client.recent_block_signatures(tolerance)
            for client in self.clients.values()
        ]

        sig_list_0 = list_of_sig_lists[0]

        for sig_list in list_of_sig_lists[1:]:
            if not any(sig in sig_list for sig in sig_list_0):
                return False
        return True

    def earliest_client(self):
        earliest = min(self.clients.keys())
        return self.clients[earliest]


def make_txns():
    jacksons = 'michael', 'tito', 'jackie', 'jermaine', 'marlon'
    populate = [('set', jackson, 10000) for jackson in jacksons]
    increment = [('inc', jackson, 1) for jackson in jacksons]
    return populate, increment
