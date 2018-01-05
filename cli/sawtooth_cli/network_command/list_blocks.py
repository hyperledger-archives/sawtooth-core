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
import argparse

from sawtooth_cli.network_command.parent_parsers import base_multinode_parser
from sawtooth_cli.network_command.parent_parsers import split_comma_append_args
from sawtooth_cli.network_command.parent_parsers import make_rest_apis
from sawtooth_cli.network_command.fork_graph import SimpleBlock


def add_list_blocks_parser(subparsers, parent_parser):
    """Creates the arg parsers needed for the compare command.
    """
    parser = subparsers.add_parser(
        'list-blocks',
        help='List blocks from different nodes.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='',
        parents=[parent_parser, base_multinode_parser()])

    parser.add_argument(
        '-n',
        '--count',
        default=10,
        type=int,
        help='the number of blocks to list')


def do_list_blocks(args):
    urls = split_comma_append_args(args.urls)
    users = split_comma_append_args(args.users)
    clients = make_rest_apis(urls, users)
    block_lists = list(map(list_blocks, clients))
    for node, block_list in enumerate(block_lists):
        print("-- NODE %d --" % node)
        print("HEIGHT ID PREVIOUS")
        for _ in range(args.count):
            try:
                block = next(block_list)
                print_block(block)
            except StopIteration:
                break
        print()


def list_blocks(client):
    return map(SimpleBlock.from_block_dict, client.list_blocks(limit=10))


def print_block(block):
    print("%d %s %s" % (block.num, block.ident[:8], block.previous[:8]))
