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
import unittest
import cbor
import hashlib
import random
import string

import sawtooth_signing as signing
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.gossip.permission_verifier import PermissionVerifier
from test_permission_verifier.mocks import  MockIdentityViewFactory
from test_permission_verifier.mocks import make_policy


class TestPermissionVerifier(unittest.TestCase):
    def setUp(self):
        self.private_key = signing.generate_privkey()
        self.public_key = signing.generate_pubkey(self.private_key)
        self._identity_view_factory = MockIdentityViewFactory()
        self.permissions = {}
        self.permission_verifier = \
            PermissionVerifier(
                identity_view_factory=self._identity_view_factory,
                permissions=self.permissions,
                current_root_func=self._current_root_func)

    def _current_root_func(self):
        return "0000000000000000000000"

    def _create_transactions(self, count):
        txn_list = []
        for i in range(count):
            payload = {'Verb': 'set',
                       'Name': 'name' ,
                       'Value': 1}
            intkey_prefix = \
                hashlib.sha512('intkey'.encode('utf-8')).hexdigest()[0:6]

            addr = intkey_prefix + \
                hashlib.sha512(payload["Name"].encode('utf-8')).hexdigest()

            payload_encode = hashlib.sha512(cbor.dumps(payload)).hexdigest()

            header = TransactionHeader(
                signer_pubkey=self.public_key,
                family_name='intkey',
                family_version='1.0',
                inputs=[addr],
                outputs=[addr],
                dependencies=[],
                payload_encoding="application/cbor",
                payload_sha512=payload_encode)

            header.batcher_pubkey = self.public_key

            header_bytes = header.SerializeToString()

            signature = signing.sign(
                header_bytes,
                self.private_key)

            transaction = Transaction(
                header=header_bytes,
                payload=cbor.dumps(payload),
                header_signature=signature)

            txn_list.append(transaction)

        return txn_list

    def _create_batches(self, batch_count, txn_count):

        batch_list = []

        for i in range(batch_count):
            txn_list = self._create_transactions(txn_count)
            txn_sig_list = [txn.header_signature for txn in txn_list]

            batch_header = BatchHeader(signer_pubkey=self.public_key)
            batch_header.transaction_ids.extend(txn_sig_list)

            header_bytes = batch_header.SerializeToString()

            signature = signing.sign(
                header_bytes,
                self.private_key)

            batch = Batch(header=header_bytes,
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
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY " +  \
                                               self.public_key])
        self._identity_view_factory.add_role("transactor", "policy1")
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertTrue(allowed)

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
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY " +  \
                                               self.public_key])
        self._identity_view_factory.add_role("transactor.batch_signer",
                                             "policy1")
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertTrue(allowed)

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
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY " +  \
                                               self.public_key])
        self._identity_view_factory.add_role("transactor.transaction_signer",
                                             "policy1")
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertTrue(allowed)

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
        self._identity_view_factory.add_policy("policy1", ["PERMIT_KEY " +  \
                                               self.public_key])
        self._identity_view_factory.add_role(
            "transactor.transaction_signer.intkey",
            "policy1")
        batch = self._create_batches(1, 1)[0]
        allowed = self.permission_verifier.is_batch_signer_authorized(batch)
        self.assertTrue(allowed)

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
        Test that role:"transactor.transaction_signer" is checked properly if in
        permissions.
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

        self._identity_view_factory.add_policy("policy2", ["PERMIT_KEY other"])
        self._identity_view_factory.add_role(
                "network",
                "policy2")
        allowed = self.permission_verifier.check_network_role(self.public_key)
        self.assertFalse(allowed)
