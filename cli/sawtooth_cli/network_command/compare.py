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
from math import floor, log

from sawtooth_cli.network_command.parent_parsers import base_multinode_parser
from sawtooth_cli.network_command.parent_parsers import split_comma_append_args
from sawtooth_cli.network_command.parent_parsers import make_rest_apis
from sawtooth_cli.network_command.fork_graph import ForkGraph
from sawtooth_cli.network_command.fork_graph import SimpleBlock


def add_compare_chains_parser(subparsers, parent_parser):
    """Creates the arg parsers needed for the compare command.
    """
    parser = subparsers.add_parser(
        'compare-chains',
        help='Compare chains from different nodes.',
        description=(
            'Compute and display information about how the chains at '
            'different nodes differ.'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
By default, prints a table of summary data and a table of per-node data with
the following fields. Pass --tree for a fork graph.

COMMON ANCESTOR
    The most recent block that all chains have in common.

COMMON HEIGHT
    Let min_height := the minimum height of any chain across all nodes passed
    in. COMMON HEIGHT = min_height.

HEAD
    The block id of the most recent block on a given chain.

HEIGHT
    The block number of the most recent block on a given chain.

LAG
    Let max_height := the maximum height of any chain across all nodes passed
    in. LAG = max_height - HEIGHT for a given chain.

DIVERG
    Let common_ancestor_height := the height of the COMMON ANCESTOR.
    DIVERG = HEIGHT - common_ancestor_height

''',
        parents=[parent_parser, base_multinode_parser()])

    parser.add_argument(
        '--table',
        action='store_true',
        help='Print out a fork table for all nodes since the common ancestor.')

    parser.add_argument(
        '--tree',
        action='store_true',
        help='Print out a fork tree for all nodes since the common ancestor.')


def do_compare_chains(args):
    """Calculates and outputs comparison between all nodes on the network."""
    urls = split_comma_append_args(args.urls)
    users = split_comma_append_args(args.users)
    clients = make_rest_apis(urls, users)
    chains = get_chain_generators(clients)

    tails = get_tails(chains)
    graph = build_fork_graph(chains, tails)

    if args.table:
        print_table(graph, tails)

    elif args.tree:
        print_tree(graph, tails)

    else:
        print_summary(graph, tails)


def get_chain_generators(clients):
    # Convert the block dictionaries to simpler python data structures to
    # conserve memory and simplify interactions.
    return [
        map(SimpleBlock.from_block_dict, c.list_blocks(limit=3))
        for c in clients
    ]


def print_summary(graph, tails):
    """Print out summary and per-node comparison data."""
    # Get comparison data
    heads = get_heads(tails)
    heights = get_heights(tails)
    max_height = max(heights)
    common_height, block_ids_at_common_height = get_common_height(tails)
    lags = get_lags(heights, max_height)
    common_ancestor = graph.root
    divergences = get_divergences(heights, graph.root)

    # Print summary info
    col_1 = 8
    col_n = 8
    format_str = '{:<' + str(col_1) + '} ' + ('{:<' + str(col_n) + '} ') * 2
    header = format_str.format("COMMON", "HEIGHT", "BLOCKS")
    print(header)
    print("-" * len(header))
    print(format_str.format(
        "ANCESTOR", common_ancestor.num, common_ancestor.ident[:col_n]))
    print(format_str.format(
        "HEIGHT", common_height, str(block_ids_at_common_height)))
    print()

    # Print per-node data
    col_1 = 6
    col_n = 8
    format_str = \
        '{:<' + str(col_1) + '} ' + ('{:<' + str(col_n) + '} ') * len(tails)
    header = format_str.format("NODE", *list(range(len(tails))))
    print(header)
    print('-' * len(header))

    print(format_str.format("HEAD", *heads))
    print(format_str.format("HEIGHT", *heights))
    print(format_str.format("LAG", *lags))
    print(format_str.format("DIVERG", *divergences))
    print()


def print_table(graph, tails):
    """Print out a table of nodes and the blocks they have at each block height
    starting with the common ancestor."""
    node_count = len(tails)

    # Get the width of the table columns
    num_col_width = max(
        floor(log(max(get_heights(tails)), 10)) + 1,
        len("NUM"))
    node_col_width = max(
        floor(log(node_count, 10)) + 1,
        8)

    # Construct the output format string
    format_str = ''
    format_str += '{:<' + str(num_col_width) + '} '
    for _ in range(node_count):
        format_str += '{:<' + str(node_col_width) + '} '

    nodes_header = ["NODE " + str(i) for i in range(node_count)]
    header = format_str.format("NUM", *nodes_header)
    print(header)
    print('-' * len(header))

    prev_block_num = -1
    node_list = [''] * node_count
    for block_num, _, siblings in graph.walk():
        if block_num != prev_block_num:
            # Need to skip the first one
            if prev_block_num != -1:
                print(format_str.format(prev_block_num, *node_list))

            node_list.clear()
            node_list.extend([''] * node_count)
            prev_block_num = block_num

        for block_id, node_ids in siblings.items():
            for node_id in node_ids:
                node_list[node_id] = block_id[:8]

    # Print the last one
    print(format_str.format(prev_block_num, *node_list))


def print_tree(graph, tails):
    """Print out a tree of blocks starting from the common ancestor."""
    num_col_width = max(
        floor(log(max(get_heights(tails)), 10)) + 1,
        len("NUM"))
    col_n = 8

    format_str = (
        '{:<' + str(num_col_width) + '} '
        + ('{:<' + str(col_n) + '} ') * 2 + '{}'
    )

    header = format_str.format("NUM", "PARENT", "BLOCK", "NODES")
    print(header)
    print('-' * len(header))
    walker = graph.walk()

    next_block_num, parent, siblings = next(walker)
    cliques = {}
    while True:
        block_num = next_block_num

        try:
            while block_num == next_block_num:
                cliques[parent] = siblings
                next_block_num, parent, siblings = next(walker)
        except StopIteration:
            break

        print_cliques_at_height(block_num, cliques, format_str)

        cliques = {}

    print_cliques_at_height(block_num, cliques, format_str)


def print_cliques_at_height(block_num, cliques, format_str):
    print(format_str.format(block_num, '', '', ''))
    for parent, siblings in cliques.items():
        print(format_str.format('', parent[:8], '', ''))
        for block_id, nodes in siblings.items():
            print(format_str.format(
                '', '', block_id[:8], format_siblings(nodes)))
    print()


def format_siblings(nodes):
    return "{" + ", ".join(str(n) for n in nodes) + "}"


def get_heads(tails):
    return [tail[-1].ident[:8] for tail in tails]


def get_heights(tails):
    return [tail[-1].num for tail in tails]


def get_common_height(tails):
    block_ids = set(tail[0].ident[:8] for tail in tails)
    return tails[0][0].num, block_ids


def get_lags(heights, max_height):
    return [max_height - height for height in heights]


def get_divergences(heights, root):
    return [height - root.num for height in heights]


def get_tails(chains):
    """
    Args:
        An ordered collection of block generators.

    Returns a list of blocks for all chains where:
        1. The first block in all the lists has the same block number
        2. Each list has all blocks from the common block to the current block
           in increasing order
    """

    def get_num_of_oldest(blocks):
        return blocks[0].num

    # Get the first block from every chain
    tails = [[next(chain)] for chain in chains]

    # Find the minimum block number between all chains
    min_block_num = min(map(get_num_of_oldest, tails))

    # Walk all chains back to the minimum block number, adding blocks to the
    # chain lists as we go
    for i, chain in enumerate(chains):
        tail = tails[i]
        while get_num_of_oldest(tail) > min_block_num:
            tail.insert(0, next(chain))

    return tails


def _compare_across(collections, key):
    """Return whether all the collections return equal values when called with
    `key`."""
    if len(collections) < 2:
        return True
    c0 = key(collections[0])
    return all(c0 == key(c) for c in collections[1:])


def build_fork_graph(chains, tails):
    """
    Args:
        An ordered collection of block generators which have been consumed to
        the point where they are all at the same block height and the tails of
        the chains from that block height (in the same order).

    Returns a ForkGraph.
    """
    graph = ForkGraph()

    # Add tails to the graph first
    for i, tail in enumerate(tails):
        for block in reversed(tail):
            graph.add_block(i, block)

    # If we are already at the common ancestor, stop
    if _compare_across(
        [tail[0] for tail in tails], key=lambda block: block.ident
    ):
        return graph

    # Chains should now all be at the same height, so we can walk back
    # to common ancestor
    while True:
        heads = [next(chain) for chain in chains]
        for i, block in enumerate(heads):
            graph.add_block(i, block)
        if _compare_across(heads, key=lambda block: block.ident):
            break

    return graph
