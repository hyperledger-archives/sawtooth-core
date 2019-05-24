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
# ------------------------------------------------------------------------------

# pylint: disable=invalid-name

import unittest
import hashlib

import cbor

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.events_pb2 import Event
from sawtooth_validator.protobuf.transaction_receipt_pb2 import \
    TransactionReceipt
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.gossip.permission_verifier import PermissionVerifier
from sawtooth_validator.gossip.permission_verifier import IdentityCache
from sawtooth_validator.gossip.identity_observer import IdentityObserver
from test_permission_verifier.mocks import MockIdentityViewFactory
from test_permission_verifier.mocks import make_policy


class TestPermissionVerifier(unittest.TestCase):
    def setUp(self):
        context = create_context('secp256k1')
        crypto_factory = CryptoFactory(context)
        private_key = context.new_random_private_key()
        self.signer = crypto_factory.new_signer(private_key)
        self._identity_view_factory = MockIdentityViewFactory()
        self.permissions = {}
        self._identity_cache = IdentityCache(
            self._identity_view_factory)
        self.permission_verifier = \
            PermissionVerifier(
                permissions=self.permissions,
                current_root_func=self._current_root_func,
                identity_cache=self._identity_cache)

    @property
    def public_key(self):
        return self.signer.get_public_key().as_hex()

    def _current_root_func(self):
        return "0000000000000000000000"

    def _create_transactions(self, count):
        txn_list = []

        for _ in range(count):
            payload = {
                'Verb': 'set',
                'Name': 'name',
                'Value': 1,
            }

            intkey_prefix = \
                hashlib.sha512('intkey'.encode('utf-8')).hexdigest()[0:6]

            addr = intkey_prefix + \
                hashlib.sha512(payload["Name"].encode('utf-8')).hexdigest()

            payload_encode = hashlib.sha512(cbor.dumps(payload)).hexdigest()

            header = TransactionHeader(
                signer_public_key=self.public_key,
                family_name='intkey',
                family_version='1.0',
                inputs=[addr],
                outputs=[addr],
                dependencies=[],
                payload_sha512=payload_encode)

            header.batcher_public_key = self.public_key

            header_bytes = header.SerializeToString()

            signature = self.signer.sign(header_bytes)

            transaction = Transaction(
                header=header_bytes,
                payload=cbor.dumps(payload),
                header_signature=signature)

            txn_list.append(transaction)

        return txn_list

    def _create_batches(self, batch_count, txn_count):

        batch_list = []

        for _ in range(batch_count):
            txn_list = self._create_transactions(txn_count)
            txn_sig_list = [txn.header_signature for txn in txn_list]

            batch_header = BatchHeader(
                signer_public_key=self.signer.get_public_key().as_hex())
            batch_header.transaction_ids.extend(txn_sig_list)

            header_bytes = batch_header.SerializeToString()

            signature = self.signer.sign(header_bytes)

            batch = Batch(
                header=header_bytes,
                transactions=txn_list,
                header_signature=signature)

            batch_list.append(batch)

        return batch_list

    def test_permission(self):
        """
        Test that if no roles are set and no default policy is set,
        permit all is used.
        """
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertTrue(allowed)

    def test_default_policy_permission(self):
        """
        Test that if no roles are set, the default policy is used.
            1. Set default policy to permit all. Batch should be allowed.
            2. Set default policy to deny all. Batch should be rejected.
        """
        self._identity_view_factory.add_policy("default", ["PERMIT_KEY *"])
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertTrue(allowed)

        self._identity_cache.forked()
        self._identity_view_factory.add_policy("default", ["DENY_KEY *"])
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertFalse(allowed)

    def test_transactor_role(self):
        """
        Test that role:"transactor" is checked properly.
            1. Set policy to permit signing key. Batch should be allowed.
            2. Set policy to permit some other key. Batch should be rejected.
        """
        self._identity_view_factory.add_policy(
            "policy1", ["PERMIT_KEY " + self.public_key])
        self._identity_view_factory.add_role("transactor", "policy1")
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertTrue(allowed)

        self._identity_cache.forked()
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY other"])
        self._identity_view_factory.add_role("transactor", "policy1")
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertFalse(allowed)

    def test_transactor_batch_signer(self):
        """
        Test that role: "transactor.batch_signer" is checked properly.
            1. Set policy to permit signing key. Batch should be allowed.
            2. Set policy to permit some other key. Batch should be rejected.
        """
        self._identity_view_factory.add_policy(
            "policy1", ["PERMIT_KEY " + self.public_key])
        self._identity_view_factory.add_role("transactor.batch_signer",
                                             "policy1")
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertTrue(allowed)

        self._identity_cache.forked()
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY other"])
        self._identity_view_factory.add_role("transactor.batch_signer",
                                             "policy1")
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertFalse(allowed)

    def test_transactor_transaction_signer(self):
        """
        Test that role: "transactor.transaction_signer" is checked properly.
            1. Set policy to permit signing key. Batch should be allowed.
            2. Set policy to permit some other key. Batch should be rejected.
        """
        self._identity_view_factory.add_policy(
            "policy1", ["PERMIT_KEY " + self.public_key])
        self._identity_view_factory.add_role("transactor.transaction_signer",
                                             "policy1")
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertTrue(allowed)

        self._identity_cache.forked()
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY other"])
        self._identity_view_factory.add_role("transactor.transaction_signer",
                                             "policy1")
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertFalse(allowed)

    def test_transactor_transaction_siger_transaction_family(self):
        """
        Test that role: "transactor.transaction_signer.intkey" is checked
        properly.
            1. Set policy to permit signing key. Batch should be allowed.
            2. Set policy to permit some other key. Batch should be rejected.
        """
        self._identity_view_factory.add_policy(
            "policy1", ["PERMIT_KEY " + self.public_key])
        self._identity_view_factory.add_role(
            "transactor.transaction_signer.intkey",
            "policy1")
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertTrue(allowed)

        self._identity_cache.forked()
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY other"])
        self._identity_view_factory.add_role(
            "transactor.transaction_signer.intkey",
            "policy1")
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertFalse(allowed)

    def test_off_chain_permissions(self):
        """
        Test that if permissions are empty all signers are permitted.
        """
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.check_off_chain_batch_roles(batch)
        self.assertTrue(allowed)

    def test_off_chain_transactor(self):
        """
        Test that role:"transactor" is checked properly if in permissions.
            1. Set policy to permit signing key. Batch should be allowed.
            2. Set policy to permit some other key. Batch should be rejected.
        """
        policy = make_policy("policy1", ["PERMIT_KEY " + self.public_key])
        self.permissions["transactor"] = policy
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.check_off_chain_batch_roles(batch)
        self.assertTrue(allowed)

        policy = make_policy("policy1", ["PERMIT_KEY other"])
        self.permissions["transactor"] = policy
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.check_off_chain_batch_roles(batch)
        self.assertFalse(allowed)

    def test_off_chain_transactor_batch_signer(self):
        """
        Test that role:"transactor.batch_signer" is checked properly if in
        permissions.
            1. Set policy to permit signing key. Batch should be allowed.
            2. Set policy to permit some other key. Batch should be rejected.
        """
        policy = make_policy("policy1", ["PERMIT_KEY " + self.public_key])
        self.permissions["transactor.batch_signer"] = policy
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.check_off_chain_batch_roles(batch)
        self.assertTrue(allowed)

        policy = make_policy("policy1", ["PERMIT_KEY other"])
        self.permissions["transactor.batch_signer"] = policy
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.check_off_chain_batch_roles(batch)
        self.assertFalse(allowed)

    def test_off_chain_transactor_transaction_signer(self):
        """
        Test that role:"transactor.transaction_signer" is checked
        properly if in permissions.
            1. Set policy to permit signing key. Batch should be allowed.
            2. Set policy to permit some other key. Batch should be rejected.

        """
        policy = make_policy("policy1", ["PERMIT_KEY " + self.public_key])
        self.permissions["transactor.transaction_signer"] = policy
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.check_off_chain_batch_roles(batch)
        self.assertTrue(allowed)

        policy = make_policy("policy1", ["PERMIT_KEY other"])
        self.permissions["transactor.transaction_signer"] = policy
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.check_off_chain_batch_roles(batch)
        self.assertFalse(allowed)

    def test_off_chain_transactor_transaction_signer_family(self):
        """
        Test that role:"transactor.transaction_signer.intkey" is checked
        properly if in permissions.
            1. Set policy to permit signing key. Batch should be allowed.
            2. Set policy to permit some other key. Batch should be rejected.
        """
        policy = make_policy("policy1", ["PERMIT_KEY " + self.public_key])
        self.permissions["transactor.transaction_signer.intkey"] = policy
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.check_off_chain_batch_roles(batch)
        self.assertTrue(allowed)

        policy = make_policy("policy1", ["PERMIT_KEY other"])
        self.permissions["transactor.transaction_signer.intkey"] = policy
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.check_off_chain_batch_roles(batch)
        self.assertFalse(allowed)

    def test_network(self):
        """
        Test that if no roles are set and no default policy is set,
        permit all is used.
        """
        allowed = self.permission_verifier.check_network_role(self.public_key)
        self.assertTrue(allowed)

    def test_network_default(self):
        """
        Test that if no roles are set, the default policy is used.
            1. Set default policy to permit all. Public key should be allowed.
            2. Set default policy to deny all. Public key should be rejected.
        """
        self._identity_view_factory.add_policy("default", ["PERMIT_KEY *"])
        allowed = self.permission_verifier.check_network_role(self.public_key)
        self.assertTrue(allowed)

        self._identity_cache.forked()
        self._identity_view_factory.add_policy("default", ["DENY_KEY *"])
        allowed = self.permission_verifier.check_network_role(self.public_key)
        self.assertFalse(allowed)

    def test_network_role(self):
        """
        Test that role:"network" is checked properly.
            1. Set policy to permit signing key. Public key should be allowed.
            2. Set policy to permit some other key. Public key should be
                rejected.
        """
        self._identity_view_factory.add_policy(
            "policy1", ["PERMIT_KEY " + self.public_key])

        self._identity_view_factory.add_role(
            "network",
            "policy1")

        allowed = self.permission_verifier.check_network_role(self.public_key)
        self.assertTrue(allowed)

        self._identity_cache.forked()
        self._identity_view_factory.add_policy("policy2", ["PERMIT_KEY other"])
        self._identity_view_factory.add_role(
            "network",
            "policy2")
        allowed = self.permission_verifier.check_network_role(self.public_key)
        self.assertFalse(allowed)

    def test_network_consensus(self):
        """
        Test that if no roles are set and no default policy is set,
        permit all is used.
        """
        allowed = self.permission_verifier.check_network_consensus_role(
            self.public_key)
        self.assertTrue(allowed)

    def test_network_consensus_default(self):
        """
        Test that if no roles are set, the default policy is used.
            1. Set default policy to permit all. Public key should be allowed.
            2. Set default policy to deny all. Public key should be rejected.
        """
        self._identity_view_factory.add_policy("default", ["PERMIT_KEY *"])
        allowed = self.permission_verifier.check_network_consensus_role(
            self.public_key)
        self.assertTrue(allowed)

        self._identity_cache.forked()
        self._identity_view_factory.add_policy("default", ["DENY_KEY *"])
        allowed = self.permission_verifier.check_network_consensus_role(
            self.public_key)
        self.assertFalse(allowed)

    def test_network_consensus_role(self):
        """
        Test that role:"network.consensus" is checked properly.
            1. Set policy to permit signing key. Public key should be allowed.
            2. Set policy to permit some other key. Public key should be
                rejected.
        """
        self._identity_view_factory.add_policy(
            "policy1", ["PERMIT_KEY " + self.public_key])

        self._identity_view_factory.add_role(
            "network.consensus",
            "policy1")

        allowed = self.permission_verifier.check_network_consensus_role(
            self.public_key)
        self.assertTrue(allowed)

        self._identity_cache.forked()
        self._identity_view_factory.add_policy("policy2", ["PERMIT_KEY other"])
        self._identity_view_factory.add_role(
            "network.consensus",
            "policy2")
        allowed = self.permission_verifier.check_network_consensus_role(
            self.public_key)
        self.assertFalse(allowed)


