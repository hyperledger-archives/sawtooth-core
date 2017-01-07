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

from __future__ import print_function

import csv
import json
import sys
import yaml

from gossip.common import pretty_print_dict
from sawtooth.client import SawtoothClient
from sawtooth.exceptions import MessageException
from sawtooth.cli.exceptions import CliException


def add_block_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('block')

    grand_parsers = parser.add_subparsers(title='grandchildcommands',
                                          dest='subcommand')

    epilog = '''
    details:
      list the committed block IDs from the newest to the oldest.
    '''

    list_parser = grand_parsers.add_parser('list', epilog=epilog)
    list_parser.add_argument(
        '--url',
        type=str,
        help='the URL to the validator')
    list_parser.add_argument(
        '--blockcount',
        type=int,
        default=None,
        help='the maximum number of committed block IDs to list. Default: all')
    list_parser.add_argument(
        '--format',
        action='store',
        default='default',
        help='the format of the output. Options: csv, json or yaml.')

    epilog = '''
    details:
      show the contents of block or the value associated with key
      within the block.
    '''
    show_parser = grand_parsers.add_parser('show', epilog=epilog)
    show_parser.add_argument(
        'blockID',
        type=str,
        help='the id of the block')
    show_parser.add_argument(
        '-k', '--key',
        type=str,
        help='the key within the block')
    show_parser.add_argument(
        '--url',
        type=str,
        help='the URL to the validator')


def do_block(args):
    subcommands = ['list', 'show']
    if args.subcommand not in subcommands:
        print('Unknown sub-command, expecting one of {0}'.format(
            subcommands))
        return

    if args.url is not None:
        url = args.url
    else:
        url = 'http://localhost:8800'

    web_client = SawtoothClient(url)

    try:
        if args.subcommand == 'list':
            if args.blockcount is None:
                blockids = web_client.get_block_list()
            else:
                blockids = web_client.get_block_list(count=args.blockcount)

            if args.format == 'default':
                print('{:6} {:20} {:4} {:10} {:10} {:50}'.format(
                    'NUM', 'BLOCK', 'TXNS', 'DURATION', 'LOCALMEAN',
                    'VALIDATOR'))

                for block_id in blockids:
                    block_num, blockid, txns, duration, local_mean,\
                        validator_dest = get_block_info(web_client, block_id)
                    print('{:6} {:20} {:4} {:10} {:10} {:50}'.format(
                        block_num, blockid, txns, duration, local_mean,
                        validator_dest))

            elif args.format == 'csv':
                try:
                    writer = csv.writer(sys.stdout)
                    writer.writerow(
                        (
                            'NUM', 'BLOCK', 'TXNS', 'DURATION',
                            'LOCALMEAN', 'VALIDATOR'))
                    for block_id in blockids:
                        writer.writerow(
                            (get_block_info(web_client, block_id)))
                except csv.Error:
                    raise CliException('Error writing CSV.')

            elif args.format == 'json' or args.format == 'yaml':
                json_dict = []
                for block_id in blockids:
                    block_num, blockid, txns, duration, local_mean,\
                        validator_dest = get_block_info(web_client, block_id)
                    json_block = {
                        'NUM': block_num, 'BLOCK': blockid,
                        'TXNS': txns, 'DURATION': duration,
                        'LOCALMEAN': local_mean, 'VALIDATOR': validator_dest}
                    json_dict.append(json_block)

                if args.format == 'json':
                    print(json.dumps(json_dict))
                else:
                    print(yaml.dump(json_dict, default_flow_style=False))

            else:
                raise CliException(
                    "unknown format option: {}".format(args.format))

        elif args.subcommand == 'show':
            block_info = \
                web_client.get_block(
                    block_id=args.blockID,
                    field=args.key)
            print(pretty_print_dict(block_info))
            return

    except MessageException as e:
        raise CliException(e)


def get_block_info(web_client, block_id):
    block_info = web_client.get_block(block_id)
    serialized_cert = json.loads(
        block_info["WaitCertificate"]["SerializedCert"])
    block_num = str(block_info["BlockNum"])
    txns = str(len(block_info["TransactionIDs"]))
    duration = str(serialized_cert["Duration"])
    local_mean = str(serialized_cert["LocalMean"])
    validator_dest = str(serialized_cert["ValidatorAddress"])

    return block_num, str(block_id), txns, duration, local_mean, validator_dest
