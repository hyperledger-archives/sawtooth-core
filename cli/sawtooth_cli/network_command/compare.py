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

from sawtooth_cli.exceptions import CliException


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
        '-l',
        '--limit',
        default=25,
        type=int,
        help='the number of blocks to request at a time',
    )

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

    broken = []

    chains, errors = get_chain_generators(clients, args.limit)
    broken.extend(errors)
    for node in errors:
        print("Error connecting to node %d: %s" % (node, urls[node]))
    if not chains:
        print("No nodes reporting")
        return

    tails, errors = get_tails(chains)
    broken.extend(errors)
    for node in errors:
        del chains[node]
    for node in errors:
        print("Failed to reach common height with node %d: %s" % (
            node, urls[node]))
    if not chains:
        print("Failed to get common height")
        return

    graph, errors = build_fork_graph(chains, tails)
    broken.extend(errors)
    for node in errors:
        print("Failed to reach common ancestor with node %d: %s" % (
            node, urls[node]))
    if not graph:
        print("Failed to build fork graph")
        return

    # Transform tails and errors into the format expected by the print
    # functions. Because errors can occur while building the graph, we need to
    # remove the tails for those clients.
    broken.sort()
    node_id_map = get_node_id_map(broken, len(clients))
    tails = list(map(
        lambda item: item[1],
        filter(
            lambda item: item[0] not in broken,
            sorted(tails.items()))))

    if args.table:
        print_table(graph, tails, node_id_map)

    elif args.tree:
        print_tree(graph, tails, node_id_map)

    else:
        print_summary(graph, tails, node_id_map)


def get_chain_generators(clients, limit):
    # Send one request to each client to determine if it is responsive or not.
    # Use the heights of all the responding clients' heads to set the paging
    # size for future requests, so that the number of requests is minimized.
    heads = []
    good_clients = []
    bad_clients = []
    for i, client in enumerate(clients):
        try:
            block = next(client.list_blocks(limit=1))
            heads.append(SimpleBlock.from_block_dict(block))
            good_clients.append(client)
        except CliException:
            bad_clients.append(i)

    if not heads:
        return {}, bad_clients

    # Convert the block dictionaries to simpler python data structures to
    # conserve memory and simplify interactions.
    return {
        i: map(SimpleBlock.from_block_dict, c.list_blocks(limit=limit))
        for i, c in enumerate(good_clients)
    }, bad_clients


def prune_unreporting_peers(graph, unreporting):
    for _, _, siblings in graph.walk():
        for _, peers in siblings.items():
            for bad_peer in unreporting:
                if bad_peer in peers:
                    peers.remove(bad_peer)


def get_node_id_map(unreporting, total):
    node_id_map = {}
    offset = 0
    for i in range(total):
        if i not in unreporting:
            node_id_map[i - offset] = i
        else:
            offset += 1
    return node_id_map


def print_summary(graph, tails, node_id_map):
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
    node_col_width = get_col_width_for_num(len(tails), len("NODE"))
    num_col_width = get_col_width_for_num(max_height, len("HEIGHT"))
    lag_col_width = get_col_width_for_num(max(lags), len("LAG"))
    diverg_col_width = get_col_width_for_num(max(divergences), len("DIVERG"))

    format_str = (
        '{:<' + str(node_col_width) + '} '
        '{:<8} '
        '{:<' + str(num_col_width) + '} '
        '{:<' + str(lag_col_width) + '} '
        '{:<' + str(diverg_col_width) + '}'
    )

    header = format_str.format("NODE", "HEAD", "HEIGHT", "LAG", "DIVERG")
    print(header)
    print('-' * len(header))

    for i, _ in enumerate(tails):
        print(format_str.format(
            node_id_map[i],
            heads[i],
            heights[i],
            lags[i],
            divergences[i],
        ))
    print()


def get_col_width_for_num(num, min_width):
    assert num >= 0
    if num == 0:
        num = 1
    return max(floor(log(num)) + 1, min_width)