class TestIdentityObserver(unittest.TestCase):
    def setUp(self):
        self._identity_view_factory = MockIdentityViewFactory()
        self._identity_cache = IdentityCache(
            self._identity_view_factory)
        self._identity_obsever = IdentityObserver(
            to_update=self._identity_cache.invalidate,
            forked=self._identity_cache.forked
        )

        # Make sure IdentityCache has populated roles and policy
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY key"])
        self._identity_view_factory.add_role(
            "network",
            "policy1")
        self._identity_cache.get_role("network", lambda: "state_root")
        self._identity_cache.get_policy("policy1", lambda: "state_root")

    def _current_root_func(self):
        return "0000000000000000000000"

    def create_block(self, previous_block_id="0000000000000000"):
        block_header = BlockHeader(
            block_num=85,
            state_root_hash="0987654321fedcba",
            previous_block_id=previous_block_id)
        block = BlockWrapper(
            Block(
                header_signature="abcdef1234567890",
                header=block_header.SerializeToString()))
        return block

    def test_chain_update(self):
        """
        Test that if there is no fork and only one value is udpated, only
        that value is in validated in the catch.
        """
        # Set up cache so it does not fork
        block1 = self.create_block()
        self._identity_obsever.chain_update(block1, [])
        self._identity_cache.get_role("network", lambda: "state_root")
        self._identity_cache.get_policy("policy1", lambda: "state_root")
        self.assertNotEqual(self._identity_cache["network"], None)
        self.assertNotEqual(self._identity_cache["policy1"], None)

        # Add next block and event that says network was updated.
        block2 = self.create_block("abcdef1234567890")
        event = Event(
            event_type="identity/update",
            attributes=[Event.Attribute(key="updated", value="network")])
        receipts = TransactionReceipt(events=[event])
        self._identity_obsever.chain_update(block2, [receipts])
        # Check that only "network" was invalidated
        self.assertEqual(self._identity_cache["network"], None)
        self.assertNotEqual(self._identity_cache["policy1"], None)

        # check that the correct values can be fetched from state.
        identity_view = \
            self._identity_view_factory.create_identity_view("state_root")

        self.assertEqual(
            self._identity_cache.get_role("network", lambda: "state_root"),
            identity_view.get_role("network"))

        self.assertEqual(
            self._identity_cache.get_policy("policy1", lambda: "state_root"),
            identity_view.get_policy("policy1"))

    def test_fork(self):
        """
        Test that if there is a fork, all values in the cache will be
        invalidated and fetched from state.
        """
        block = self.create_block()
        self._identity_obsever.chain_update(block, [])
        # Check that all items are invalid
        for key in self._identity_cache:
            self.assertEqual(self._identity_cache[key], None)

        # Check that the items can be fetched from state.
        identity_view = \
            self._identity_view_factory.create_identity_view("state_root")

        self.assertEqual(
            self._identity_cache.get_role("network", lambda: "state_root"),
            identity_view.get_role("network"))

        self.assertEqual(
            self._identity_cache.get_policy("policy1", lambda: "state_root"),
            identity_view.get_policy("policy1"))


