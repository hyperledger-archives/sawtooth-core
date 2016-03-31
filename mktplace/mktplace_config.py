# Copyright 2016 Intel Corporation
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

import getpass
import os

import gossip.config
from gossip.config import AggregateConfig
from gossip.config import load_config_files


def get_mktplace_configuration(config_files,
                               options_config,
                               os_name=os.name,
                               config_files_required=True):
    env_config = MarketPlaceEnvConfig()

    default_config = MarketPlaceDefaultConfig(os_name=os_name)

    conf_dir = AggregateConfig(
        configs=[default_config, env_config, options_config]).resolve(
        {'home': 'CurrencyHome'})['ConfigDirectory']

    user_conf_dir = os.path.join(os.path.expanduser("~"), ".sawtooth")

    # Determine the configuration file search path
    search_path = [conf_dir, user_conf_dir, '.', os.path.join(
        os.path.dirname(__file__), "..", "etc")]

    file_configs = load_config_files(config_files, search_path,
                                     config_files_required)

    config_list = [default_config]
    config_list.extend(file_configs)
    config_list.append(env_config)
    config_list.append(options_config)

    cfg = AggregateConfig(configs=config_list)
    resolved = cfg.resolve({
        'home': 'CurrencyHome',
        'host': 'CurrencyHost',
        'node': 'NodeName',
        'base': 'BaseDirectory',
        'conf_dir': 'ConfigDirectory',
        'data_dir': 'DataDirectory',
        'log_dir': 'LogDirectory',
        'name': 'ParticipantName',
        'user': 'UserName',
        'user_conf_dir': 'UserConfigDirectory'
    })
    return resolved


class MarketPlaceDefaultConfig(gossip.config.Config):
    def __init__(self, os_name=os.name):
        super(MarketPlaceDefaultConfig, self).__init__(name="default")

        if 'CURRENCYHOME' in os.environ:
            self['ConfigDirectory'] = '{home}/etc'
            self['LogDirectory'] = '{home}/logs'
            self['DataDirectory'] = '{home}/data'
        elif os_name == 'nt':
            base_dir = 'C:\\Program Files (x86)\\Intel\\sawtooth-validator\\'
            self['ConfigDirectory'] = '{0}conf'.format(base_dir)
            self['LogDirectory'] = '{0}logs'.format(base_dir)
            self['DataDirectory'] = '{0}data'.format(base_dir)
        else:
            self['ConfigDirectory'] = '/etc/sawtooth-validator'
            self['LogDirectory'] = '/var/log/sawtooth-validator'
            self['DataDirectory'] = '/var/lib/sawtooth-validator'

        self['BaseDirectory'] = os.path.abspath(os.path.dirname(__file__))
        self['CurrencyHost'] = "localhost"
        self['UserConfigDirectory'] = os.path.join(
            os.path.expanduser("~"), ".sawtooth")
        try:
            self['User'] = getpass.getuser()
        except:
            # currently getpass is broken in the python 2.7 windows distro (pwd
            # module not found)
            if 'USERNAME' in os.environ:
                # get it from env instead.
                self['User'] = os.environ['USERNAME']


class MarketPlaceEnvConfig(gossip.config.EnvConfig):
    def __init__(self):
        super(MarketPlaceEnvConfig, self).__init__([
            ('CURRENCYHOME', 'CurrencyHome'),
            ('CURRENCY_CONF_DIR', 'ConfigDirectory'),
            ('CURRENCY_LOG_DIR', 'LogDirectory'),
            ('CURRENCY_DATA_DIR', 'DataDirectory'),
            ('HOSTNAME', 'CurrencyHost')
        ])
