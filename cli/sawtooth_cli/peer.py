# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the 'License');
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

from sawtooth_cli import format_utils as fmt
from sawtooth_cli.rest_client import RestClient
from sawtooth_cli.exceptions import CliException
from sawtooth_cli.parent_parsers import base_http_parser
from sawtooth_cli.parent_parsers import base_list_parser


def add_peer_parser(subparsers, parent_parser):
    """Adds argument parser for the peer command

        Args:
            subparsers: Add parsers to this subparser object
            parent_parser: The parent argparse.ArgumentParser object
    """
    parser = subparsers.add_parser(
        'peer',
        help='Displays information about validator peers',
        description="Provides a subcommand to list a validator's peers")

    grand_parsers = parser.add_subparsers(title='subcommands',
                                          dest='subcommand')
    grand_parsers.required = True
    add_peer_list_parser(grand_parsers, parent_parser)


def add_peer_list_parser(subparsers, parent_parser):
    description = (
        'Displays the addresses of the validators with which '
        'a specified validator is peered.')

    subparsers.add_parser(
        'list',
        description=description,
        parents=[base_http_parser(), base_list_parser()])


def do_peer(args):
    if args.subcommand == 'list':
        do_peer_list(args)

    else:
        raise CliException('Invalid command: {}'.format(args.subcommand))


def do_peer_list(args):
    rest_client = RestClient(base_url=args.url)
    peers = sorted(rest_client.list_peers())

    if args.format == 'csv' or args.format == 'default':
        print(','.join(peers))

    elif args.format == 'json':
        fmt.print_json(peers)

    elif args.format == 'yaml':
        fmt.print_yaml(peers)
