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

import collections
import logging
import os

import toml

from sawtooth_validator.exceptions import LocalConfigurationError
from sawtooth_validator.config.path import load_path_config
from sawtooth_validator.protobuf.identity_pb2 import Policy


LOGGER = logging.getLogger(__name__)


def load_default_validator_config():
    return ValidatorConfig(
        bind_network='tcp://127.0.0.1:8800',
        bind_component='tcp://127.0.0.1:4004',
        endpoint=None,
        peering='static',
        scheduler='serial',
        minimum_peer_connectivity=3,
        maximum_peer_connectivity=10)


def load_toml_validator_config(filename):
    """Returns a ValidatorConfig created by loading a TOML file from the
    filesystem.
    """
    if not os.path.exists(filename):
        LOGGER.info(
            "Skipping validator config loading from non-existent config file:"
            " %s", filename)
        return ValidatorConfig()

    LOGGER.info("Loading validator information from config: %s", filename)

    try:
        with open(filename) as fd:
            raw_config = fd.read()
    except IOError as e:
        raise LocalConfigurationError(
            "Unable to load validator configuration file: {}".format(str(e)))

    toml_config = toml.loads(raw_config)
    invalid_keys = set(toml_config.keys()).difference(
        ['bind', 'endpoint', 'peering', 'seeds', 'peers', 'network_public_key',
         'network_private_key', 'scheduler', 'permissions', 'roles',
         'opentsdb_url', 'opentsdb_db', 'opentsdb_username',
         'opentsdb_password', 'minimum_peer_connectivity',
         'maximum_peer_connectivity'])
    if invalid_keys:
        raise LocalConfigurationError(
            "Invalid keys in validator config: "
            "{}".format(", ".join(sorted(list(invalid_keys)))))
    bind_network = None
    bind_component = None
    for bind in toml_config.get("bind", []):
        if "network" in bind:
            bind_network = bind[bind.find(":") + 1:]
        if "component" in bind:
            bind_component = bind[bind.find(":") + 1:]

    network_public_key = None
    network_private_key = None

    if toml_config.get("network_public_key") is not None:
        network_public_key = toml_config.get("network_public_key").encode()

    if toml_config.get("network_private_key") is not None:
        network_private_key = toml_config.get("network_private_key").encode()

    config = ValidatorConfig(
        bind_network=bind_network,
        bind_component=bind_component,
        endpoint=toml_config.get("endpoint", None),
        peering=toml_config.get("peering", None),
        seeds=toml_config.get("seeds", None),
        peers=toml_config.get("peers", None),
        network_public_key=network_public_key,
        network_private_key=network_private_key,
        scheduler=toml_config.get("scheduler", None),
        permissions=parse_permissions(toml_config.get("permissions", None)),
        roles=toml_config.get("roles", None),
        opentsdb_url=toml_config.get("opentsdb_url", None),
        opentsdb_db=toml_config.get("opentsdb_db", None),
        opentsdb_username=toml_config.get("opentsdb_username", None),
        opentsdb_password=toml_config.get("opentsdb_password", None),
        minimum_peer_connectivity=toml_config.get(
            "minimum_peer_connectivity", None),
        maximum_peer_connectivity=toml_config.get(
            "maximum_peer_connectivity", None)
    )

    return config


def merge_validator_config(configs):
    """
    Given a list of ValidatorConfig objects, merges them into a single
    ValidatorConfig, giving priority in the order of the configs
    (first has highest priority).
    """
    bind_network = None
    bind_component = None
    endpoint = None
    peering = None
    seeds = None
    peers = None
    network_public_key = None
    network_private_key = None
    scheduler = None
    permissions = None
    roles = None
    opentsdb_url = None
    opentsdb_db = None
    opentsdb_username = None
    opentsdb_password = None
    minimum_peer_connectivity = None
    maximum_peer_connectivity = None

    for config in reversed(configs):
        if config.bind_network is not None:
            bind_network = config.bind_network
        if config.bind_component is not None:
            bind_component = config.bind_component
        if config.endpoint is not None:
            endpoint = config.endpoint
        if config.peering is not None:
            peering = config.peering
        if config.seeds is not None:
            seeds = config.seeds
        if config.peers is not None:
            peers = config.peers
        if config.network_public_key is not None:
            network_public_key = config.network_public_key
        if config.network_private_key is not None:
            network_private_key = config.network_private_key
        if config.scheduler is not None:
            scheduler = config.scheduler
        if config.permissions is not None or config.permissions == {}:
            permissions = config.permissions
        if config.roles is not None:
            roles = config.roles
        if config.opentsdb_url is not None:
            opentsdb_url = config.opentsdb_url
        if config.opentsdb_db is not None:
            opentsdb_db = config.opentsdb_db
        if config.opentsdb_username is not None:
            opentsdb_username = config.opentsdb_username
        if config.opentsdb_password is not None:
            opentsdb_password = config.opentsdb_password
        if config.minimum_peer_connectivity is not None:
            minimum_peer_connectivity = config.minimum_peer_connectivity
        if config.maximum_peer_connectivity is not None:
            maximum_peer_connectivity = config.maximum_peer_connectivity

    return ValidatorConfig(
        bind_network=bind_network,
        bind_component=bind_component,
        endpoint=endpoint,
        peering=peering,
        seeds=seeds,
        peers=peers,
        network_public_key=network_public_key,
        network_private_key=network_private_key,
        scheduler=scheduler,
        permissions=permissions,
        roles=roles,
        opentsdb_url=opentsdb_url,
        opentsdb_db=opentsdb_db,
        opentsdb_username=opentsdb_username,
        opentsdb_password=opentsdb_password,
        minimum_peer_connectivity=minimum_peer_connectivity,
        maximum_peer_connectivity=maximum_peer_connectivity)