class TestIdentityCache(unittest.TestCase):
    def setUp(self):
        self._identity_view_factory = MockIdentityViewFactory()
        self._identity_cache = IdentityCache(
            self._identity_view_factory)

    def test_get_role(self):
        """
        Test that a role can be fetched from the state.
        """
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY key"])
        self._identity_view_factory.add_role(
            "network",
            "policy1")
        self.assertIsNone(self._identity_cache["network"])

        identity_view = \
            self._identity_view_factory.create_identity_view("state_root")
        self.assertEqual(
            self._identity_cache.get_role("network", lambda: "state_root"),
            identity_view.get_role("network"))

    def test_get_policy(self):
        """
        Test that a policy can be fetched from the state.
        """
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY key"])
        self._identity_view_factory.add_role(
            "network",
            "policy1")
        self.assertIsNone(self._identity_cache["policy1"])

        identity_view = \
            self._identity_view_factory.create_identity_view("state_root")
        self.assertEqual(
            self._identity_cache.get_policy("policy1", lambda: "state_root"),
            identity_view.get_policy("policy1"))

    def test_role_invalidate(self):
        """
        Test that a role can be invalidated.
        """
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY key"])
        self._identity_view_factory.add_role(
            "network",
            "policy1")
        self._identity_cache.invalidate("network")
        self.assertEqual(self._identity_cache["network"], None)

        identity_view = \
            self._identity_view_factory.create_identity_view("state_root")
        self.assertEqual(
            self._identity_cache.get_role("network", lambda: "state_root"),
            identity_view.get_role("network"))

    def test_policy_invalidate(self):
        """
        Test that a policy can be invalidated.
        """
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY key"])
        self._identity_view_factory.add_role(
            "network",
            "policy1")
        self._identity_cache.invalidate("policy1")
        self.assertEqual(self._identity_cache["policy1"], None)

        identity_view = \
            self._identity_view_factory.create_identity_view("state_root")
        self.assertEqual(
            self._identity_cache.get_policy("policy1", lambda: "state_root"),
            identity_view.get_policy("policy1"))

    def test_forked(self):
        """
        Test that forked() invalidates all items in the cache, and they can
        be fetched from state.
        """
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY key"])
        self._identity_view_factory.add_role(
            "network",
            "policy1")

        identity_view = \
            self._identity_view_factory.create_identity_view("state_root")

        self._identity_cache.get_policy("policy1", lambda: "state_root")
        self._identity_cache.get_role("network", lambda: "state_root")

        self.assertEqual(len(self._identity_cache), 2)
        self._identity_cache.forked()

        self.assertEqual(self._identity_cache["network"], None)
        self.assertEqual(self._identity_cache["policy1"], None)

        self.assertEqual(
            self._identity_cache.get_policy("policy1", lambda: "state_root"),
            identity_view.get_policy("policy1"))

        self.assertEqual(
            self._identity_cache.get_role("network", lambda: "state_root"),
            identity_view.get_role("network"))
