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
import os
import toml

from sawtooth_supplychain.rest_api.exceptions import RestApiConfigurationError


LOGGER = logging.getLogger(__name__)


def load_default_rest_api_config():
    """Returns a default configuration for the Supply Chain REST API.
    Args:
        None

    Returns:
        bind: the host and port for the api to run on
        connect: the url to connect to a running Validator
        timeout: seconds to wait for a validator response
        db_cnx: the database connection string
    """
    return RestApiConfig(
        bind=["127.0.0.1:8080"],
        connect="tcp://localhost:4004",
        timeout=300,
        db_cnx=("dbname='sc_rest_api' "
                "user='sc_rest_api' host='localhost' password='my_passwd'"))


def load_toml_rest_api_config(filename):
    """Returns a RestApiConfig created by loading a TOML file from the
    filesystem.

    Args:
        filename: the config file to load
    Returns:
        A configuration with following values:
        * bind
        * connect
        * timeout
        * db_cnx
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
        ['bind', 'connect', 'timeout', 'db_cnx'])
    if invalid_keys:
        raise RestApiConfigurationError(
            "Invalid keys in rest api config: {}".format(
                ", ".join(sorted(list(invalid_keys)))))
    config = RestApiConfig(
        bind=toml_config.get("bind", None),
        connect=toml_config.get('connect', None),
        timeout=toml_config.get('timeout', None),
        db_cnx=toml_config.get('db_cnx', None)
    )

    return config


def merge_rest_api_config(configs):
    """
    Given a list of PathConfig objects, merges them into a single PathConfig,
    giving priority in the order of the configs (first has highest priority).

    Args:
        configs: a list of configs to merge
    Returns:
        A single config with values:
            * bind
            * connect
            * timeout
            * db_cnx
    """
    bind = None
    connect = None
    timeout = None
    db_cnx = None

    for config in reversed(configs):
        if config.bind is not None:
            bind = config.bind
        if config.connect is not None:
            connect = config.connect
        if config.timeout is not None:
            timeout = config.timeout
        if config.db_cnx is not None:
            db_cnx = config.db_cnx

    return RestApiConfig(
        bind=bind,
        connect=connect,
        timeout=timeout,
        db_cnx=db_cnx)


class RestApiConfig:
    def __init__(self, bind=None, connect=None, timeout=None, db_cnx=None):
        self._bind = bind
        self._connect = connect
        self._timeout = timeout
        self._db_cnx = db_cnx

    @property
    def bind(self):
        return self._bind

    @property
    def connect(self):
        return self._connect

    @property
    def timeout(self):
        return self._timeout

    @property
    def db_cnx(self):
        return self._db_cnx

    def __repr__(self):
        return \
            "{}(bind={}, connect={}, timeout={}, db_cnx={})".format(
                self.__class__.__name__,
                repr(self._bind),
                repr(self._connect),
                repr(self._timeout),
                repr(self._db_cnx))
