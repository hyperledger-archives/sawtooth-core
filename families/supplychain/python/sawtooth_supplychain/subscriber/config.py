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
from sawtooth_supplychain.subscriber.exceptions import \
    SubscriberConfigurationError


LOGGER = logging.getLogger(__name__)


def load_default_subscriber_config():
    return SubscriberConfig(
        connect='tcp://localhost:4004',
        database_name='supplychain',
        database_host='localhost',
        database_port=5432)


def load_toml_subscriber_config(filename):
    """Returns a SubscriberConfig create by loading a TOML file from the
    file system.

    Args:
        filename (str): the name of the .toml file

    Returns:
        (:obj:`SubscriberConfig`) - the subscriber configuration"""
    if not os.path.exists(filename):
        LOGGER.info(
            "Skipping loading from non-existent config file: %s",
            filename)
        return SubscriberConfig()

    LOGGER.info('Loading subscriber information from config: %s', filename)

    try:
        with open(filename) as config_file:
            raw_config = config_file.read()
    except IOError as e:
        raise SubscriberConfigurationError(
            'Unable to load subscriber configuration file: {}'.format(str(e)))

    toml_config = toml.loads(raw_config)

    invalid_keys = set(toml_config.keys()).difference(
        ['connect', 'database_name', 'database_host', 'database_port',
         'database_user', 'database_password'])
    if invalid_keys:
        raise SubscriberConfigurationError(
            'Invalid keys in subscriber config: {}'.format(
                ', '.join(sorted(list(invalid_keys)))))

    port = None
    port_str = toml_config.get('database_port', None)
    if port_str is not None:
        try:
            port = port_str
        except ValueError:
            raise SubscriberConfigurationError(
                '"database_port" must be valid port number')

    return SubscriberConfig(
        connect=toml_config.get('connect', None),
        database_name=toml_config.get('database_name', None),
        database_host=toml_config.get('database_host', None),
        database_port=port,
        database_user=toml_config.get('database_user', None),
        database_password=toml_config.get('database_password', None)
    )


def merge_subscriber_configs(configs):
    """Given a list of SubscriberConfig objects, returns a single
    SubscriberConfig with the values merged.  Priority is in order of
    arguments, first to last.
    """
    connect = None
    database_name = None
    database_host = None
    database_port = None
    database_user = None
    database_password = None

    for config in reversed(configs):
        if config.connect is not None:
            connect = config.connect

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

    return SubscriberConfig(
        connect=connect,
        database_name=database_name,
        database_host=database_host,
        database_port=database_port,
        database_user=database_user,
        database_password=database_password)


def load_subscriber_config(first_config):
    """Loads the config from the config file and merges it with the given
    configuration.
    """
    default_config = load_default_subscriber_config()
    config_dir = get_config_dir()
    conf_file = os.path.join(config_dir, 'supplychain_sds.toml')

    toml_config = load_toml_subscriber_config(conf_file)
    return merge_subscriber_configs(
        configs=[first_config, toml_config, default_config])


class SubscriberConfig:
    def __init__(self, connect=None, database_name=None,
                 database_host=None, database_port=None,
                 database_user=None, database_password=None):
        self._connect = connect
        self._database_name = database_name
        self._database_host = database_host
        self._database_port = database_port
        self._database_user = database_user
        self._database_password = database_password

    @property
    def connect(self):
        return self._connect

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
            ("{}(connect={}, database_name={}, "
             "database_host={}, database_port={}, "
             "database_user={}, database_password={})").format(
                self.__class__.__name__,
                repr(self._connect),
                repr(self._database_name),
                repr(self._database_host),
                repr(self._database_port),
                repr(self._database_user),
                repr(self._database_password))

    def to_dict(self):
        return collections.OrderedDict([
            ('connect', self._connect),
            ('database_name', self._database_name),
            ('database_host', self._database_host),
            ('database_port', self._database_port),
            ('database_user', self._database_user),
            ('database_password', self._database_password)
        ])

    def to_toml_string(self):
        return str(toml.dumps(self.to_dict())).strip().split('\n')
