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
# ----------------------------------------------------------------------------

from collections import deque
import hashlib
import logging
import os
import subprocess
from tempfile import mkdtemp
import time
import unittest
from uuid import uuid4

import cbor
import toml

from sawtooth_processor_test.message_factory import MessageFactory

from sawtooth_integration.tests.integration_tools import SetSawtoothHome
from sawtooth_integration.tests import node_controller as NodeController
from sawtooth_integration.tests.integration_tools import RestClient

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory

LOGGER = logging.getLogger(__name__)


class TestNetworkPermissioning(unittest.TestCase):
    """Network Permissioning tests test the ability of a validator to
    determine which network messages it will allow and which other validators
    it will peer with. Since there is no outside query to get information on
    messages that the validator has received or which other validators it is
    peered with, the tests break consensus between validators by removing
    one validator from having network capabilities, and assume that the
    change in consensus is because of the network permissioning change.

    """

    def setUp(self):
        self.clients = []
        self.sawtooth_home = {}
        self.processes = []

    def tearDown(self):
        NodeController.stop_node(self.processes)

    def test_network_trust_permissioning(self):
        """Test the network "trust" permissioning role.

        Notes:
            1) Create a network of 2 validators.
            2) Assert that 2 blocks of consensus happens within 200s
            3) Add a policy that denies the non-genesis validator from the
               network role.
            4) Assert that the validators get 2 blocks out of consensus.
            5) Add a new policy that allows both validators to use the network
               role.
            6) Assert that the validators come back into consensus within 200s.
            7) Add a policy that denies the non-genesis validator from the
               network.consensus role.
            8) Assert that the validators get 2 blocks out of consensus.
            9) Add a policy that allows both validators to use the
               network.consensus role.
            10) Assert that the validators come back into consensus

        """

        walter = Admin("http://127.0.0.1:{}".format(8008 + 0))

        sawtooth_home0 = mkdtemp()
        self.sawtooth_home[0] = sawtooth_home0

        sawtooth_home1 = mkdtemp()
        self.sawtooth_home[1] = sawtooth_home1

        with SetSawtoothHome(sawtooth_home0):
            write_validator_config(
                sawtooth_home0,
                roles={"network": "trust"},
                endpoint="tcp://127.0.0.1:{}".format(8800 + 0),
                bind=[
                    "network:tcp://127.0.0.1:{}".format(8800 + 0),
                    "component:tcp://127.0.0.1:{}".format(4004 + 0),
                    "consensus:tcp://127.0.0.1:{}".format(5050 + 0)
                ],
                seeds=["tcp://127.0.0.1:{}".format(8800 + 1)],
                peering="dynamic",
                scheduler='parallel')
            validator_non_genesis_init(sawtooth_home1)
            validator_genesis_init(
                sawtooth_home0,
                sawtooth_home1,
                identity_pub_key=walter.pub_key,
                role="network")
            self.processes.extend(start_validator(0, sawtooth_home0))
            self.clients.append(Client(NodeController.http_address(0)))

        with SetSawtoothHome(sawtooth_home1):
            write_validator_config(
                sawtooth_home1,
                roles={"network": "trust"},
                endpoint="tcp://127.0.0.1:{}".format(8800 + 1),
                bind=[
                    "network:tcp://127.0.0.1:{}".format(8800 + 1),
                    "component:tcp://127.0.0.1:{}".format(4004 + 1),
                    "consensus:tcp://127.0.0.1:{}".format(5050 + 1)
                ],
                peering="dynamic",
                seeds=["tcp://127.0.0.1:{}".format(8800 + 0)],
                scheduler='parallel')

            self.processes.extend(start_validator(1, sawtooth_home1))
            self.clients.append(Client(NodeController.http_address(1)))

        with open(
                os.path.join(self.sawtooth_home[1], 'keys', 'validator.pub'),
                'r') as infile:
            non_genesis_key = infile.read().strip('\n')
        with open(
                os.path.join(self.sawtooth_home[0], 'keys', 'validator.pub'),
                'r') as infile:
            genesis_key = infile.read().strip('\n')

        wait_for_consensus(self.clients, amount=2)

        walter.set_public_key_for_role(
            "non_genesis_out_of_network",
            "network",
            permit_keys=[genesis_key],
            deny_keys=[non_genesis_key])

        wait_for_out_of_consensus(self.clients, tolerance=2)
        show_blocks(self.clients[0].block_list())
        show_blocks(self.clients[1].block_list())

        walter.set_public_key_for_role(
            "allow_all",
            "network",
            permit_keys=[genesis_key, non_genesis_key],
            deny_keys=[])

        wait_for_consensus(self.clients)
        show_blocks(self.clients[0].block_list())
        show_blocks(self.clients[1].block_list())

        walter.set_public_key_for_role(
            "non_genesis_out_of_network",
            "network.consensus",
            permit_keys=[genesis_key],
            deny_keys=[non_genesis_key])

        wait_for_out_of_consensus(self.clients, tolerance=2)
        show_blocks(self.clients[0].block_list())
        show_blocks(self.clients[1].block_list())

        walter.set_public_key_for_role(
            "allow_all_for_consensus",
            "network.consensus",
            permit_keys=[genesis_key, non_genesis_key],
            deny_keys=[])

        wait_for_consensus(self.clients)
        show_blocks(self.clients[0].block_list())
        show_blocks(self.clients[1].block_list())

    def test_network_challenge_permissioning(self):
        """Test the network "challenge" permissioning role.

        Notes:
            1) Create a network of 2 validators.
            2) Assert that 2 blocks of consensus happens within 200s
            3) Add a policy that denies the non-genesis validator from the
               network role.
            4) Assert that the validators get 2 blocks out of consensus.
            5) Add a new policy that allows both validators to use the network
               role.
            6) Assert that the validators come back into consensus within 200s.
            7) Add a policy that denies the non-genesis validator from the
               network.consensus role.
            8) Assert that the validators get 2 blocks out of consensus.
            9) Add a policy that allows both validators to use the
               network.consensus role.
            10) Assert that the validators come back into consensus

        """

        walter = Admin("http://127.0.0.1:{}".format(8008 + 2))

        processes = []

        sawtooth_home0 = mkdtemp()
        self.sawtooth_home[0] = sawtooth_home0

        sawtooth_home1 = mkdtemp()
        self.sawtooth_home[1] = sawtooth_home1

        with SetSawtoothHome(sawtooth_home0):
            write_validator_config(
                sawtooth_home0,
                roles={"network": "challenge"},
                endpoint="tcp://127.0.0.1:{}".format(8800 + 2),
                bind=[
                    "network:tcp://127.0.0.1:{}".format(8800 + 2),
                    "component:tcp://127.0.0.1:{}".format(4004 + 2),
                    "consensus:tcp://127.0.0.1:{}".format(5050 + 2)
                ],
                seeds=["tcp://127.0.0.1:{}".format(8800 + 3)],
                peering="dynamic",
                scheduler='parallel')
            validator_non_genesis_init(sawtooth_home1)
            validator_genesis_init(
                sawtooth_home0,
                sawtooth_home1,
                identity_pub_key=walter.pub_key,
                role="network")
            processes.extend(start_validator(2, sawtooth_home0))
            self.clients.append(Client(NodeController.http_address(2)))

        with SetSawtoothHome(sawtooth_home1):
            write_validator_config(
                sawtooth_home1,
                roles={"network": "challenge"},
                endpoint="tcp://127.0.0.1:{}".format(8800 + 3),
                bind=[
                    "network:tcp://127.0.0.1:{}".format(8800 + 3),
                    "component:tcp://127.0.0.1:{}".format(4004 + 3),
                    "consensus:tcp://127.0.0.1:{}".format(5050 + 3)
                ],
                peering="dynamic",
                seeds=["tcp://127.0.0.1:{}".format(8800 + 2)],
                scheduler='parallel')

            processes.extend(start_validator(3, sawtooth_home1))
            self.clients.append(Client(NodeController.http_address(3)))

        with open(os.path.join(self.sawtooth_home[1], 'keys', 'validator.pub'),
                  'r') as infile:
            non_genesis_key = infile.read().strip('\n')
        with open(os.path.join(self.sawtooth_home[0], 'keys', 'validator.pub'),
                  'r') as infile:
            genesis_key = infile.read().strip('\n')

        wait_for_consensus(self.clients, amount=2)

        walter.set_public_key_for_role(
            "non_genesis_out_of_network",
            "network",
            permit_keys=[genesis_key],
            deny_keys=[non_genesis_key])

        wait_for_out_of_consensus(self.clients, tolerance=2)
        show_blocks(self.clients[0].block_list())
        show_blocks(self.clients[1].block_list())

        walter.set_public_key_for_role(
            "allow_all_for_consensus",
            "network",
            permit_keys=[genesis_key, non_genesis_key],
            deny_keys=[])

        wait_for_consensus(self.clients)
        show_blocks(self.clients[0].block_list())
        show_blocks(self.clients[1].block_list())

        walter.set_public_key_for_role(
            "non_genesis_out_of_network",
            "network.consensus",
            permit_keys=[genesis_key],
            deny_keys=[non_genesis_key])

        wait_for_out_of_consensus(self.clients, tolerance=2)
        show_blocks(self.clients[0].block_list())
        show_blocks(self.clients[1].block_list())

        walter.set_public_key_for_role(
            "allow_all_for_consensus",
            "network.consensus",
            permit_keys=[genesis_key, non_genesis_key],
            deny_keys=[])

        wait_for_consensus(self.clients)
        show_blocks(self.clients[0].block_list())
        show_blocks(self.clients[1].block_list())


