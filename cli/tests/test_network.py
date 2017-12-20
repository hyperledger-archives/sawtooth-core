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
import unittest

from sawtooth_cli.network_command.compare import build_fork_graph
from sawtooth_cli.network_command.compare import get_tails
from sawtooth_cli.network_command.compare import print_table
from sawtooth_cli.network_command.compare import print_tree
from sawtooth_cli.network_command.fork_graph import SimpleBlock


def make_generator(collection):
    for item in collection:
        yield item


class TestNetworkCompare(unittest.TestCase):
    def test_complex_graph(self):
        """Test that building the fork graph works correctly for a complex
        network state."""

        #          -------PEER IDS------
        #   NUM    0    1    2    3    4
        chains_info = [
            (15, ['z', '', '', '', '']),
            (14, ['y', '', '', '', '']),
            (13, ['w', '', 'x', '', '']),
            (12, ['t', '', 'u', '', 'v']),
            (11, ['g', 'h', 'l', 'm', 's']),
            (10, ['f', 'f', 'k', 'k', 'r']),
            (9, ['e', 'e', 'j', 'j', 'q']),
            (8, ['d', 'd', 'i', 'i', 'p']),
            (7, ['c', 'c', 'c', 'c', 'o']),
            (6, ['b', 'b', 'b', 'b', 'n']),
            (5, ['a', 'a', 'a', 'a', 'a']),
            (4, ['0', '0', '0', '0', '0']),
        ]

        # Build chain generators
        chains = [[] for _ in chains_info[0][1]]
        for i, num_ids in enumerate(chains_info[:-1]):
            num, ids = num_ids
            for j, ident in enumerate(ids):
                if ident != '':
                    next_chain_info = chains_info[i + 1]
                    previous = next_chain_info[1][j]
                    block = SimpleBlock(num, ident, previous)
                    chains[j].append(block)

        chains = [make_generator(chain) for chain in chains]

        tails = get_tails(chains)
        for tail in tails:
            self.assertEqual(tail[0].num, 11)

        graph = build_fork_graph(chains, tails)
        self.assertEqual(graph.root.previous, '0')
        self.assertEqual(graph.root.ident, 'a')

        # How many checks should happen
        expected_checks = sum(map(
            lambda ci: sum(map(
                lambda bi: 0 if (bi == '' or bi == '0') else 1, ci[1]
            )),
            chains_info))

        checks = []

        for block_num, _, siblings in graph.walk():
            expected = chains_info[-(block_num - 3)]
            # Make sure we did the math right in this test
            assert expected[0] == block_num
            expected = expected[1]

            # `expected` contains a list of block ids, where the index is the
            # peer and the at that index is the block that peer should have
            for block_id, nodes in siblings.items():
                # Make sure none of the null strings were added
                self.assertNotEqual(block_id, '')

                for node in nodes:
                    self.assertEqual(block_id, expected[node])
                    checks.append(block_id)

        self.assertEqual(len(checks), expected_checks)

        print_table(graph, tails)
        print()
        print_tree(graph, tails)

    def test_simple_graph(self):
        """Test that building the fork graph works correctly for a simple
        network state."""

        chains = [make_generator(chain) for chain in (
            [SimpleBlock(19, '19', '18')],
            [SimpleBlock(19, '19', '18')],
            [SimpleBlock(19, '19', '18')],
        )]

        tails = get_tails(chains)
        graph = build_fork_graph(chains, tails)

        self.assertEqual(graph.root.previous, '18')
        self.assertEqual(graph.root.ident, '19')
