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

import hashlib

from sawtooth_validator.protobuf import identity_pb2


_IDENTITY_NS = '00001d'


_POLICY_NS = "00"


_ROLE_NS = "01"


_NUM_PARTS = 4


def _short_hash(data, length=16):
    return hashlib.sha256(data).hexdigest()[:length]


_NULL_HASH = _short_hash(''.encode())


def _create_role_address(name):
    prefix = _IDENTITY_NS + _ROLE_NS

    parts = name.split(".", maxsplit=_NUM_PARTS - 1)

    hashed_parts = [
        _short_hash(d.encode()) if i != 0 else _short_hash(d.encode(), 14)
        for i, d in enumerate(parts)
    ]
    hashed_parts.extend([_NULL_HASH] * (_NUM_PARTS - len(parts)))
    return prefix + "".join(hashed_parts)


def _create_policy_address(name):
    return _IDENTITY_NS + _POLICY_NS + _short_hash(name.encode(), 62)


def _create_from_bytes(data, protobuf_klass):
    """Return a deserialized protobuf class from the passed in bytes data
    and the protobuf class.

    Args:
        data (bytes): The serialized protobuf.
        protobuf_klass (callable): The protobuf class. Either PolicyList or
            RolesList.

    Returns:
        Either RolesList or PolicyList
    """

    protobuf_instance = protobuf_klass()
    protobuf_instance.ParseFromString(data)
    return protobuf_instance


class IdentityView:
    def __init__(self, state_view):
        """Creates an IdentityView from a StateView that is passed in.

        Args:
            state_view (:obj:`StateView`): the read-only view of state.
        """

        self._state_view = state_view

    def get_role(self, name):
        """Get a single Role by name.

        Args:
            name (str): The name of the Role.

        Returns:
            (:obj:`Role`): The Role that matches the name or None.
        """

        address = _create_role_address(name)
        role_list_bytes = None

        try:
            role_list_bytes = self._state_view.get(address=address)
        except KeyError:
            return None

        if role_list_bytes is not None:
            role_list = _create_from_bytes(role_list_bytes,
                                           identity_pb2.RoleList)
            for role in role_list.roles:
                if role.name == name:
                    return role
        return None

    def get_roles(self):
        """Return all the Roles under the Identity namespace.

        Returns:
            (list): A list containing all the Roles under the Identity
                namespace.
        """

        prefix = _IDENTITY_NS + _ROLE_NS
        rolelist_list = [
            _create_from_bytes(d, identity_pb2.RoleList)
            for _, d in self._state_view.leaves(prefix=prefix)
        ]
        roles = []
        for role_list in rolelist_list:
            for role in role_list.roles:
                roles.append(role)
        return sorted(roles, key=lambda r: r.name)

    def get_policy(self, name):
        """Get a single Policy by name.

        Args:
            name (str): The name of the Policy.

        Returns:
            (:obj:`Policy`) The Policy that matches the name.
        """

        address = _create_policy_address(name)
        policy_list_bytes = None

        try:
            policy_list_bytes = self._state_view.get(address=address)
        except KeyError:
            return None

        if policy_list_bytes is not None:
            policy_list = _create_from_bytes(policy_list_bytes,
                                             identity_pb2.PolicyList)
            for policy in policy_list.policies:
                if policy.name == name:
                    return policy
        return None

    def get_policies(self):
        """Returns all the Policies under the Identity namespace.

        Returns:
            (list): A list containing all the Policies under the Identity
                namespace.
        """

        prefix = _IDENTITY_NS + _POLICY_NS
        policylist_list = [
            _create_from_bytes(d, identity_pb2.PolicyList)
            for _, d in self._state_view.leaves(prefix=prefix)
        ]
        policies = []
        for policy_list in policylist_list:
            for policy in policy_list.policies:
                policies.append(policy)
        return sorted(policies, key=lambda p: p.name)


class IdentityViewFactory:
    def __init__(self, state_view_factory):
        """Creates a factory for producing IdentityViews based on the passed
        in StateViewFactory.

        Args:
            state_view_factory (:obj:`StateViewFactory`): A factory for
                producing StateViews with a given state hash.
        """

        self._state_view_factory = state_view_factory

    def create_identity_view(self, state_hash):
        """Factory method that creates a new IdentityView for a given
        state hash.

        Args:
            state_hash (str): The merkle root that the IdentityView should
                be based on.

        Returns:
            (:obj:`IdentityView`): A read-only view of the Identity namespace.
        """

        return IdentityView(
            self._state_view_factory.create_view(state_root_hash=state_hash))
