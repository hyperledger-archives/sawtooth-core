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

import os
import shutil
import tempfile
import unittest
import hashlib

from sawtooth_validator.database.native_lmdb import NativeLmdbDatabase
from sawtooth_validator.protobuf import identity_pb2
from sawtooth_validator.state import identity_view
from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.state.state_view import StateViewFactory


class TestIdentityView(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

        self._database = NativeLmdbDatabase(
            os.path.join(self._temp_dir, 'test_identity_view.lmdb'),
            indexes=MerkleDatabase.create_index_configuration(),
            _size=10 * 1024 * 1024)
        self._tree = MerkleDatabase(self._database)

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    def test_identityview_roles(self):
        """Tests get_role and get_roles get the correct Roles and the
        IdentityViewFactory produces the correct view of the database.

        Notes:
            1. Create an empty MerkleDatabase and update it with one
            serialized RoleList.
            2. Assert that get_role returns that named Role.
            3. Assert that get_role returns None for a name that doesn't
               correspond to a Role.
            4. Assert that all the Roles are returned by get_roles.
            5. Update the MerkleDatabase with another serialized RoleList with
               a different name.
            6. Repeat 2.
            7. Repeat 3.
            8. Repeat 4.

        """

        state_view_factory = StateViewFactory(self._database)

        identity_view_factory = identity_view.IdentityViewFactory(
            state_view_factory=state_view_factory)

        # 1.
        role_list = identity_pb2.RoleList()
        role1 = role_list.roles.add()
        role1_name = "sawtooth.test.example1"

        role1.name = role1_name
        role1.policy_name = "this_is_an_example"

        state_root1 = self._tree.update(
            set_items={
                _get_role_address(role1_name): role_list.SerializeToString()
            },
            virtual=False)

        # 2.
        identity_view1 = identity_view_factory.create_identity_view(
            state_hash=state_root1)
        self.assertEqual(
            identity_view1.get_role(role1_name),
            role1,
            "IdentityView().get_role returns the correct Role by name.")

        # 3.
        self.assertIsNone(
            identity_view1.get_role("Not-a-Role"),
            "IdentityView().get_role returns None if there is "
            "no Role with that name.")

        # 4.
        self.assertEqual(identity_view1.get_roles(),
                         [role1],
                         "IdentityView().get_roles returns all the roles in"
                         " State.")

        # 5.
        role_list2 = identity_pb2.RoleList()
        role2 = role_list2.roles.add()
        role2_name = "sawtooth.test.example2"

        role2.name = role2_name
        role2.policy_name = "this_is_another_example"

        self._tree.set_merkle_root(merkle_root=state_root1)

        state_root2 = self._tree.update(
            {
                _get_role_address(role2_name): role_list2.SerializeToString()
            },
            virtual=False)

        # 6.
        identity_view2 = identity_view_factory.create_identity_view(
            state_hash=state_root2)

        self.assertEqual(
            identity_view2.get_role(role2_name),
            role2,
            "IdentityView().get_role returns the correct Role by name.")

        # 7.

        self.assertIsNone(
            identity_view2.get_role("not-a-role2"),
            "IdentityView().get_role returns None for names that don't "
            "correspond to a Role.")

        # 8.

        self.assertEqual(
            identity_view2.get_roles(),
            [role1, role2],
            "IdentityView().get_roles() returns all the Roles in alphabetical "
            "order by name.")

    def test_identityview_policy(self):
        """Tests get_policy and get_policies get the correct Policies and
        the IdentityViewFactory produces the correct view of the database.

        Notes:
            1. Create an empty MerkleDatabase and update it with one
            serialized PolicyList.
            2. Assert that get_policy returns that named Policy.
            3. Assert that get_policy returns None for a name that doesn't
               correspond to a Policy.
            4. Assert that all the Policies are returned by get_policies.
            5. Update the MerkleDatabase with another serialized PolicyList
               with a different name.
            6. Repeat 2.
            7. Repeat 3.
            8. Repeat 4.

        """

        state_view_factory = StateViewFactory(self._database)

        identity_view_factory = identity_view.IdentityViewFactory(
            state_view_factory=state_view_factory)

        # 1.
        policy_list = identity_pb2.PolicyList()
        policy1 = policy_list.policies.add()
        policy1_name = "deny_all_keys"

        policy1.name = policy1_name

        state_root1 = self._tree.update(
            set_items={
                _get_policy_address(policy1_name):
                policy_list.SerializeToString()
            },
            virtual=False)

        # 2.
        identity_view1 = identity_view_factory.create_identity_view(
            state_hash=state_root1)
        self.assertEqual(
            identity_view1.get_policy(policy1_name),
            policy1,
            "IdentityView().get_policy returns the correct Policy by name.")

        # 3.
        self.assertIsNone(
            identity_view1.get_policy("Not-a-Policy"),
            "IdentityView().get_policy returns None if "
            "there is no Policy with that name.")

        # 4.
        self.assertEqual(identity_view1.get_policies(),
                         [policy1],
                         "IdentityView().get_policies returns all the "
                         "policies in State.")

        # 5.
        policy_list2 = identity_pb2.PolicyList()
        policy2 = policy_list2.policies.add()
        policy2_name = "accept_all_keys"

        policy2.name = policy2_name

        self._tree.set_merkle_root(merkle_root=state_root1)

        state_root2 = self._tree.update(
            {
                _get_policy_address(policy2_name):
                policy_list2.SerializeToString()
            },
            virtual=False)

        # 6.
        identity_view2 = identity_view_factory.create_identity_view(
            state_hash=state_root2)

        self.assertEqual(
            identity_view2.get_policy(policy2_name),
            policy2,
            "IdentityView().get_policy returns the correct Policy by name.")

        # 7.

        self.assertIsNone(
            identity_view2.get_policy("not-a-policy2"),
            "IdentityView().get_policy returns None for names that don't "
            "correspond to a Policy.")

        # 8.
        self.assertEqual(
            identity_view2.get_policies(),
            [policy2, policy1],
            "IdentityView().get_policies returns all the Policies in "
            "alphabetical order by name.")


def _to_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _get_policy_address(policy_name):
    return IDENTITY_NAMESPACE + POLICY_PREFIX + _to_hash(policy_name)[:62]


IDENTITY_NAMESPACE = '00001d'
POLICY_PREFIX = '00'
ROLE_PREFIX = '01'


_MAX_KEY_PARTS = 4
_FIRST_ADDRESS_PART_SIZE = 14
_ADDRESS_PART_SIZE = 16
_EMPTY_PART = _to_hash('')[:_ADDRESS_PART_SIZE]


def _get_role_address(role_name):
    # split the key into 4 parts, maximum
    key_parts = role_name.split('.', maxsplit=_MAX_KEY_PARTS - 1)

    # compute the short hash of each part
    addr_parts = [_to_hash(key_parts[0])[:_FIRST_ADDRESS_PART_SIZE]]
    addr_parts += [_to_hash(x)[:_ADDRESS_PART_SIZE] for x in key_parts[1:]]

    # pad the parts with the empty hash, if needed
    addr_parts.extend([_EMPTY_PART] * (_MAX_KEY_PARTS - len(addr_parts)))

    return IDENTITY_NAMESPACE + ROLE_PREFIX + ''.join(addr_parts)
