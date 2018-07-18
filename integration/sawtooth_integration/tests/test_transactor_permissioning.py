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

import enum
import subprocess
import unittest
from uuid import uuid4

import cbor

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_signing.secp256k1 import Secp256k1PrivateKey
from sawtooth_processor_test.message_factory import MessageFactory

from sawtooth_integration.tests.integration_tools import RestClient
from sawtooth_integration.tests.integration_tools import wait_for_rest_apis


REST_API = "rest-api:8008"


class TestTransactorPermissioning(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        wait_for_rest_apis([REST_API])
        cls.REST_ENDPOINT = "http://" + REST_API

    def setUp(self):

        self.alice = Transactor('alice', self.REST_ENDPOINT)
        self.bob = Transactor('bob', self.REST_ENDPOINT)
        self.carol = Transactor('carol', self.REST_ENDPOINT)
        self.dave = Transactor('dave', self.REST_ENDPOINT)

        self.chuck = Transactor('chuck', self.REST_ENDPOINT)
        self.mallory = Transactor('mallory', self.REST_ENDPOINT)

        self.walter = Transactor('walter', self.REST_ENDPOINT)

    def test_transactor_permissioning(self):
        """Test the transactor permissioning system using the Identity
        transaction family.

        Notes:
            The test works from general to specific on the transactor
            permissioning settings, starting with 'transactor', then
            'transactor.batch_signer', then 'transactor.transaction_signer',
            and then finally 'transactor.transaction_signer.intkey' and
            'transaction.transaction_signer.xo'. For each subsection,
            the test allows some transactors and denies others and asserts
            that each either is or is not able to send transactions.

            From local configuration, Chuck and Mallory are denied from
            being transactors, Dave is denied from being a batch_signer,
            Carol is denied from sending XO transactions, while Walter, Bob,
            and Alice have all transactor permissions and no explicit denials
            from more specific permissions.

        """

        #
        # transactor subsection
        #
        # From local configuration Dave is denied from being a batch_signer,
        # and Chuck and Mallory are denied from all transactor permissions.

        self.walter.set_public_key_for_role(
            'deny_bob_allow_alice_walter',
            'transactor',
            permit_keys=[self.alice.public_key, self.walter.public_key],
            deny_keys=[self.bob.public_key])

        self.assert_able_to_send(
            (self.alice, Families.INTKEY),
            (self.walter, Families.INTKEY))

        self.assert_not_able_to_send(
            (self.bob, Families.INTKEY),
            (self.dave, Families.INTKEY),
            (self.chuck, Families.INTKEY),
            (self.mallory, Families.INTKEY))

        self.walter.set_public_key_for_role(
            'deny_alice_allow_bob_walter',
            'transactor',
            permit_keys=[self.bob.public_key, self.walter.public_key],
            deny_keys=[self.alice.public_key])

        self.assert_able_to_send(
            (self.bob, Families.INTKEY),
            (self.walter, Families.INTKEY))

        self.assert_not_able_to_send(
            (self.alice, Families.INTKEY),
            (self.chuck, Families.INTKEY),
            (self.dave, Families.INTKEY),
            (self.mallory, Families.INTKEY))

        self.walter.set_public_key_for_role(
            "allow_all_transactors",
            "transactor",
            permit_keys=["*"],
            deny_keys=[])

        #
        # transactor.batch_signer subsection
        #
        # From local configuration both Alice and Bob are allowed
        # batch_signers, while Dave is denied.

        self.walter.set_public_key_for_role(
            "deny_alice_as_batcher_allow_bob",
            "transactor.batch_signer",
            permit_keys=[self.bob.public_key, self.walter.public_key],
            deny_keys=[self.alice.public_key])

        txns = [self.alice.create_txn(
            Families.INTKEY,
            batcher=self.bob.public_key)]

        self.assert_able_to_send_batch(
            txns,
            (self.bob, Families.INTKEY))

        self.assert_not_able_to_send_batch(
            txns,
            (self.alice, Families.INTKEY))

        daves_txns = [self.alice.create_txn(
            Families.INTKEY,
            batcher=self.dave.public_key)]

        self.assert_not_able_to_send_batch(
            daves_txns,
            (self.dave, Families.INTKEY))

        self.walter.set_public_key_for_role(
            "allow_all_batchers",
            "transactor.batch_signer",
            permit_keys=["*"],
            deny_keys=[])

        #
        # transactor.transaction_signer
        #
        # From local configuration Carol is denied from XO, but is allowed all
        # other transactor permissions, Mallory and Chuck are denied from all
        # transactor permissions.

        self.walter.set_public_key_for_role(
            "allow_carol_and_no_others",
            "transactor.transaction_signer",
            permit_keys=[self.carol.public_key, self.walter.public_key],
            deny_keys=[self.alice.public_key, self.bob.public_key,
                       self.dave.public_key])

        self.assert_able_to_send((self.carol, Families.INTKEY))
        self.assert_not_able_to_send((self.carol, Families.XO))

        self.assert_not_able_to_send(
            (self.alice, Families.INTKEY),
            (self.alice, Families.XO),
            (self.bob, Families.INTKEY),
            (self.bob, Families.XO),
            (self.dave, Families.INTKEY),
            (self.dave, Families.XO),
            (self.chuck, Families.INTKEY),
            (self.chuck, Families.XO),
            (self.mallory, Families.INTKEY),
            (self.mallory, Families.XO))

        self.walter.set_public_key_for_role(
            "allow_all_transaction_signers",
            "transactor.transaction_signer",
            permit_keys=["*"],
            deny_keys=[])

        #
        # transactor.transaction_signer.< tp_name > subsection
        #
        # From local configuration Dave is denied from being a batch_signer,
        # Mallory and Chuck are denied being transactors.

        self.walter.set_public_key_for_role(
            "deny_alice_from_xo_allow_bob",
            "transactor.transaction_signer.xo",
            permit_keys=[self.bob.public_key, self.dave.public_key],
            deny_keys=[self.alice.public_key])

        self.assert_able_to_send((self.bob, Families.XO))

        self.assert_not_able_to_send(
            (self.alice, Families.XO),
            (self.chuck, Families.XO),
            (self.mallory, Families.XO),
            (self.dave, Families.XO))

        self.walter.set_public_key_for_role(
            "deny_bob_from_intkey_allow_dave_alice",
            "transactor.transaction_signer.intkey",
            permit_keys=[self.alice.public_key, self.dave.public_key],
            deny_keys=[self.bob.public_key])

        self.assert_able_to_send((self.alice, Families.INTKEY))

        self.assert_not_able_to_send(
            (self.bob, Families.INTKEY),
            (self.chuck, Families.INTKEY),
            (self.mallory, Families.INTKEY),
            (self.dave, Families.INTKEY))

    def assert_able_to_send(self, *transactor_family_pairs):
        for transactor, family in transactor_family_pairs:
            transactor.send(family)

    def assert_able_to_send_batch(self, txns, *transactor_family_pairs):
        for transactor, family in transactor_family_pairs:
            transactor.send(family_name=family, transactions=txns)

    def assert_not_able_to_send(self, *transactor_family_pairs):
        for transactor, family in transactor_family_pairs:
            with self.assertRaises(Exception):
                transactor.send(family)

    def assert_not_able_to_send_batch(self, txns, *transactor_family_pairs):
        for transactor, family in transactor_family_pairs:
            with self.assertRaises(Exception):
                transactor.send(family, txns)


INTKEY_NAMESPACE = MessageFactory.sha512('intkey'.encode())[:6]
XO_NAMESPACE = MessageFactory.sha512('xo'.encode())[:6]


# pylint: disable=invalid-name
class Families(enum.Enum):
    INTKEY = 1
    XO = 2


FAMILY_CONFIG = {
    Families.INTKEY: {
        'family_name': 'intkey',
        'family_version': '1.0',
        'namespace': MessageFactory.sha256('intkey'.encode())[:6]
    },
    Families.XO: {
        'family_name': 'xo',
        'family_version': '1.0',
        'namespace': MessageFactory.sha256('xo'.encode())[:6]
    },
}


def make_intkey_payload(unique_value):
    return {'Verb': 'set', 'Name': unique_value, 'Value': 1000}


def make_intkey_address(unique_value):
    return INTKEY_NAMESPACE + MessageFactory.sha512(
        unique_value.encode())[-64:]


def make_xo_payload(unique_value):
    return "{},{},{}".format(unique_value, 'create', '').encode('utf-8')


def xo_encode(contents):
    return contents


def make_xo_address(unique_value):
    return XO_NAMESPACE + MessageFactory.sha512(unique_value.encode())[:64]


TRANSACTION_ENCODER = {
    Families.INTKEY: {
        'encoder': cbor.dumps,
        'payload_func': make_intkey_payload,
        'address_func': make_intkey_address
    },
    Families.XO: {
        'encoder': xo_encode,
        'payload_func': make_xo_payload,
        'address_func': make_xo_address
    }
}


class Transactor:
    def __init__(self, name, rest_endpoint):
        """
        Args:
            name (str): An identifier for this Transactor
            rest_endpoint (str): The rest api that this Transactor will
                communicate with.
        """

        self.name = name
        self._rest_endpoint = rest_endpoint \
            if rest_endpoint.startswith("http://") \
            else "http://{}".format(rest_endpoint)
        with open('/root/.sawtooth/keys/{}.priv'.format(name)) as priv_file:
            private_key = Secp256k1PrivateKey.from_hex(
                priv_file.read().strip('\n'))
        self._signer = CryptoFactory(create_context('secp256k1')) \
            .new_signer(private_key)
        self._factories = {}
        self._client = RestClient(url=self._rest_endpoint)

        self._add_transaction_family_factory(Families.INTKEY)
        self._add_transaction_family_factory(Families.XO)

    @property
    def public_key(self):
        return self._signer.get_public_key().as_hex()

    def _add_transaction_family_factory(self, family_name):
        """Add a MessageFactory for the specified family.

        Args:
            family_name (Families): One of the Enum values representing
                transaction families.
        """

        family_config = FAMILY_CONFIG[family_name]
        self._factories[family_name] = MessageFactory(
            family_name=family_config['family_name'],
            family_version=family_config['family_version'],
            namespace=family_config['namespace'],
            signer=self._signer)

    def create_txn(self, family_name, batcher=None):
        unique_value = uuid4().hex[:20]
        encoder = TRANSACTION_ENCODER[family_name]['encoder']
        payload = encoder(
            TRANSACTION_ENCODER[family_name]['payload_func'](unique_value))

        address = TRANSACTION_ENCODER[family_name]['address_func'](
            unique_value)

        return self._factories[family_name].create_transaction(
            payload=payload,
            inputs=[address],
            outputs=[address],
            deps=[],
            batcher=batcher)

    def create_batch(self, family_name, count=1):
        transactions = [self.create_txn(family_name) for _ in range(count)]
        return self.batch_transactions(family_name, transactions=transactions)

    def batch_transactions(self, family_name, transactions):
        return self._factories[family_name].create_batch(
            transactions=transactions)

    def send(self, family_name, transactions=None):
        if not transactions:
            batch_list = self.create_batch(family_name)
        else:
            batch_list = self.batch_transactions(
                family_name=family_name,
                transactions=transactions)

        self._client.send_batches(batch_list=batch_list)

    def set_public_key_for_role(self, policy, role, permit_keys, deny_keys):
        permits = ["PERMIT_KEY {}".format(key) for key in permit_keys]
        denies = ["DENY_KEY {}".format(key) for key in deny_keys]
        self._run_identity_commands(policy, role, denies + permits)

    def _run_identity_commands(self, policy, role, rules):
        subprocess.run(
            ['sawtooth', 'identity', 'policy', 'create',
             '-k', '/root/.sawtooth/keys/{}.priv'.format(self.name),
             '--wait', '15',
             '--url', self._rest_endpoint, policy, *rules],
            check=True)
        subprocess.run(
            ['sawtooth', 'identity', 'role', 'create',
             '-k', '/root/.sawtooth/keys/{}.priv'.format(self.name),
             '--wait', '15',
             '--url', self._rest_endpoint, role, policy],
            check=True)
