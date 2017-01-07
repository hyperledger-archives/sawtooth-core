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

from collections import namedtuple

import sawtooth.config
from sawtooth.config import AggregateConfig
from sawtooth.config import load_config_files


ListenListEntry = namedtuple('ListenListEntry', ['host', 'port', 'protocol'])
ListenData = namedtuple('ListenData', ['host', 'port'])


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
        cfg.update(parse_configuration_file(filename))

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
                                config_files_required=None):
    env_config = CurrencyEnvConfig()

    default_config = ValidatorDefaultConfig(os_name=os_name)

    conf_dir = get_config_directory(
        [default_config, env_config, options_config])

    # Determine the configuration file search path
    search_path = [conf_dir, '.', os.path.join(
        os.path.dirname(__file__), "..", "etc")]

    # Require the config files unless it is an empty list or the
    # default of txnvalidator.js.
    if config_files_required is None:
        config_files_required = len(config_files) != 0 and \
            not (len(config_files) == 1 and
                 config_files[0] == 'txnvalidator.js')

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


__IPV4_REGEX = \
    r'(?:(?:\d|[1-9]\d|1\d{2}|2[0-4]\d|25[0-5])\.){3}' \
    r'(?:\d|[1-9]\d|1[0-9]{2}|2[0-4]\d|25[0-5])'
__HOST_NAME_REGEX = \
    r'localhost|(?:(?:[a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])' \
    r'(?:\.(?:[a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9]))+)'
__PORT_REGEX = \
    r'[0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|' \
    r'655[0-2][0-9]|6553[0-5]'
__TRANSPORT_REGEX = r'UDP|TCP'
__PROTOCOL_REGEX = r'gossip|http'
__FULL_REGEX = \
    r'^(?:(?P<host>{0}|{1})(?::))?(?P<port>{2})(?:(?:/)(?P<transport>{3}))' \
    r'?\s+(?P<protocol>{4})$'.format(
        __IPV4_REGEX,
        __HOST_NAME_REGEX,
        __PORT_REGEX,
        __TRANSPORT_REGEX,
        __PROTOCOL_REGEX)
__LISTEN_REGEX = re.compile(__FULL_REGEX)


def _parse_listen_directive(value):
    """
    An internal helper that parses a listen entry, checks for validity,
    and fills in defaults for missing values.

    Args:
        value: A listen string that is expected to be in the form
         "[IP_OR_HOST_NAME:]PORT[/TRANSPORT] PROTOCOL"

    Returns:
        A named tuple of (host, port, protocol)
    """

    # Beat the string senseless using a regex.  If there is not a match, then
    # it is malformed
    match = __LISTEN_REGEX.match(value)
    if match is None:
        raise Exception('listen directive "{}" is malformed'.format(value))

    # Extract the pieces of data we need.  Note that for optional pieces
    # host and transport, missing values will be None.  For a missing host
    # value, we will provide 0.0.0.0, which basically means listen on all
    # interfaces.
    host = match.group('host')
    if host is None:
        host = '0.0.0.0'
    port = int(match.group('port'))
    transport = match.group('transport')
    protocol = match.group('protocol')

    # Make sure that if there is a transport that it matches the protocol
    if transport is not None:
        if protocol == 'gossip' and transport != 'UDP':
            raise Exception('gossip listen directive requires UDP')
        if protocol == 'http' and transport != 'TCP':
            raise Exception('http listen directive requires TCP')

    # For HTTP, we don't allow listening on an ephemeral port
    if protocol == 'http' and port == 0:
        raise Exception('http listen directive requires non-zero port')

    return ListenListEntry(
        host=host,
        port=port,
        protocol=protocol)


