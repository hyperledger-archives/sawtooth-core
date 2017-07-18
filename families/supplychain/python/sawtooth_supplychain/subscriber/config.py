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

from sawtooth_supplychain.subscriber.exceptions import \
    SubscriberConfigurationError


LOGGER = logging.getLogger(__name__)


def load_default_subscriber_config():
    return SubscriberConfig(
        connect='tcp://localhost:4004',
        database='dbname=supplychain host=localhost port=5432')


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
        ['connect', 'database'])
    if invalid_keys:
        raise SubscriberConfigurationError(
            'Invalid keys in subscriber config: {}'.format(
                ', '.join(sorted(list(invalid_keys)))))

    return SubscriberConfig(
        connect=toml_config.get('connect', None),
        database=toml_config.get('database', None)
    )


def merge_subscriber_configs(configs):
    """Given a list of SubscriberConfig objects, returns a single
    SubscriberConfig with the values merged.  Priority is in order of
    arguments, first to last.
    """
    connect = None
    database = None

    for config in reversed(configs):
        if config.connect is not None:
            connect = config.connect

        if config.database is not None:
            database = config.database

    return SubscriberConfig(
        connect=connect,
        database=database)


class SubscriberConfig:
    def __init__(self, connect=None, database=None):
        self._connect = connect
        self._database = database

    @property
    def connect(self):
        return self._connect

    @property
    def database(self):
        return self._database

    def __repr__(self):
        return \
            "{}(connect={}, database={})".format(
                self.__class__.__name__,
                repr(self._connect),
                repr(self._database))

    def to_dict(self):
        return collections.OrderedDict([
            ('connect', self._connect),
            ('database', self._database)
        ])

    def to_toml_string(self):
        return str(toml.dumps(self.to_dict())).strip().split('\n')
