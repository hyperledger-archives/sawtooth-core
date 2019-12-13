# Copyright 2018 Intel Corporation
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

from sawtooth_cli.network_command.parent_parsers import base_multinode_parser
from sawtooth_cli.network_command.parent_parsers import split_comma_append_args
from sawtooth_cli.network_command.parent_parsers import make_rest_apis

from sawtooth_cli.exceptions import CliException


DOT_FILE = 'peers.dot'


def add_peers_parser(subparsers, parent_parser):
    help_text = 'Shows the peering arrangment of a network'

    parser = subparsers.add_parser(
        'peers',
        help=help_text,
        description='{}.'.format(help_text))

    peers_parsers = parser.add_subparsers(
        title='subcommands',
        dest='peers_command')
    peers_parsers.required = True

    _add_list_parser(peers_parsers, parent_parser)
    _add_graph_parser(peers_parsers, parent_parser)


def _add_list_parser(parser, parent_parser):
    help_text = 'Lists peers for validators with given URLs'

    list_parser = parser.add_parser(
        'list',
        help=help_text,
        description='{}.'.format(help_text),
        parents=[parent_parser, base_multinode_parser()])

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
    urls = split_comma_append_args(args.urls)
    users = split_comma_append_args(args.users)
    clients = make_rest_apis(urls, users)

    print(
        json.dumps(
            _get_peer_endpoints(clients),
            sort_keys=True,
            indent=(4 if args.pretty else 0)
        )
    )


def _get_peer_endpoints(clients):
    statuses = [client.get_status() for client in clients]

    return {
        status['endpoint']: [
            peer['endpoint']
            for peer in status['peers']
        ]
        for status in statuses
    }


def _add_graph_parser(parser, parent_parser):
    help_text = "Generates a file to graph a network's peering arrangement"

    graph_parser = parser.add_parser(
        'graph',
        help=help_text,
        description='{}.'.format(help_text),
        parents=[parent_parser, base_multinode_parser()])

    graph_parser.add_argument(
        '-o', '--output',
        help='The path of the dot file to be produced (defaults to peers.dot)')

    graph_parser.add_argument(
        '--force',
        action='store_true',
        help='TODO')


def _do_peers_graph(args):
    urls = split_comma_append_args(args.urls)
    users = split_comma_append_args(args.users)
    clients = make_rest_apis(urls, users)

    status_dict = _get_peer_endpoints(clients)

    path = args.output if args.output else DOT_FILE

    if not args.force and os.path.isfile(path):
        raise CliException(
            '{} already exists; '
            'rerun with `--force` to overwrite'.format(path))

    with open(path, 'w') as dot:
        print(
            'strict graph peers {',
            file=dot)

        for node, peers in status_dict.items():
            for peer in peers:
                print(
                    '    "{}" -- "{}"'.format(node, peer),
                    file=dot)

        print(
            '}',
            file=dot)
