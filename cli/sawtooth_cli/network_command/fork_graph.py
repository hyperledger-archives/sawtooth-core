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


class SimpleBlock:
    """Use a simpler data structure to save memory in the event the graph gets
    large and to simplify operations on blocks."""
    def __init__(self, num, ident, previous):
        self.num = num
        self.ident = ident
        self.previous = previous

    @classmethod
    def from_block_dict(cls, block_dict):
        return cls(
            int(block_dict['header']['block_num']),
            block_dict['header_signature'],
            block_dict['header']['previous_block_id'],
        )

    def __str__(self):
        return "(NUM:{}, ID:{}, P:{})".format(
            self.num, self.ident[:8], self.previous[:8])


class ForkGraphNode:
    """Represents a node on the fork graph. `siblings` is a dictionary whose
    keys are all the block ids that have the same parent and whose values are
    all the peers that have that particular block id."""
    def __init__(self, num, previous):
        self.siblings = {}
        self.num = num
        self.previous = previous

    def add_sibling(self, peer_id, block):
        assert block.num == self.num
        assert block.previous == self.previous
        if block.ident not in self.siblings:
            self.siblings[block.ident] = []
        self.siblings[block.ident].append(peer_id)


class ForkGraph:
    """Represents a directed graph of blocks from multiple peers. Blocks are
    stored under their previous block's id and each node may have multiple
    children. An AssertionError is raised if two blocks are added with the
    same previous block id but different block numbers. The earliest block
    is stored in `root`. This implementation does not ensure that all
    nodes are connected to the root.
    """
    def __init__(self):
        self._graph = {}
        self._root_node = None
        self._root_block = None

    @property
    def root(self):
        return self._root_block

    def add_block(self, peer_id, block):
        if block.previous not in self._graph:
            self._graph[block.previous] = \
                ForkGraphNode(block.num, block.previous)
        self._graph[block.previous].add_sibling(peer_id, block)

        if self._root_node is None or self._root_node.num > block.num:
            self._root_node = self._graph[block.previous]
            self._root_block = block

    def walk(self, head=None):
        """Do a breadth-first walk of the graph, yielding on each node,
        starting at `head`."""
        head = head or self._root_node

        queue = []
        queue.insert(0, head)

        while queue:
            node = queue.pop()

            yield node.num, node.previous, node.siblings

            for child in node.siblings:
                if child in self._graph:
                    queue.insert(0, self._graph[child])