def write_validator_config(sawtooth_home, **kwargs):
    with open(os.path.join(sawtooth_home, 'etc',
                           'validator.toml'), mode='w') as out:
        toml.dump(kwargs, out)


def start_validator(num, sawtooth_home):
    return NodeController.start_node(
        num,
        NodeController.intkey_config_identity,
        NodeController.everyone_peers_with_everyone,
        NodeController.even_parallel_odd_serial,
        sawtooth_home,
        NodeController.simple_validator_cmds)


def show_blocks(block_list):
    blocks = [("Block Num", "Block ID", "Signer Key")] + block_list
    output = "\n" + "\n".join([
        "{:^5} {:^21} {:^21}".format(item[0], item[1][:10], item[2][:10])
        for item in blocks
    ])
    LOGGER.warning(output)


class Client:
    def __init__(self, rest_endpoint):
        context = create_context('secp256k1')
        private_key = context.new_random_private_key()
        self.priv_key = private_key.as_hex()
        self.pub_key = context.get_public_key(private_key).as_hex()

        self.signer = CryptoFactory(context).new_signer(private_key)
        self._namespace = hashlib.sha512('intkey'.encode()).hexdigest()[:6]
        self._factory = MessageFactory(
            'intkey',
            '1.0',
            self._namespace,
            signer=self.signer)
        self._rest = RestClient(rest_endpoint)

    def send(self):
        name = uuid4().hex[:20]
        txns = [
            self._factory.create_transaction(
                cbor.dumps({
                    'Name': name,
                    'Verb': 'set',
                    'Value': 1000
                }),
                inputs=[
                    self._namespace + self._factory.sha512(name.encode())[-64:]
                ],
                outputs=[
                    self._namespace + self._factory.sha512(name.encode())[-64:]
                ],
                deps=[])
        ]
        self._rest.send_batches(self._factory.create_batch(txns))

    def block_list(self):
        return [(item['header']['block_num'],
                 item['header_signature'],
                 item['header']['signer_public_key'])
                for item in self._rest.block_list()['data']]


