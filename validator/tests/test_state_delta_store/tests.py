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

from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.state.state_delta_store import StateDeltaStore

from sawtooth_validator.protobuf.state_delta_pb2 import StateChange


class StateDeltaStoreTest(unittest.TestCase):
    def test_state_store_get_and_set(self):
        """Tests that we correctly get and set state changes to a
        StateDeltaStore.

        This tests sets a list of state change values and then gets them back,
        ensuring that the data is the same.
        """

        database = DictDatabase()

        delta_store = StateDeltaStore(database)

        changes = [StateChange(address='a100000' + str(i),
                               value=str(i).encode(),
                               type=StateChange.SET)
                   for i in range(0, 10)]

        delta_store.save_state_deltas('my_state_root_hash', changes)

        stored_changes = delta_store.get_state_deltas('my_state_root_hash')
        # This is a list-like repeated field, but to make it comparable we'll
        # have to generate a new list
        stored_changes = [c for c in stored_changes]

        self.assertEqual(changes, stored_changes)

    def test_raise_key_error_on_missing_root_hash(self):
        """Tests that we correctly raise key error on a missing hash
        """
        database = DictDatabase()
        delta_store = StateDeltaStore(database)

        with self.assertRaises(KeyError):
            delta_store.get_state_deltas('unknown_state_root_hash')
