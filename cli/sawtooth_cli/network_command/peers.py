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

import json
import shlex
import subprocess

from sawtooth_cli.exceptions import CliException


def add_peers_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'peers',
        help='TODO',
        description='TODO',
    )

    peers_parsers = parser.add_subparsers(
        title='subcommands',
        dest='peers_command')
    peers_parsers.required = True

    list_parser = peers_parsers.add_parser(
        'list',
        help='List peers for validators with given URLs',
        description=(
            'List peers for validators with given URLs separated by commas.'))

    list_parser.add_argument(
        'urls',
        nargs=1,
        help='the comma-separated URLs of the validators to be queried',
        type=str)

    list_parser.add_argument(
        '--pretty', '-p',
        action='store_true',
        help='Pretty-print the results')


def do_peers(args):
    if args.peers_command == 'list':
        do_peers_list(args)
    else:
        raise CliException('Invalid command: {}'.format(args.subcommand))


def do_peers_list(args):
    urls = args.urls[0].split(',')

    peer_dict = {
        url: _get_peers(url)
        for url in urls
    }

    print(
        json.dumps(
            peer_dict,
            sort_keys=True,
            indent=(4 if args.pretty else 0)
        )
    )


def _get_peers(url):
    peers = subprocess.check_output(
        shlex.split(
            'sawtooth peer list --url {}'.format(url))
    ).decode().strip().split(',')

    return peers
