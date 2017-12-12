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

import logging
import hashlib


from sawtooth_sdk.processor.handler import TransactionHandler
from sawtooth_sdk.messaging.future import FutureTimeoutError
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.protobuf.setting_pb2 import Setting

from sawtooth_identity.protobuf.identity_pb2 import Policy
from sawtooth_identity.protobuf.identity_pb2 import PolicyList
from sawtooth_identity.protobuf.identity_pb2 import Role
from sawtooth_identity.protobuf.identity_pb2 import RoleList
from sawtooth_identity.protobuf.identities_pb2 import IdentityPayload

LOGGER = logging.getLogger(__name__)

# The identity namespace is special: it is not derived from a hash.
IDENTITY_NAMESPACE = '00001d'
POLICY_PREFIX = '00'
ROLE_PREFIX = '01'
ALLOWED_SIGNER_SETTING = "sawtooth.identity.allowed_keys"

# Constants to be used when constructing config namespace addresses
_SETTING_NAMESPACE = '000000'
_SETTING_MAX_KEY_PARTS = 4
_SETTING_ADDRESS_PART_SIZE = 16
# Number of seconds to wait for state operations to succeed
STATE_TIMEOUT_SEC = 10


def _setting_key_to_address(key):
    """Computes the address for the given setting key.

     Keys are broken into four parts, based on the dots in the string. For
     example, the key `a.b.c` address is computed based on `a`, `b`, `c` and
     padding. A longer key, for example `a.b.c.d.e`, is still
     broken into four parts, but the remaining pieces are in the last part:
     `a`, `b`, `c` and `d.e`.

     Each of these pieces has a short hash computed (the first
     _SETTING_ADDRESS_PART_SIZE characters of its SHA256 hash in hex), and is
     joined into a single address, with the config namespace
     (_SETTING_NAMESPACE) added at the beginning.

     Args:
         key (str): the setting key
     Returns:
         str: the computed address
     """
    # Split the key into _SETTING_MAX_KEY_PARTS parts, maximum, compute the
    # short hash of each, and then pad if necessary
    key_parts = key.split('.', maxsplit=_SETTING_MAX_KEY_PARTS - 1)
    addr_parts = [_setting_short_hash(byte_str=x.encode()) for x in key_parts]
    addr_parts.extend(
        [_SETTING_ADDRESS_PADDING] * (_SETTING_MAX_KEY_PARTS - len(addr_parts))
    )
    return _SETTING_NAMESPACE + ''.join(addr_parts)


def _setting_short_hash(byte_str):
    # Computes the SHA 256 hash and truncates to be the length
    # of an address part (see _config_key_to_address for information on
    return hashlib.sha256(byte_str).hexdigest()[:_SETTING_ADDRESS_PART_SIZE]


_SETTING_ADDRESS_PADDING = _setting_short_hash(byte_str=b'')
ALLOWED_SIGNER_ADDRESS = _setting_key_to_address(
    "sawtooth.identity.allowed_keys")


class IdentityTransactionHandler(TransactionHandler):
    @property
    def family_name(self):
        return 'sawtooth_identity'

    @property
    def family_versions(self):
        return ['1.0']

    @property
    def namespaces(self):
        return [IDENTITY_NAMESPACE]

    def apply(self, transaction, context):
        _check_allowed_transactor(transaction, context)

        payload = IdentityPayload()
        payload.ParseFromString(transaction.payload)

        id_type = payload.type
        data = payload.data

        if id_type == IdentityPayload.ROLE:
            _set_role(data, context)

        elif id_type == IdentityPayload.POLICY:
            _set_policy(data, context)

        else:
            raise InvalidTransaction("The IdentityType must be either a"
                                     " ROLE or a POLICY")


def _check_allowed_transactor(transaction, context):
    header = transaction.header

    entries_list = _get_data(ALLOWED_SIGNER_ADDRESS, context)
    if not entries_list:
        raise InvalidTransaction(
            "The transaction signer is not authorized to submit transactions: "
            "{}".format(header.signer_public_key))

    setting = Setting()
    setting.ParseFromString(entries_list[0].data)
    for entry in setting.entries:
        if entry.key == "sawtooth.identity.allowed_keys":
            allowed_signer = entry.value.split(",")
            if header.signer_public_key in allowed_signer:
                return

    raise InvalidTransaction(
        "The transction signer is not authorized to submit transactions: "
        "{}".format(header.signer_public_key))


