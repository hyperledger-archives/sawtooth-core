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
from sawtooth_validator.state.merkle import INIT_ROOT_KEY


class StateViewFactory:
    """The StateViewFactory produces StateViews for a particular merkle root.

    This factory produces read-only views of a merkle tree. For a given
    database, these views are considered immutable.
    """

    def __init__(self, database):
        """Initializes the factory with a given database.

        Args:
            database (:obj:`Database`): the database containing the merkle
                tree.
        """
        self._database = database

    def create_view(self, state_root_hash=None):
        """Creates a StateView for the given state root hash.

        Args:
            state_root_hash (str): The state root hash of the state view
                to return.  If None, returns the state view for the
        Returns:
            StateView: state view locked to the given root hash.
        """
        # Create a default Merkle database and if we have a state root hash,
        # update the Merkle database's root to that
        if state_root_hash is None:
            state_root_hash = INIT_ROOT_KEY

        merkle_db = MerkleDatabase(self._database,
                                   merkle_root=state_root_hash)

        return StateView(merkle_db)


class StateView:
    """The StateView provides read-only access to a particular merkle tree
    root.

    The StateView is a read-only view of a merkle tree. Access is limited to
    available addresses, collections of leaf nodes, and specific leaf nodes.
    The view is lock to a single merkle root, effectively making it an
    immutable snapshot.
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
            bytes the state entry at the given address
        """
        return self._tree.get(address)

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
            dict of str,bytes: the state entries at the leaves
        """
        return self._tree.leaves(prefix)
