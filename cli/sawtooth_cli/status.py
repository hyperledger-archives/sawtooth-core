# Copyright 2018 Intel Corporation
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


def add_status_parser(subparsers, parent_parser):
    """Adds argument parser for the status command

        Args:
            subparsers: Add parsers to this subparser object
            parent_parser: The parent argparse.ArgumentParser object
    """
    parser = subparsers.add_parser(
        'status',
        help='Displays information about validator status',
        description="Provides a subcommand to show a validator\'s status")

    grand_parsers = parser.add_subparsers(title='subcommands',
                                          dest='subcommand')
    grand_parsers.required = True
    add_status_show_parser(grand_parsers, parent_parser)


def add_status_show_parser(subparsers, parent_parser):
    description = ('Displays information about the status of a validator.')

    subparsers.add_parser(
        'show',
        description=description,
        parents=[base_http_parser(), base_list_parser()])


def do_status(args):
    if args.subcommand == 'show':
        do_status_show(args)
    else:
        raise CliException('Invalid command: {}'.format(args.subcommand))


def do_status_show(args):
    rest_client = RestClient(base_url=args.url)
    status = rest_client.get_status()

    if args.format == 'csv' or args.format == 'default':
        print(status)

    elif args.format == 'json':
        fmt.print_json(status)

    elif args.format == 'yaml':
        fmt.print_yaml(status)
