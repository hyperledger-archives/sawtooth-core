
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

from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.protobuf.state_context_pb2 import Entry


class StateViewFactory(object):
    """The StateViewFactory produces StateViews for a particular merkle root.

    This factory produces read-only views of a merkle tree. For a given
    database, these views are considered immutable.
    """

    def __init__(self, database):
        """Initilizes the factory with a given database.

        Args:
            database (:obj:`Database`): the database containing the merkle
                tree.
        """
        self._database = database

    def create_view(self, state_root_hash):
        """Creates a StateView for the given state root hash.

        Returns:
            StateView: state view locked to the given root hash.
        """
        return StateView(MerkleDatabase(self._database, state_root_hash))


class StateView(object):
    """The StateView is a snapshot of state stored in a merkle tree.

    The StateView is a read-only view of a merkle tree that stores state
    entries.  It is locked to a specific merkle root.
    """

    def __init__(self, tree):
        """Creates a StateView with a given merkle tree.

        Args:
            tree (:obj:`MerkleDatabase`): the merkle tree for this view
        """
        self._tree = tree

    def get(self, address):
        """
        Returns:
            :obj:`Entry`: the state entry at the given address
        """
        return StateView._entry(self._tree.get(address))

    def addresses(self):
        """
        Returns:
            list of str: the list of addresses available in this view
        """
        return self._tree.addresses()

    def leaves(self, prefix):
        """
        Args:
            prefix (str): an address prefix under which to look for leaves

        Returns:
            list of `Entry`: the state entries at the leaves
        """
        return {addr: StateView._entry(leaf)
                for addr, leaf in self._tree.leaves(prefix).items()}

    @staticmethod
    def _entry(data):
        if data is not None:
            entry = Entry()
            entry.ParseFromString(data)
            return entry
        else:
            return None
