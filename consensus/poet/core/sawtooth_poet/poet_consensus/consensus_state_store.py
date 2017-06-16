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

import threading
import logging
import os

# pylint: disable=no-name-in-module
from collections.abc import MutableMapping

from sawtooth_poet.poet_consensus.consensus_state import ConsensusState

from sawtooth_validator.database.lmdb_nolock_database \
    import LMDBNoLockDatabase

LOGGER = logging.getLogger(__name__)


class ConsensusStateStore(MutableMapping):
    """Manages access to the underlying database holding per-block consensus
    state information.  Note that because of the architectural model around
    the consensus objects, all ConsensusStateStore objects actually reference
    a single underlying database.  Provides a dict-like interface to the
    consensus state, mapping block IDs to their corresponding consensus state.
    """

    _store_dbs = {}
    _lock = threading.Lock()

    def __init__(self, data_dir, validator_id):
        """Initialize the consensus state store

        Args:
            data_dir (str): The directory where underlying database file will
                be stored
            validator_id (str): A unique ID for the validator for which the
                consensus state store is being created

        Returns:
            None
        """
        with ConsensusStateStore._lock:
            # Create an underlying LMDB database file for the validator if
            # there already isn't one.  We will create the LMDB with the 'c'
            # flag so that it will open if already exists.
            self._store_db = ConsensusStateStore._store_dbs.get(validator_id)
            if self._store_db is None:
                db_file_name = \
                    os.path.join(
                        data_dir,
                        'poet_consensus_state-{}.lmdb'.format(
                            validator_id[:8]))
                LOGGER.debug('Create consensus store: %s', db_file_name)
                self._store_db = LMDBNoLockDatabase(db_file_name, 'c')
                ConsensusStateStore._store_dbs[validator_id] = self._store_db

    def __setitem__(self, block_id, consensus_state):
        """Adds/updates an item in the consensus state store

        Args:
            block_id (str): The ID of the block that this consensus state
                corresponds to
            consensus_state (ConsensusState): The consensus state

        Returns:
            None
        """
        self._store_db[block_id] = consensus_state.serialize_to_bytes()

    def __getitem__(self, block_id):
        """Return the consensus state corresponding to the block ID

        Args:
            block_id (str): The ID of the block for which consensus state
                is being requested

        Returns:
            ConsensusState object

        Raises:
            KeyError if the block ID is not in the store
        """
        serialized_consensus_state = self._store_db[block_id]
        if serialized_consensus_state is None:
            raise KeyError('Block ID {} not found'.format(block_id))

        try:
            consensus_state = ConsensusState()
            consensus_state.parse_from_bytes(
                buffer=serialized_consensus_state)
            return consensus_state
        except ValueError as error:
            raise \
                KeyError(
                    'Cannot return block with ID {}: {}'.format(
                        block_id,
                        error))

    def __delitem__(self, block_id):
        del self._store_db[block_id]

    def __contains__(self, block_id):
        return block_id in self._store_db

    def __iter__(self):
        # Required by abstract base class, but implementing is non-trivial
        raise NotImplementedError('ConsensusState is not iterable')

    def __len__(self):
        return len(self._store_db)

    def __str__(self):
        out = []
        for block_id in self._store_db.keys():
            try:
                serialized_consensus_state = self._store_db[block_id]
                consensus_state = ConsensusState()
                consensus_state.parse_from_bytes(
                    buffer=serialized_consensus_state)
                out.append(
                    '{}...{}: {{{}}}'.format(
                        block_id[:8],
                        block_id[-8:],
                        consensus_state))
            except ValueError:
                pass

        return ', '.join(out)

    # pylint: disable=arguments-differ
    def get(self, block_id, default=None):
        """Return the consensus state corresponding to block ID or the default
        value if none exists

        Args:
            block_id (str):  The ID of the block for which consensus state
                is being requested
            default (ConsensusState): The default value to return if there
                is no consensus state associated with the block ID

        Returns:
            ConsensusState object or default if no state for key
        """
        try:
            return self.__getitem__(block_id)
        except KeyError:
            pass

        return default
