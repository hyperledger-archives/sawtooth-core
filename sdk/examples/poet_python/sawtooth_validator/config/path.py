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
import sys

import toml

from sawtooth_validator.exceptions import LocalConfigurationError


LOGGER = logging.getLogger(__name__)


def get_default_path_config():
    """Returns the default PathConfig as calculated based on SAWTOOTH_HOME
    (if set) and operating system.
    """
    if 'SAWTOOTH_HOME' in os.environ:
        home_dir = os.environ['SAWTOOTH_HOME']
        return PathConfig(
            config_dir=os.path.join(home_dir, 'etc'),
            log_dir=os.path.join(home_dir, 'logs'),
            data_dir=os.path.join(home_dir, 'data'),
            key_dir=os.path.join(home_dir, 'keys'),
            policy_dir=os.path.join(home_dir, 'policy'))

    if os.name == 'nt':
        # Paths appropriate for Windows.
        base_dir = \
            os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
        return PathConfig(
            config_dir=os.path.join(base_dir, 'conf'),
            log_dir=os.path.join(base_dir, 'logs'),
            data_dir=os.path.join(base_dir, 'data'),
            key_dir=os.path.join(base_dir, 'conf', 'keys'),
            policy_dir=os.path.join(base_dir, 'policy'))

    # Paths appropriate for modern Linux distributions.
    return PathConfig(
        config_dir='/etc/sawtooth',
        log_dir='/var/log/sawtooth',
        data_dir='/var/lib/sawtooth',
        key_dir='/etc/sawtooth/keys',
        policy_dir='/etc/sawtooth/policy')


def load_toml_path_config(filename):
    """Returns a PathConfig created by loading a TOML file from the
    filesystem.
    """
    if not os.path.exists(filename):
        LOGGER.info(
            "Skipping path loading from non-existent config file: %s",
            filename)
        return PathConfig()

    LOGGER.info("Loading path information from config: %s", filename)

    try:
        with open(filename) as fd:
            raw_config = fd.read()
    except IOError as e:
        raise LocalConfigurationError(
            "Unable to load path configuration file: {}".format(str(e)))

    toml_config = toml.loads(raw_config)

    invalid_keys = set(toml_config.keys()).difference(
        ['data_dir', 'key_dir', 'log_dir', 'policy_dir'])
    if invalid_keys:
        raise LocalConfigurationError("Invalid keys in path config: {}".format(
            ", ".join(sorted(list(invalid_keys)))))

    config = PathConfig(
        config_dir=None,
        data_dir=toml_config.get('data_dir', None),
        key_dir=toml_config.get('key_dir', None),
        log_dir=toml_config.get('log_dir', None),
        policy_dir=toml_config.get('policy_dir', None)
    )

    return config


def merge_path_config(configs, config_dir_override):
    """
    Given a list of PathConfig objects, merges them into a single PathConfig,
    giving priority in the order of the configs (first has highest priority).
    """
    config_dir = None
    log_dir = None
    data_dir = None
    key_dir = None
    policy_dir = None

    for config in reversed(configs):
        if config.config_dir is not None:
            config_dir = config.config_dir
        if config.log_dir is not None:
            log_dir = config.log_dir
        if config.data_dir is not None:
            data_dir = config.data_dir
        if config.key_dir is not None:
            key_dir = config.key_dir
        if config.policy_dir is not None:
            policy_dir = config.policy_dir

    if config_dir_override is not None:
        config_dir = config_dir_override

    return PathConfig(
        config_dir=config_dir,
        log_dir=log_dir,
        data_dir=data_dir,
        key_dir=key_dir,
        policy_dir=policy_dir)


def load_path_config(config_dir=None):
    default_config = get_default_path_config()

    if config_dir is None:
        conf_file = os.path.join(default_config.config_dir, 'path.toml')
    else:
        conf_file = os.path.join(config_dir, 'path.toml')

    toml_config = load_toml_path_config(conf_file)

    return merge_path_config(configs=[toml_config, default_config],
                             config_dir_override=config_dir)


class PathConfig:
    def __init__(self, config_dir=None, log_dir=None, data_dir=None,
                 key_dir=None, policy_dir=None):

        self._config_dir = config_dir
        self._log_dir = log_dir
        self._data_dir = data_dir
        self._key_dir = key_dir
        self._policy_dir = policy_dir

    @property
    def config_dir(self):
        return self._config_dir

    @property
    def log_dir(self):
        return self._log_dir

    @property
    def data_dir(self):
        return self._data_dir

    @property
    def key_dir(self):
        return self._key_dir

    @property
    def policy_dir(self):
        return self._policy_dir

    def __repr__(self):
        return \
            "{}(config_dir={}, log_dir={}, data_dir={}, key_dir={}," \
            " policy_dir={})".format(
                self.__class__.__name__,
                repr(self._config_dir),
                repr(self._log_dir),
                repr(self._data_dir),
                repr(self._key_dir),
                repr(self._policy_dir))

    def to_dict(self):
        return collections.OrderedDict([
            ('config_dir', self._config_dir),
            ('key_dir', self._key_dir),
            ('data_dir', self._data_dir),
            ('log_dir', self._log_dir),
            ('policy_dir', self._policy_dir)
        ])

    def to_toml_string(self):
        return str(toml.dumps(self.to_dict())).strip().split('\n')
