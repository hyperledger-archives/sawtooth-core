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

from base64 import b64decode
import csv
import hashlib
import json
import sys

import yaml

from sawtooth_cli.exceptions import CliException
from sawtooth_cli.rest_client import RestClient
from sawtooth_cli import tty

from sawtooth_cli.protobuf.setting_pb2 import Setting


SETTINGS_NAMESPACE = '000000'

_MIN_PRINT_WIDTH = 15
_MAX_KEY_PARTS = 4
_ADDRESS_PART_SIZE = 16


def add_settings_parser(subparsers, parent_parser):
    """Creates the args parser needed for the settings command and its
    subcommands.
    """
    # The following parser is for the settings subsection of commands.  These
    # commands display information about the currently applied on-chain
    # settings.

    settings_parser = subparsers.add_parser(
        'settings',
        help='Displays on-chain settings',
        description='Displays the values of currently active on-chain '
                    'settings.')

    settings_parsers = settings_parser.add_subparsers(
        title='settings',
        dest='settings_cmd')
    settings_parsers.required = True

    list_parser = settings_parsers.add_parser(
        'list',
        help='Lists the current keys and values of on-chain settings',
        description='List the current keys and values of on-chain '
                    'settings. The content can be exported to various '
                    'formats for external consumption.'
    )

    list_parser.add_argument(
        '--url',
        type=str,
        help="identify the URL of a validator's REST API",
        default='http://localhost:8008')

    list_parser.add_argument(
        '--filter',
        type=str,
        default='',
        help='filters keys that begin with this value')

    list_parser.add_argument(
        '--format',
        default='default',
        choices=['default', 'csv', 'json', 'yaml'],
        help='choose the output format')


def do_settings(args):
    if args.settings_cmd == 'list':
        _do_settings_list(args)
    else:
        raise AssertionError('Invalid subcommand: ')


def _do_settings_list(args):
    """Lists the current on-chain configuration values.
    """
    rest_client = RestClient(args.url)
    state = rest_client.list_state(subtree=SETTINGS_NAMESPACE)

    prefix = args.filter

    head = state['head']
    state_values = state['data']
    printable_settings = []
    proposals_address = _key_to_address('sawtooth.settings.vote.proposals')
    for state_value in state_values:
        if state_value['address'] == proposals_address:
            # This is completely internal setting and we won't list it here
            continue

        decoded = b64decode(state_value['data'])
        setting = Setting()
        setting.ParseFromString(decoded)

        for entry in setting.entries:
            if entry.key.startswith(prefix):
                printable_settings.append(entry)

    printable_settings.sort(key=lambda s: s.key)

    if args.format == 'default':
        tty_width = tty.width()
        for setting in printable_settings:
            # Set value width to the available terminal space, or the min width
            width = tty_width - len(setting.key) - 3
            width = width if width > _MIN_PRINT_WIDTH else _MIN_PRINT_WIDTH
            value = (setting.value[:width] + '...'
                     if len(setting.value) > width
                     else setting.value)
            print('{}: {}'.format(setting.key, value))
    elif args.format == 'csv':
        try:
            writer = csv.writer(sys.stdout, quoting=csv.QUOTE_ALL)
            writer.writerow(['KEY', 'VALUE'])
            for setting in printable_settings:
                writer.writerow([setting.key, setting.value])
        except csv.Error:
            raise CliException('Error writing CSV')
    elif args.format == 'json' or args.format == 'yaml':
        settings_snapshot = {
            'head': head,
            'settings': {setting.key: setting.value
                         for setting in printable_settings}
        }
        if args.format == 'json':
            print(json.dumps(settings_snapshot, indent=2, sort_keys=True))
        else:
            print(yaml.dump(settings_snapshot, default_flow_style=False)[0:-1])
    else:
        raise AssertionError('Unknown format {}'.format(args.format))


def _key_to_address(key):
    """Creates the state address for a given setting key.
    """
    key_parts = key.split('.', maxsplit=_MAX_KEY_PARTS - 1)
    key_parts.extend([''] * (_MAX_KEY_PARTS - len(key_parts)))

    return SETTINGS_NAMESPACE + ''.join(_short_hash(x) for x in key_parts)


def _short_hash(in_str):
    return hashlib.sha256(in_str.encode()).hexdigest()[:_ADDRESS_PART_SIZE]