class Admin:

    def __init__(self, rest_endpoint):
        context = create_context('secp256k1')
        private_key = context.new_random_private_key()
        self.priv_key = private_key.as_hex()
        self.pub_key = context.get_public_key(private_key).as_hex()

        self._priv_key_file = os.path.join("/tmp", uuid4().hex[:20])
        with open(self._priv_key_file, mode='w') as out:
            out.write(self.priv_key)

        self._rest_endpoint = rest_endpoint

    def set_public_key_for_role(self, policy, role, permit_keys, deny_keys):
        permits = ["PERMIT_KEY {}".format(key) for key in permit_keys]
        denies = ["DENY_KEY {}".format(key) for key in deny_keys]
        self._run_identity_commands(policy, role, denies + permits)

    def _run_identity_commands(self, policy, role, rules):
        subprocess.run(
            ['sawtooth', 'identity', 'policy', 'create',
             '-k', self._priv_key_file,
             '--wait', '20',
             '--url', self._rest_endpoint, policy, *rules],
            check=True)
        subprocess.run(
            ['sawtooth', 'identity', 'role', 'create',
             '-k', self._priv_key_file,
             '--wait', '45',
             '--url', self._rest_endpoint, role, policy],
            check=True)


def wait_for_consensus(clients, tolerance=1, amount=4, timeout=100):
    """Loop until validators are within tolerance blocks of consensus. This
    happens in two phases: First there must be amount blocks in the chain,
    then each other validator can have at most tolerance different blocks
    from the genesis validator.

    Args:
        clients (list of Client): The clients of each REST Api.
        tolerance (int): The number of blocks that can differ between
            validators.
        amount (int): The number of blocks needed before a consensus check
            is valid.
        timeout (timeout): The seconds seconds that each phase of the wait
            can take.
    """

    initial_time = time.time()
    message = "Timed out waiting for consensus"

    block_height = len(clients[0].block_list())
    while block_height <= amount:
        block_height = len(clients[0].block_list())
        assert timeout > time.time() - initial_time, message
        for c in clients:
            c.send()
    not_in_consensus = deque(clients[1:])
    initial_time = time.time()
    while not_in_consensus:
        client = not_in_consensus.popleft()
        if not within_tolerance(client.block_list(), clients[0].block_list(),
                                tolerance=tolerance):
            not_in_consensus.append(client)
        assert timeout > time.time() - initial_time, message
        for c in clients:
            c.send()
    LOGGER.warning("All validators in consensus")


