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
from sawtooth_validator.protobuf.state_delta_pb2 import StateDeltaSet


class StateDeltaStore(object):
    """A StateDeltaStore persists StateChange records to a provided database
    implementation.
    """

    def __init__(self, delta_db):
        """Constructs a StateDeltaStore, backed by a given database
        implementation.

        Args:
            delta_db (:obj:sawtooth_validator.database.database.Database): A
                database implementation that backs this store.
        """
        self._delta_db = delta_db

    def save_state_deltas(self, state_root_hash, state_changes):
        """Saves a list of state changes for the given state root hash to the
        backing store.

        Args:
            state_root_hash (str): the state root hash that resulted in the
                changes.
            state_changes (list of StateChange objs): the list of StateChange
                objects to be stored
        """
        delta_set = StateDeltaSet(state_changes=state_changes)

        self._delta_db[state_root_hash] = delta_set.SerializeToString()

    def get_state_deltas(self, state_root_hash):
        """Returns the state deltas stored for a given state root hash.

        Args:
            state_root_hash (str): the state root hash associated with
                the desired changes.

        Raises:
            KeyError: if the state_root_hash is unknown.
        """
        if state_root_hash not in self._delta_db:
            raise KeyError(
                'Unknown state_root_hash {}'.format(state_root_hash))

        delta_set_bytes = self._delta_db[state_root_hash]
        delta_set = StateDeltaSet()
        delta_set.ParseFromString(delta_set_bytes)
        return delta_set.state_changes