def parse_permissions(permissions):
    roles = {}
    path_config = load_path_config()
    policy_dir = path_config.policy_dir
    if permissions is not None:
        for role_name in permissions:
            policy_name = permissions[role_name]
            policy_path = os.path.join(policy_dir,
                                       policy_name)
            rules = []
            if os.path.exists(policy_path):
                with open(policy_path) as policy_file:
                    rules = policy_file.read().splitlines()
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

                policy = Policy(name=policy_name, entries=entries)
                roles[role_name] = policy

            else:
                LOGGER.warning("%s does not exist. %s will not be set.",
                               policy_path, role_name)
    if not roles:
        return None
    return roles


class ValidatorConfig:
    def __init__(self, bind_network=None, bind_component=None,
                 endpoint=None, peering=None, seeds=None,
                 peers=None, network_public_key=None,
                 network_private_key=None,
                 scheduler=None, permissions=None,
                 roles=None, opentsdb_url=None, opentsdb_db=None,
                 opentsdb_username=None, opentsdb_password=None,
                 minimum_peer_connectivity=None,
                 maximum_peer_connectivity=None):

        self._bind_network = bind_network
        self._bind_component = bind_component
        self._endpoint = endpoint
        self._peering = peering
        self._seeds = seeds
        self._peers = peers
        self._network_public_key = network_public_key
        self._network_private_key = network_private_key
        self._scheduler = scheduler
        self._permissions = permissions
        self._roles = roles
        self._opentsdb_url = opentsdb_url
        self._opentsdb_db = opentsdb_db
        self._opentsdb_username = opentsdb_username
        self._opentsdb_password = opentsdb_password
        self._minimum_peer_connectivity = minimum_peer_connectivity
        self._maximum_peer_connectivity = maximum_peer_connectivity

    @property
    def bind_network(self):
        return self._bind_network

    @property
    def bind_component(self):
        return self._bind_component

    @property
    def endpoint(self):
        return self._endpoint

    @property
    def peering(self):
        return self._peering

    @property
    def seeds(self):
        return self._seeds

    @property
    def peers(self):
        return self._peers

    @property
    def network_public_key(self):
        return self._network_public_key

    @property
    def network_private_key(self):
        return self._network_private_key

    @property
    def scheduler(self):
        return self._scheduler

    @property
    def permissions(self):
        return self._permissions

    @property
    def roles(self):
        return self._roles

    @property
    def opentsdb_url(self):
        return self._opentsdb_url

    @property
    def opentsdb_db(self):
        return self._opentsdb_db

    @property
    def opentsdb_username(self):
        return self._opentsdb_username

    @property
    def opentsdb_password(self):
        return self._opentsdb_password

    @property
    def minimum_peer_connectivity(self):
        return self._minimum_peer_connectivity

    @property
    def maximum_peer_connectivity(self):
        return self._maximum_peer_connectivity

    def __repr__(self):
        # not including  password for opentsdb
        return (
            "{}(bind_network={}, bind_component={}, "
            "endpoint={}, peering={}, seeds={}, peers={}, "
            "network_public_key={}, network_private_key={}, "
            "scheduler={}, permissions={}, roles={} "
            "opentsdb_url={}, opentsdb_db={}, opentsdb_username={}, "
            "minimum_peer_connectivity={}, maximum_peer_connectivity={})"
        ).format(
            self.__class__.__name__,
            repr(self._bind_network),
            repr(self._bind_component),
            repr(self._endpoint),
            repr(self._peering),
            repr(self._seeds),
            repr(self._peers),
            repr(self._network_public_key),
            repr(self._network_private_key),
            repr(self._scheduler),
            repr(self._permissions),
            repr(self._roles),
            repr(self._opentsdb_url),
            repr(self._opentsdb_db),
            repr(self._opentsdb_username),
            repr(self._minimum_peer_connectivity),
            repr(self._maximum_peer_connectivity))

    def to_dict(self):
        return collections.OrderedDict([
            ('bind_network', self._bind_network),
            ('bind_component', self._bind_component),
            ('endpoint', self._endpoint),
            ('peering', self._peering),
            ('seeds', self._seeds),
            ('peers', self._peers),
            ('network_public_key', self._network_public_key),
            ('network_private_key', self._network_private_key),
            ('scheduler', self._scheduler),
            ('permissions', self._permissions),
            ('roles', self._roles),
            ('opentsdb_url', self._opentsdb_url),
            ('opentsdb_db', self._opentsdb_db),
            ('opentsdb_username', self._opentsdb_username),
            ('opentsdb_password', self._opentsdb_password),
            ('minimum_peer_connectivity', self._minimum_peer_connectivity),
            ('maximum_peer_connectivity', self._maximum_peer_connectivity)
        ])

    def to_toml_string(self):
        return str(toml.dumps(self.to_dict())).strip().split('\n')
