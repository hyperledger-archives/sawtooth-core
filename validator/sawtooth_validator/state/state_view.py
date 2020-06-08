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
import ctypes
import weakref
from functools import lru_cache, wraps

from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.state.merkle import INIT_ROOT_KEY

from sawtooth_validator import ffi


# Wrapper of lru_cache that works for instance methods
def lru_cached_method(*lru_args, **lru_kwargs):
    def decorator(wrapped_fn):
        @wraps(wrapped_fn)
        def wrapped(self, *args, **kwargs):
            # Use a weak reference to self; this prevents a self-reference
            # cycle that fools the garbage collector into thinking the instance
            # shouldn't be dropped when all external references are dropped.
            weak_ref_to_self = weakref.ref(self)

            @wraps(wrapped_fn)
            @lru_cache(*lru_args, **lru_kwargs)
            def cached(*args, **kwargs):
                return wrapped_fn(weak_ref_to_self(), *args, **kwargs)
            setattr(self, wrapped_fn.__name__, cached)
            return cached(*args, **kwargs)
        return wrapped
    return decorator


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

    @lru_cache()
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


class NativeStateViewFactory(ffi.OwnedPointer):
    """A StateViewFactory, which wraps a native Rust instance, which can be
    passed to other rust objects."""
    def __init__(self, database):
        super(NativeStateViewFactory, self).__init__('state_view_factory_drop')
        ffi.LIBRARY.call('state_view_factory_new',
                         database.pointer,
                         ctypes.byref(self.pointer))


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

    @lru_cached_method()
    def get(self, address):
        """
        Returns:
            bytes the state entry at the given address
        """
        return self._tree.get(address)

    @lru_cached_method()
    def addresses(self):
        """
        Returns:
            list of str: the list of addresses available in this view
        """
        return self._tree.addresses()

    @lru_cached_method()
    def leaves(self, prefix):
        """
        Args:
            prefix (str): an address prefix under which to look for leaves

        Returns:
            dict of str,bytes: the state entries at the leaves
        """
        return self._tree.leaves(prefix)
