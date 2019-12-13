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


LOGGER = logging.getLogger(__name__)


def _load_default_cli_config():
    return {
        'url': 'http://localhost:8008'
    }


def load_cli_config(args):
    """Modifies ARGS in-place to have the attributes defined in the CLI
    config file if it doesn't already have them. Certain default
    values are given if they are not in ARGS or the config file.
    """
    default_cli_config = _load_default_cli_config()
    toml_config = _load_toml_cli_config()

    for config in (toml_config, default_cli_config):
        for key, val in config.items():
            if key in args and getattr(args, key) is not None:
                pass
            else:
                setattr(args, key, val)


class CliConfigurationError(Exception):
    pass


def _load_toml_cli_config(filename=None):
    if filename is None:
        filename = os.path.join(
            _get_config_dir(),
            'cli.toml')

    if not os.path.exists(filename):
        LOGGER.info(
            "Skipping CLI config loading from non-existent config file: %s",
            filename)

        return {}

    LOGGER.info("Loading CLI information from config: %s", filename)

    try:
        with open(filename) as fd:
            raw_config = fd.read()
    except IOError as e:
        raise CliConfigurationError(
            "Unable to load CLI configuration file: {}".format(str(e)))

    return toml.loads(raw_config)


def _get_config_dir():
    if 'SAWTOOTH_HOME' in os.environ:
        return os.path.join(os.environ['SAWTOOTH_HOME'], 'etc')

    return '/etc/sawtooth'