def wait_for_out_of_consensus(clients, tolerance=3, amount=4, timeout=100):
    """Loop until validators have a last common block that is at least
    tolerance back in the chain. Happens in two phases: first there must
    be amount blocks in the chain, then 1 validator must have at least
    tolerance different blocks at the end of the chain from the genesis
    validator.

    Args:
        clients (list of Client): The Clients of each REST Api.
        tolerance (int): The number of blocks between head of chain and
            last common block.
        amount (int): The number of blocks that must be in the chain before
            the out_of_consensus check is valid.
        timeout (int): The seconds that each phase of the wait can take.
    """

    initial_time = time.time()
    message = "Timed out waiting for validators to come out of consensus"

    block_height = 0
    while block_height <= amount:
        block_height = len(clients[0].block_list())
        assert timeout > time.time() - initial_time, message

    in_consensus = deque(clients[1:])
    initial_time = time.time()
    while in_consensus:
        client = in_consensus.popleft()
        if within_tolerance(client.block_list(), clients[0].block_list(),
                            tolerance=tolerance):
            in_consensus.append(client)
        assert timeout > time.time() - initial_time, message
        for c in clients:
            c.send()
    LOGGER.warning("Validators out of consensus")


def within_tolerance(block_list1, block_list2, tolerance):
    """Returns whether there is a common block within tolerance within the
    two block chains.

    Args:
        block_list1 (list): List of block num, signature, signer tuples.
        block_list2 (list): List of block num, signature, signer tuples.
        tolerance (int): The number of blocks between head of chain and
            last common block.

    Returns (Boolean): Whether there is a common block within tolerance.

    """

    LOGGER.warning("Head of chain height==%s, id==%s",
                   block_list1[0][0],
                   block_list1[0][1][:10])
    LOGGER.warning("Head of chain height==%s, id==%s",
                   block_list2[0][0],
                   block_list2[0][1][:10])

    if len(block_list1) >= len(block_list2):
        block_chain_long = deque(block_list1)
        block_chain_short = deque(block_list2)
    else:
        block_chain_long = deque(block_list2)
        block_chain_short = deque(block_list1)

    difference = 0
    while len(block_chain_long) > len(block_chain_short):
        difference += 1
        block_chain_long.popleft()
        if difference >= tolerance:
            return False

    for block1, block2 in zip(block_chain_long, block_chain_short):

        if block1[1] != block2[1]:
            difference += 1
        else:
            break

    return tolerance > difference


def validator_genesis_init(sawtooth_home_genesis,
                           sawtooth_home_non_genesis,
                           identity_pub_key,
                           role,
                           initial_wait_time=5.0,
                           target_wait_time=5.0,
                           minimum_wait_time=1.0):

    subprocess.run(['sawadm', 'keygen',
                    os.path.join(sawtooth_home_genesis, 'keys', 'validator')],
                   check=True)

    priv = os.path.join(sawtooth_home_genesis, 'keys', 'validator.priv')
    with open(priv, 'r') as infile:
        priv_key = infile.read().strip('\n')

    priv_non = os.path.join(sawtooth_home_non_genesis,
                            'keys', 'validator.priv')
    with open(priv_non, 'r') as infile:
        priv_key_non = infile.read().strip('\n')

    subprocess.run([
        'sawset', 'genesis',
        '-k', priv,
        '-o', os.path.join(
            sawtooth_home_genesis, 'data', 'config-genesis.batch')
    ], check=True)

    policy = "policy"
    subprocess.run(['sawtooth',
                    'identity',
                    'policy',
                    'create',
                    '-k', priv,
                    '-o', os.path.join(sawtooth_home_genesis,
                                       'data', 'policy.batch'),
                    policy,
                    "PERMIT_KEY {} PERMIT_KEY {}".format(priv_key,
                                                         priv_key_non)],
                   check=True)

    subprocess.run(['sawtooth',
                    'identity',
                    'policy',
                    'create',
                    '-k', priv,
                    '-o', os.path.join(sawtooth_home_genesis, 'data',
                                       'role.batch'),
                    role, policy],
                   check=True)

    subprocess.run([
        'sawadm', 'genesis',
        os.path.join(sawtooth_home_genesis, 'data', 'config-genesis.batch'),
        os.path.join(sawtooth_home_genesis, 'data', 'policy.batch'),
        os.path.join(sawtooth_home_genesis, 'data', 'role.batch')
    ], check=True)


def validator_non_genesis_init(sawtooth_home):
    os.mkdir(os.path.join(sawtooth_home, 'keys'))
    subprocess.run(['sawadm', 'keygen',
                    os.path.join(sawtooth_home, 'keys', 'validator')],
                   check=True)