def parse_listen_directives(listen_info):
    """
    From the configuration object, parses the list of entries for "Listen"
    and returns a dictionary of mapping from protocol to address/hostname
    and port.

    Args:
        config: The object holding validator configuration

    Returns:
        A dictionary mapping a protocol name to a ListenData named tuple.
    """

    listen_mapping = {}

    # First try to parse the "Listen" entries if one exists
    if listen_info is not None:
        for value in listen_info:
            directive = _parse_listen_directive(value)

            # No duplicates for protocols allowed
            if directive.protocol in listen_mapping:
                raise Exception(
                    'configuration has more than one {0} listen '
                    'directive'.format(directive.protocol))

            listen_mapping[directive.protocol] = \
                ListenData(host=directive.host, port=directive.port)

        # If there was no gossip listen directive, then flag an error
        if 'gossip' not in listen_mapping:
            raise Exception('configuration requires gossip listen directive')

    # Otherwise, we are going to set defaults for both gossip and HTTP
    else:
        listen_mapping['gossip'] = ListenData(host='0.0.0.0', port=5500)
        listen_mapping['http'] = ListenData(host='0.0.0.0', port=8800)

    return listen_mapping


class ValidatorDefaultConfig(sawtooth.config.Config):
    def __init__(self, os_name=os.name):
        super(ValidatorDefaultConfig, self).__init__(name="default")

        # file paths for validator data and process information
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

        # validator identity
        self['NodeName'] = "base000"
        self['KeyFile'] = '{key_dir}/{node}.wif'

        # validator network exposure
        self["Listen"] = [
            "localhost:0/UDP gossip",
            "localhost:8800/TCP http"
        ]
        # publicly-visible endpoint information if validator is behind NAT
        # self["Endpoint"] = {
        #     "Host" : "localhost",
        #     "Port" : 5500,
        #     "HttpPort" : 8800
        # }
        self['Endpoint'] = None

        # network flow control
        self['NetworkFlowRate'] = 96000
        self['NetworkBurstRate'] = 128000
        self['NetworkDelayRange'] = [0.00, 0.10]
        self['UseFixedDelay'] = True

        # startup options
        self['LedgerURL'] = 'http://localhost:8800/'

        # topological configuration
        self['TopologyAlgorithm'] = 'RandomWalk'
        self['InitialConnectivity'] = 0
        self['TargetConnectivity'] = 3
        self['MaximumConnectivity'] = 15
        self['MinimumConnectivity'] = 1

        # concrete topologic specification
        # Nodes specifies apriori validators for e.g. fixed topologies, e.g:
        # self['Nodes'] = [
        #     {
        #         'NodeName': <a validator's name>,
        #         'Identity': <said validator's public key>,
        #         'Host': <said validator's hostname>,
        #         'Port': <said validator's gossip/udp port>,
        #         'HttpPort': <said validator's web api port>,
        #     },
        # ]
        self['Nodes'] = []
        # Peers specifies peers from Nodes (above) by validator name, e.g.:
        # self['Peers'] = [<a validator's name>, ]
        self["Peers"] = []

        # PoET wait time certificates
        self['CertificateSampleLength'] = 30
        # the values TargetWaitTime and InitialWaitTime are a function of
        # network size.  The defaults of 5.0, 5.0 are geared toward very small
        # developer networks.  A larger network of n nodes might use 30.0 for
        # TargetWaitTime, and then set InitialWaitTime to n * TargetWaitTime
        self['TargetWaitTime'] = 5.0
        self['InitialWaitTime'] = 5.0

        # ledger type (PoET default)
        self['LedgerType'] = 'poet0'

        # block-chain transaction limits
        self['MinTransactionsPerBlock'] = 1
        self['MaxTransactionsPerBlock'] = 1000

        # transaction families
        self['TransactionFamilies'] = [
            'ledger.transaction.integer_key'
        ]

        # public key allowed to send shutdown messages
        self['AdministrationNode'] = None

        # R&D options
        self['Profile'] = True

        # legacy settings
        self['CurrencyHost'] = "localhost"

        # security settings
        self['CheckElevated'] = False


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
