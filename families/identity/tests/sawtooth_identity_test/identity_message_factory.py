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
import hashlib
import logging
from sawtooth_processor_test.message_factory import MessageFactory
from sawtooth_identity.protobuf.identities_pb2 import IdentityPayload
from sawtooth_identity.protobuf.identity_pb2 import Policy
from sawtooth_identity.protobuf.identity_pb2 import PolicyList
from sawtooth_identity.protobuf.identity_pb2 import Role
from sawtooth_identity.protobuf.identity_pb2 import RoleList
from sawtooth_identity.protobuf.setting_pb2 import Setting

_MAX_KEY_PARTS = 4
_FIRST_ADDRESS_PART_SIZE = 14
_ADDRESS_PART_SIZE = 16
_EMPTY_PART = hashlib.sha256("".encode()).hexdigest()[:_ADDRESS_PART_SIZE]

_POLICY_PREFIX = '00'
_ROLE_PREFIX = '01'

LOGGER = logging.getLogger(__name__)


class IdentityMessageFactory:
    def __init__(self, signer=None):
        self._factory = MessageFactory(
            family_name="sawtooth_identity",
            family_version="1.0",
            namespace="00001d",
            signer=signer,
        )

    @property
    def public_key(self):
        return self._factory.get_public_key()

    def _to_hash(self, value):
        return hashlib.sha256(value.encode()).hexdigest()

    def _role_to_address(self, role_name):
        # split the key into 4 parts, maximum
        key_parts = role_name.split('.', maxsplit=_MAX_KEY_PARTS - 1)

        # compute the short hash of each part
        addr_parts = [self._to_hash(key_parts[0])[:_FIRST_ADDRESS_PART_SIZE]]
        addr_parts += [
            self._to_hash(x)[:_ADDRESS_PART_SIZE] for x in key_parts[1:]
        ]
        # pad the parts with the empty hash, if needed
        addr_parts.extend([_EMPTY_PART] * (_MAX_KEY_PARTS - len(addr_parts)))
        return self._factory.namespace + _ROLE_PREFIX + ''.join(addr_parts)

    def _policy_to_address(self, policy_name):
        return self._factory.namespace + _POLICY_PREFIX + \
            self._to_hash(policy_name)[:62]

    def create_tp_register(self):
        return self._factory.create_tp_register()

    def create_tp_response(self, status):
        return self._factory.create_tp_response(status)

    def _create_tp_process_request(self, payload):
        inputs = []
        outputs = []
        if payload.type == IdentityPayload.ROLE:
            role = Role()
            role.ParseFromString(payload.data)
            inputs = [
                self._role_to_address(role.name),
                self._policy_to_address(role.policy_name)
            ]

            outputs = [self._role_to_address(role.name)]
        else:
            policy = Policy()
            policy.ParseFromString(payload.data)
            inputs = [self._policy_to_address(policy.name)]

            outputs = [self._role_to_address(policy.name)]

        return self._factory.create_tp_process_request(
            payload.SerializeToString(), inputs, outputs, [])

    def create_policy_transaction(self, name, rules):
        rules_list = rules.split("\n")
        entries = []
        for rule in rules_list:
            rule = rule.split(" ")
            if rule[0] == "PERMIT_KEY":
                entry = Policy.Entry(type=Policy.PERMIT_KEY,
                                     key=rule[1])
                entries.append(entry)
            elif rule[0] == "DENY_KEY":
                entry = Policy.Entry(type=Policy.DENY_KEY,
                                     key=rule[1])
                entries.append(entry)
        policy = Policy(name=name, entries=entries)
        payload = IdentityPayload(type=IdentityPayload.POLICY,
                                  data=policy.SerializeToString())
        return self._create_tp_process_request(payload)

    def create_role_transaction(self, name, policy_name):
        role = Role(name=name, policy_name=policy_name)
        payload = IdentityPayload(type=IdentityPayload.ROLE,
                                  data=role.SerializeToString())
        return self._create_tp_process_request(payload)

    def create_get_policy_request(self, name):
        addresses = [self._policy_to_address(name)]
        return self._factory.create_get_request(addresses)

    def create_get_policy_response(self, name, rules=None):
        data = None
        if rules is not None:
            rules_list = rules.split("\n")
            entries = []
            for rule in rules_list:
                rule = rule.split(" ")
                if rule[0] == "PERMIT_KEY":
                    entry = Policy.Entry(type=Policy.PERMIT_KEY,
                                         key=rule[0])
                    entries.append(entry)
                elif rule[0] == "DENY_KEY":
                    entry = Policy.Entry(type=Policy.DENY_KEY,
                                         key=rule[0])
                    entries.append(entry)
            policy = Policy(name=name, entries=entries)
            policy_list = PolicyList(policies=[policy])
            data = policy_list.SerializeToString()
        return self._factory.create_get_response(
            {self._policy_to_address(name): data})

    def create_get_role_request(self, name):
        addresses = [self._role_to_address(name)]
        return self._factory.create_get_request(addresses)

    def create_get_role_response(self, name, policy_name=None):
        data = None
        if policy_name is not None:
            role = Role(name=name, policy_name=policy_name)
            role_list = RoleList(roles=[role])
            data = role_list.SerializeToString()
        return self._factory.create_get_response({
            self._role_to_address(name): data})

    def create_set_policy_request(self, name, rules=None):
        rules_list = rules.split("\n")
        entries = []
        for rule in rules_list:
            rule = rule.split(" ")
            if rule[0] == "PERMIT_KEY":
                entry = Policy.Entry(type=Policy.PERMIT_KEY,
                                     key=rule[1])
                entries.append(entry)
            elif rule[0] == "DENY_KEY":
                entry = Policy.Entry(type=Policy.DENY_KEY,
                                     key=rule[1])
                entries.append(entry)
        policy = Policy(name=name, entries=entries)
        policy_list = PolicyList(policies=[policy])
        return self._factory.create_set_request({
            self._policy_to_address(name): policy_list.SerializeToString()})

    def create_set_policy_response(self, name):
        addresses = [self._policy_to_address(name)]
        return self._factory.create_set_response(addresses)

    def create_set_role_request(self, name, policy_name):
        role = Role(name=name, policy_name=policy_name)
        role_list = RoleList(roles=[role])
        return self._factory.create_set_request({
            self._role_to_address(name): role_list.SerializeToString()})

    def create_set_role_response(self, name):
        addresses = [self._role_to_address(name)]
        return self._factory.create_set_response(addresses)

    def create_get_setting_request(self, key):
        addresses = [key]
        return self._factory.create_get_request(addresses)

    def create_get_setting_response(self, key, allowed):
        if allowed:
            entry = Setting.Entry(
                key="sawtooth.identity.allowed_keys",
                value=self.public_key)
            data = Setting(entries=[entry]).SerializeToString()
        else:
            entry = Setting.Entry(
                key="sawtooth.identity.allowed_keys",
                value="")
            data = Setting(entries=[entry]).SerializeToString()

        return self._factory.create_get_response({key: data})

    def create_add_event_request(self, key):
        return self._factory.create_add_event_request(
            "identity/update",
            [("updated", key)])

    def create_add_event_response(self):
        return self._factory.create_add_event_response()