def print_table(graph, tails, node_id_map):
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

    nodes_header = ["NODE " + str(node_id_map[i]) for i in range(node_count)]
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


def print_tree(graph, tails, node_id_map):
    """Print out a tree of blocks starting from the common ancestor."""
    # Example:
    # |
    # | 5
    # *  a {0, 1, 2, 3, 4}
    # |
    # | 6
    # |\
    # * |  b {0, 1, 2, 3}
    # | *  n {4}
    # | |
    # | | 7
    # * |  c {0, 1, 2, 3}
    # | *  o {4}
    # | |
    # | | 8
    # |\ \
    # * | |  i {2, 3}
    # | * |  d {0, 1}
    # | | *  p {4}
    # | | |
    # | | | 9
    # * | |  j {2, 3}
    # | * |  e {0, 1}
    # | | *  q {4}
    # | | |
    # | | | 10
    # * | |  k {2, 3}
    # | * |  f {0, 1}
    # | | *  r {4}
    # | | |
    # | | | 11
    # |\ \ \
    # | | |\ \
    # * | | | |    g {0}
    # | * | | |    h {1}
    # |   * | |    l {2}
    # |   | * |    m {3}
    # |   |   *    s {4}
    # |  /   /
    # | |  /
    # | | | 12
    # * | |   t {0}
    # | * |   u {2}
    # | | *   v {4}
    # | |
    # | | 13
    # * |   w {0}
    # | *   x {2}
    # |
    # | 14
    # *   y {0}
    # | 15
    # *   z {0}

    walker = graph.walk()
    next_block_num, next_parent, next_siblings = next(walker)
    prev_cliques = []

    done = False
    while not done:
        cliques = {}
        block_num = next_block_num

        # Read all the cliques for this block number
        try:
            while block_num == next_block_num:
                cliques[next_parent] = next_siblings
                next_block_num, next_parent, next_siblings = next(walker)
        except StopIteration:
            # Do one last iteration after we've consumed the entire graph
            done = True

        print_cliques(prev_cliques, cliques, node_id_map)

        print_block_num_row(block_num, prev_cliques, cliques)

        print_splits(prev_cliques, cliques)

        print_folds(prev_cliques, cliques)

        prev_cliques = build_ordered_cliques(prev_cliques, cliques)

    print_cliques(prev_cliques, [], node_id_map)


def build_ordered_cliques(cliques, next_cliques):
    """Order the new cliques based on the order of their ancestors in the
    previous iteration."""
    def sort_key(clique):
        return -len(clique[1])

    if not cliques:
        return list(sorted(
            list(next_cliques.values())[0].items(),
            key=sort_key))

    ordered_cliques = []
    for _, clique in enumerate(cliques):
        parent, _ = clique

        # If this fork continues
        if parent in next_cliques:
            # Sort the cliques in descending order of the size of the
            # clique, so that the main chain tends to the left
            ordered_cliques.extend(
                sorted(next_cliques[parent].items(), key=sort_key))

        # Else drop it

    return ordered_cliques


def print_folds(cliques, next_cliques):
    # Need to keep track of which columns each branch is in as we fold
    folds = []
    for i, clique in enumerate(cliques):
        block_id, _ = clique
        if block_id not in next_cliques:
            folds.append(i)

    n_cliques = len(cliques)
    for i, fold in enumerate(folds):
        print_fold(fold, n_cliques - i, folds)
        folds[i] = None
        for j, _ in enumerate(folds):
            if folds[j] is not None:
                folds[j] -= 1


def print_fold(column_to_fold, total_columns, skips):
    """Print a row that removes the given column and shifts all the following
    columns."""
    format_str = '{:<2}' * (total_columns - 1)
    cols = []
    for i in range(column_to_fold):
        # print(i)
        if i in skips:
            cols.append("  ")
        else:
            cols.append("| ")
    for i in range(column_to_fold + 1, total_columns):
        # print(i)
        if i in skips:
            cols.append("  ")
        else:
            cols.append(" /")
    print(format_str.format(*cols))


