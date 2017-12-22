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

    _add_list_parser(peers_parsers)
    _add_graph_parser(peers_parsers)


def _add_list_parser(parser):
    list_parser = parser.add_parser(
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
        _do_peers_list(args)
    elif args.peers_command == 'graph':
        _do_peers_graph(args)
    else:
        raise CliException('Invalid command: {}'.format(args.subcommand))


def _do_peers_list(args):
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


def _add_graph_parser(parser):
    graph_parser = parser.add_parser(
        'graph',
        help='TODO',
        description='TODO')

    graph_parser.add_argument(
        'urls',
        nargs=1,
        type=str,
        help='TODO')

    graph_parser.add_argument(
        '--force',
        action='store_true',
        help='TODO')

    graph_parser.add_argument(
        '--png',
        action='store_true',
        help='TODO')


def _do_peers_graph(args):
    urls = args.urls[0].split(',')

    peer_dict = {
        url: _get_peers(url)
        for url in urls
    }

    dot_file = 'peers.dot'
    png_file = 'peers.png'

    if not args.force and os.path.isfile(dot_file):
        raise CliException(
            '{} already exists; '
            'rerun with `--force` to overwrite'.format(dot_file))

    with open(dot_file, 'w') as dot:
        print('strict graph peers {', file=dot)
        for node, peers in peer_dict.items():
            for peer in peers:
                print('    "{}" -- "{}"'.format(node, peer),
                      file=dot)
        print('}', file=dot)

    if args.png:
        subprocess.run(
            shlex.split(
                'dot -Tpng {} -o {}'.format(
                    dot_file,
                    png_file)))
