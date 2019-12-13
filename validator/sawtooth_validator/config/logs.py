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
import os
import sys
import toml
import yaml


def _get_config_dir():
    """Returns the sawtooth configuration directory based on the
    SAWTOOTH_HOME environment variable (if set) or OS defaults.
    """
    if 'SAWTOOTH_HOME' in os.environ:
        return os.path.join(os.environ['SAWTOOTH_HOME'], 'etc')

    if os.name == 'nt':
        base_dir = \
            os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
        return os.path.join(base_dir, 'conf')

    return '/etc/sawtooth'


def _get_config():
    """Determines if there is a log config in the config directory
       and returns it. If it does not exist, return None.

    Returns:
        log_config (dict): The dictionary to pass to logging.config.dictConfig
    """
    conf_file = os.path.join(_get_config_dir(), 'log_config.toml')
    if os.path.exists(conf_file):
        with open(conf_file) as fd:
            raw_config = fd.read()
        log_config = toml.loads(raw_config)
        return log_config

    conf_file = os.path.join(_get_config_dir(), 'log_config.yaml')
    if os.path.exists(conf_file):
        with open(conf_file) as fd:
            raw_config = fd.read()
        log_config = yaml.safe_load(raw_config)
        return log_config

    return None


def get_log_config():
    """Returns the log config if it exists."""
    return _get_config()
