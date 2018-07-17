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

from sawtooth_validator.protobuf.identity_pb2 import Policy
from sawtooth_validator.protobuf.identity_pb2 import Role


class MockIdentityViewFactory:
    def __init__(self):
        self.roles = {}
        self.policies = {}

    def create_identity_view(self, root):
        return MockIdentityView(self.roles, self.policies)

    def add_role(self, name, policy_name):
        role = Role(name=name, policy_name=policy_name)
        self.roles[name] = role

    def add_policy(self, name, rules):
        entries = []
        for rule in rules:
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
        self.policies[name] = policy


class MockIdentityView:
    def __init__(self, roles, policies):
        self.roles = roles
        self.policies = policies

    def get_role(self, role_name):
        if role_name in self.roles:
            return self.roles[role_name]
        return None

    def get_policy(self, policy_name):
        if policy_name in self.policies:
            return self.policies[policy_name]
        return None


def make_policy(name, rules):
    entries = []
    for rule in rules:
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
    return policy
