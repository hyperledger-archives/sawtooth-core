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


LOGGER = logging.getLogger(__name__)


def load_default_validator_config():
    return ValidatorConfig(
        bind_network='tcp://127.0.0.1:8800',
        bind_component='tcp://127.0.0.1:40000',
        endpoint=None,
        peering='static')


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
        ['bind', 'endpoint', 'peering', 'seeds', 'peers'])
    if len(invalid_keys) > 0:
        raise LocalConfigurationError(
            "Invalid keys in validator config: "
            "{}".format(", ".join(sorted(list(invalid_keys)))))
    bind_network = None
    bind_component = None
    for bind in toml_config.get("bind"):
        if "network" in bind:
            bind_network = bind[bind.find(":")+1:]
        if "component" in bind:
            bind_component = bind[bind.find(":")+1:]

    config = ValidatorConfig(
         bind_network=bind_network,
         bind_component=bind_component,
         endpoint=toml_config.get("endpoint", None),
         peering=toml_config.get("peering", None),
         seeds=toml_config.get("seeds", None),
         peers=toml_config.get("peers", None),
    )

    return config


def merge_validator_config(configs):
    """
    Given a list of ValidatorConfig object, merges them into a single
    ValidatorConfig, giving priority in the order of the configs
    (first has highest priority).
    """
    bind_network = None
    bind_component = None
    endpoint = None
    peering = None
    seeds = None
    peers = None

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

    return ValidatorConfig(
         bind_network=bind_network,
         bind_component=bind_component,
         endpoint=endpoint,
         peering=peering,
         seeds=seeds,
         peers=peers
    )


class ValidatorConfig:
    def __init__(self, bind_network=None, bind_component=None,
                 endpoint=None, peering=None, seeds=None,
                 peers=None):

        self._bind_network = bind_network
        self._bind_component = bind_component
        self._endpoint = endpoint
        self._peering = peering
        self._seeds = seeds
        self._peers = peers

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

    def __repr__(self):
        return \
            "{}(bind_network={}, bind_component={}, " \
            "endpoint={}, peering={}, seeds={}, peers={})".format(
                self.__class__.__name__,
                repr(self._bind_network),
                repr(self._bind_component),
                repr(self._endpoint),
                repr(self._peering),
                repr(self._seeds),
                repr(self._peers))

    def to_dict(self):
        return collections.OrderedDict([
            ('bind_network', self._bind_network),
            ('bind_component', self._bind_component),
            ('endpoint', self._endpoint),
            ('peering', self._peering),
            ('seeds', self._seeds),
            ('peers', self._peers)
        ])

    def to_toml_string(self):
        return toml.dumps(self.to_dict()).strip().split('\n')
