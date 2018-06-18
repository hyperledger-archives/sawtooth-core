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
import os
import sys
import toml


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
