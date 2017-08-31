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

from sawtooth_sdk.client.config import get_config_dir
from sawtooth_supplychain.rest_api.exceptions import RestApiConfigurationError


LOGGER = logging.getLogger(__name__)


def load_default_rest_api_config():
    """Returns a default configuration for the Supply Chain REST API.
    Args:
        None

    Returns:
        (:obj:`RestApiConfig`) - the default REST API configuration
    """
    return RestApiConfig(
        bind=['127.0.0.1:8000'],
        database_name='supplychain',
        database_host='localhost',
        database_port='5432')


def load_toml_rest_api_config(filename):
    """Returns a RestApiConfig created by loading a TOML file from the
    filesystem.

    Args:
        filename: the config file to load
    Returns:
        (:obj:`RestApiConfig`) - the REST API configuration
    """
    if not os.path.exists(filename):
        LOGGER.info(
            "Skipping rest api loading from non-existent config file: %s",
            filename)
        return RestApiConfig()

    LOGGER.info("Loading rest api information from config: %s", filename)

    try:
        with open(filename) as fd:
            raw_config = fd.read()
    except IOError as e:
        raise RestApiConfigurationError(
            "Unable to load rest api configuration file: {}".format(str(e)))

    toml_config = toml.loads(raw_config)

    invalid_keys = set(toml_config.keys()).difference(
        ['bind', 'database_name', 'database_host',
         'database_port', 'database_user', 'database_password'])
    if invalid_keys:
        raise RestApiConfigurationError(
            "Invalid keys in rest api config: {}".format(
                ", ".join(sorted(list(invalid_keys)))))

    database_port = None
    config_port_str = None
    try:
        config_port_str = toml_config.get('database_port', None)
        if config_port_str:
            database_port = int(config_port_str)
    except ValueError:
        raise RestApiConfigurationError(
            'Invalid database_port in rest api config: {}'.format(
                config_port_str))

    config = RestApiConfig(
        bind=toml_config.get("bind", None),
        database_name=toml_config.get('database_name', None),
        database_host=toml_config.get('database_host', None),
        database_port=database_port,
        database_user=toml_config.get('database_user', None),
        database_password=toml_config.get('database_password', None)
    )

    return config


def merge_rest_api_configs(configs):
    """
    Given a list of RestApiConfig objects, merges them into a single
    RestApiConfig, giving priority in the order of the configs (first has
    highest priority).

    Args:
        configs: a list of configs to merge
    Returns:
        (:obj:`RestApiConfig`) - the merged REST API configuration
    """
    bind = None
    database_name = None
    database_host = None
    database_port = None
    database_user = None
    database_password = None

    for config in reversed(configs):
        if config.bind is not None:
            bind = config.bind

        if config.database_name is not None:
            database_name = config.database_name

        if config.database_host is not None:
            database_host = config.database_host

        if config.database_port is not None:
            database_port = config.database_port

        if config.database_user is not None:
            database_user = config.database_user

        if config.database_password is not None:
            database_password = config.database_password

    return RestApiConfig(
        bind=bind,
        database_name=database_name,
        database_host=database_host,
        database_port=database_port,
        database_user=database_user,
        database_password=database_password)


def load_rest_api_config(first_config):
    """Loads the config from the config file and merges it with the given
    configuration.
    """
    default_config = load_default_rest_api_config()
    config_dir = get_config_dir()
    conf_file = os.path.join(config_dir, 'supplychain_rest_api.toml')

    toml_config = load_toml_rest_api_config(conf_file)
    return merge_rest_api_configs(
        configs=[first_config, toml_config, default_config])


class RestApiConfig:
    def __init__(self, bind=None, database_name=None,
                 database_host=None, database_port=None,
                 database_user=None, database_password=None):
        self._bind = bind
        self._database_name = database_name
        self._database_host = database_host
        self._database_port = database_port
        self._database_user = database_user
        self._database_password = database_password

    @property
    def bind(self):
        return self._bind

    @property
    def database_name(self):
        return self._database_name

    @property
    def database_host(self):
        return self._database_host

    @property
    def database_port(self):
        return self._database_port

    @property
    def database_user(self):
        return self._database_user

    @property
    def database_password(self):
        return self._database_password

    def __repr__(self):
        return \
            ("{}(bind={}, database_name={}, "
             "database_host={}, database_port={}, "
             "database_user={}, database_password={})").format(
                self.__class__.__name__,
                repr(self._bind),
                repr(self._database_name),
                repr(self._database_host),
                repr(self._database_port),
                repr(self._database_user),
                repr(self._database_password))

    def to_dict(self):
        return collections.OrderedDict([
            ('bind', self._bind),
            ('database_name', self._database_name),
            ('database_host', self._database_host),
            ('database_port', self._database_port),
            ('database_user', self._database_user),
            ('database_password', self._database_password)
        ])

    def to_toml_string(self):
        return str(toml.dumps(self.to_dict())).strip().split('\n')