def _set_policy(data, context):
    new_policy = Policy()
    new_policy.ParseFromString(data)

    if not new_policy.entries:
        raise InvalidTransaction("Atleast one entry must be in a policy.")

    if not new_policy.name:
        raise InvalidTransaction("The name must be set in a policy.")

    # check entries in the policy
    for entry in new_policy.entries:
        if not entry.key:
            raise InvalidTransaction("Every policy entry must have a key.")

    address = _get_policy_address(new_policy.name)
    entries_list = _get_data(address, context)

    policy_list = PolicyList()
    policies = []

    if entries_list != []:
        policy_list.ParseFromString(entries_list[0].data)

        # sort all roles by using sorted(roles, policy.name)
        # if a policy with the same name exists, replace that policy
        policies = [
            x for x in policy_list.policies if x.name != new_policy.name
        ]
        policies.append(new_policy)
        policies = sorted(policies, key=lambda role: role.name)
    else:
        policies.append(new_policy)

    address = _get_policy_address(new_policy.name)

    # Store policy in a PolicyList incase of hash collisions
    new_policy_list = PolicyList(policies=policies)
    addresses = context.set_state({
        address: new_policy_list.SerializeToString()
    })

    if not addresses:
        LOGGER.warning('Failed to set policy %s at %s', new_policy.name,
                       address)
        raise InternalError('Unable to save policy {}'.format(new_policy.name))

    context.add_event(
        event_type="identity/update",
        attributes=[("updated", new_policy.name)])
    LOGGER.debug("Set policy : \n%s", new_policy)


def _set_role(data, context):
    role = Role()
    role.ParseFromString(data)

    if not role.name:
        raise InvalidTransaction("The name must be set in a role")
    if not role.policy_name:
        raise InvalidTransaction("A role must contain a policy name.")

    # Check that the policy refernced exists
    policy_address = _get_policy_address(role.policy_name)
    entries_list = _get_data(policy_address, context)

    if entries_list == []:
        raise InvalidTransaction(
            "Cannot set Role: {}, the Policy: {} is not set.".format(
                role.name, role.policy_name))
    else:
        policy_list = PolicyList()
        policy_list.ParseFromString(entries_list[0].data)
        exist = False
        for policy in policy_list.policies:
            if policy.name == role.policy_name:
                exist = True
                break

        if not exist:
            raise InvalidTransaction(
                "Cannot set Role {}, the Policy {} is not set.".format(
                    role.name, role.policy_name))

    address = _get_role_address(role.name)
    entries_list = _get_data(address, context)

    # Store role in a Roleist incase of hash collisions
    role_list = RoleList()
    if entries_list != []:
        role_list.ParseFromString(entries_list[0].data)

    # sort all roles by using sorted(roles, Role.name)
    roles = [x for x in role_list.roles if x.name != role.name]
    roles.append(role)
    roles = sorted(roles, key=lambda role: role.name)

    # set RoleList at the address above.
    addresses = context.set_state({
        address:
        RoleList(roles=roles).SerializeToString()
    })

    if not addresses:
        LOGGER.warning('Failed to set role %s at %s', role.name, address)
        raise InternalError('Unable to save role {}'.format(role.name))

    context.add_event(
        event_type="identity/update", attributes=[("updated", role.name)])
    LOGGER.debug("Set role: \n%s", role)


def _get_data(address, context):
    try:
        entries_list = context.get_state([address], timeout=STATE_TIMEOUT_SEC)

    except FutureTimeoutError:
        LOGGER.warning('Timeout occured on context.get_state([%s])', address)
        raise InternalError('Unable to get {}'.format(address))

    return entries_list


def _to_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _get_policy_address(policy_name):
    return IDENTITY_NAMESPACE + POLICY_PREFIX + _to_hash(policy_name)[:62]


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