def print_block_num_row(block_num, cliques, next_cliques):
    """Print out a row of padding and a row with the block number. Includes
    the branches prior to this block number."""
    n_cliques = len(cliques)
    if n_cliques == 0:
        print('|  {}'.format(block_num))
        return

    def mapper(clique):
        block_id, _ = clique
        if block_id not in next_cliques:
            return ' '
        return '|'

    format_str = '{:<' + str(n_cliques * 2) + '} {}'
    branches = list(map(mapper, cliques))
    for end in ('', block_num):
        print(format_str.format(' '.join(branches), end))


def print_cliques(cliques, next_cliques, node_id_map):
    """Print a '*' on each branch with its block id and the ids of the nodes
    that have the block."""
    n_cliques = len(cliques)
    format_str = '{:<' + str(n_cliques * 2) + '}  {} {}'
    branches = ['|'] * len(cliques)
    for i, clique in enumerate(cliques):
        block_id, nodes = clique
        print(format_str.format(
            ' '.join(branches[:i] + ['*'] + branches[i + 1:]),
            block_id[:8], format_siblings(nodes, node_id_map)))
        if block_id not in next_cliques:
            branches[i] = ' '


def print_splits(cliques, next_cliques):
    """Print shifts for new forks."""
    splits = 0
    for i, clique in enumerate(cliques):
        parent, _ = clique

        # If this fork continues
        if parent in next_cliques:
            # If there is a new fork, print a split
            if len(next_cliques[parent]) > 1:
                print_split(i + splits, len(cliques) + splits)
                splits += 1


def print_split(column_to_split, total_columns):
    """Print a row that splits the given column into two columns while
    shifting all the following columns."""
    out = ""
    for _ in range(column_to_split):
        out += "| "
    out += "|\\"
    for _ in range(column_to_split + 1, total_columns):
        out += " \\"
    print(out)


def format_siblings(nodes, node_id_map):
    return "{" + ", ".join(str(node_id_map[n]) for n in nodes) + "}"


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

    Returns
        A dictionary of lists of blocks for all chains where:
            1. The first block in all the lists has the same block number
            2. Each list has all blocks from the common block to the current
               block in increasing order
            3. The dictionary key is the index of the chain in `chains` that
               the list was generated from
        A list of indexes of the chains that had communication problems.
    """

    def get_num_of_oldest(blocks):
        return blocks[0].num

    # Get the first block from every chain
    tails = {}
    bad_chains = []
    for i, chain in chains.items():
        try:
            tails[i] = [next(chain)]
        except StopIteration:
            bad_chains.append(i)

    # Find the minimum block number between all chains
    min_block_num = min(map(get_num_of_oldest, tails.values()))

    # Walk all chains back to the minimum block number, adding blocks to the
    # chain lists as we go
    for i, chain in chains.items():
        if i not in bad_chains:
            tail = tails[i]
            while get_num_of_oldest(tail) > min_block_num:
                try:
                    block = next(chain)
                except StopIteration:
                    bad_chains.append(i)
                    break
                tail.insert(0, block)

    return tails, bad_chains


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

    Returns:
        A ForkGraph
        A list of indexes of the chains that had communication problems.
    """
    graph = ForkGraph()
    bad_chains = []

    # Add tails to the graph first
    for i, tail in tails.items():
        for block in reversed(tail):
            graph.add_block(i, block)

    # If we are already at the common ancestor, stop
    if _compare_across(
        [tail[0] for tail in tails.values()], key=lambda block: block.ident
    ):
        return graph, bad_chains

    # Chains should now all be at the same height, so we can walk back
    # to common ancestor
    while True:
        heads = []
        for i, chain in chains.items():
            if i not in bad_chains:
                try:
                    head = next(chain)
                except StopIteration:
                    bad_chains.append(i)
                heads.append((i, head))

        for i, block in heads:
            graph.add_block(i, block)
        if _compare_across(heads, key=lambda head: head[1].ident):
            break

    prune_unreporting_peers(graph, bad_chains)

    return graph, bad_chains
