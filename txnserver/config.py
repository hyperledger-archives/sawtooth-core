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

import json
import os
import re
import sys
import warnings

import sawtooth.config
from sawtooth.config import AggregateConfig
from sawtooth.config import load_config_files


def parse_configuration_files(cfiles, search_path):
    cfg = {}
    files_found = []
    files_not_found = []

    for cfile in cfiles:
        filename = None
        for directory in search_path:
            if os.path.isfile(os.path.join(directory, cfile)):
                filename = os.path.join(directory, cfile)
                break

        if filename is None:
            files_not_found.append(cfile)
        else:
            files_found.append(filename)

    if len(files_not_found) > 0:
        warnings.warn(
            "Unable to locate the following configuration files: "
            "{0} (search path: {1})".format(
                ", ".join(files_not_found),
                ", ".join([os.path.realpath(d) for d in search_path])))
        sys.exit(-1)

    for filename in files_found:
        try:
            cfg.update(parse_configuration_file(filename))
        except IOError as detail:
            warnings.warn("Error parsing configuration file %s; IO error %s" %
                          (filename, str(detail)))
            sys.exit(-1)
        except ValueError as detail:
            warnings.warn("Error parsing configuration file %s; value error %s"
                          % (filename, str(detail)))
            sys.exit(-1)
        except NameError as detail:
            warnings.warn("Error parsing configuration file %s; name error %s"
                          % (filename, str(detail)))
            sys.exit(-1)
        except:
            warnings.warn('Error parsing configuration file %s; %s' %
                          (filename, sys.exc_info()[0]))
            sys.exit(-1)

    return cfg


def parse_configuration_file(filename):
    cpattern = re.compile('##.*$')

    with open(filename) as fp:
        lines = fp.readlines()

    text = ""
    for line in lines:
        text += re.sub(cpattern, '', line) + ' '

    return json.loads(text)


def get_config_directory(configs):
    agg = AggregateConfig(configs=configs)

    for key in agg.keys():
        if key not in ['CurrencyHome', 'ConfigDirectory']:
            del agg[key]

    return agg.resolve({'home': 'CurrencyHome'})['ConfigDirectory']


def get_validator_configuration(config_files,
                                options_config,
                                os_name=os.name,
                                config_files_required=True):
    env_config = CurrencyEnvConfig()

    default_config = ValidatorDefaultConfig(os_name=os_name)

    conf_dir = get_config_directory(
        [default_config, env_config, options_config])

    # Determine the configuration file search path
    search_path = [conf_dir, '.', os.path.join(
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
        'key_dir': 'KeyDirectory',
        'run_dir': 'RunDirectory'
    })
    return resolved


class ValidatorDefaultConfig(sawtooth.config.Config):
    def __init__(self, os_name=os.name):
        super(ValidatorDefaultConfig, self).__init__(name="default")

        if 'CURRENCYHOME' in os.environ:
            self['ConfigDirectory'] = '{home}/etc'
            self['LogDirectory'] = '{home}/logs'
            self['DataDirectory'] = '{home}/data'
            self['KeyDirectory'] = '{home}/keys'
            self['RunDirectory'] = '{home}/run'
            self['PidFile'] = '{run_dir}/{node}.pid'
        elif os_name == 'nt':
            base_dir = 'C:\\Program Files (x86)\\Intel\\sawtooth-validator\\'
            self['ConfigDirectory'] = '{0}conf'.format(base_dir)
            self['LogDirectory'] = '{0}logs'.format(base_dir)
            self['DataDirectory'] = '{0}data'.format(base_dir)
            self['KeyDirectory'] = '{0}conf\\keys'.format(base_dir)
            self['RunDirectory'] = '{0}\\run'.format(base_dir)
        else:
            self['ConfigDirectory'] = '/etc/sawtooth-validator'
            self['LogDirectory'] = '/var/log/sawtooth-validator'
            self['DataDirectory'] = '/var/lib/sawtooth-validator'
            self['KeyDirectory'] = '/etc/sawtooth-validator/keys'
            self['RunDirectory'] = '/var/run/sawtooth-validator'
            self['PidFile'] = '{run_dir}/{node}.pid'

        self['BaseDirectory'] = os.path.abspath(os.path.dirname(__file__))
        self['CurrencyHost'] = "localhost"
        self['NodeName'] = "base000"


class CurrencyEnvConfig(sawtooth.config.EnvConfig):
    def __init__(self):
        super(CurrencyEnvConfig, self).__init__([
            ('CURRENCYHOME', 'CurrencyHome'),
            ('CURRENCY_CONF_DIR', 'ConfigDirectory'),
            ('CURRENCY_LOG_DIR', 'LogDirectory'),
            ('CURRENCY_DATA_DIR', 'DataDirectory'),
            ('CURRENCY_RUN_DIR', 'RunDirectory'),
            ('HOSTNAME', 'CurrencyHost')
        ])
