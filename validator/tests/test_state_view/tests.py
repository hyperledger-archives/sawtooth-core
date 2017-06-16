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
from sawtooth_validator.state.merkle import MerkleDatabase

from sawtooth_validator.state.state_view import StateViewFactory


class StateViewTest(unittest.TestCase):
    def test_state_view(self):
        """Tests the StateViewFactory and its creation of StateViews

        This test exercises the following:

        1. Create an empty merkle database.
        2. Create a view into the database, asserting its emptiness.
        3. Update the database with a value, creating a new root.
        4. Create a view into the database with the new root.
        5. Verify the view does not match the previous view and contains the
           new item.
        """

        database = DictDatabase()
        merkle_db = MerkleDatabase(database)

        state_view_factory = StateViewFactory(database)

        initial_state_view = state_view_factory.create_view(
            merkle_db.get_merkle_root())

        # test that the initial state view returns empty values
        self.assertEqual([], initial_state_view.addresses())
        self.assertEqual({}, initial_state_view.leaves(''))
        with self.assertRaises(KeyError):
            initial_state_view.get('abcd')

        next_root = merkle_db.update({'abcd': 'hello'.encode()},
                                     virtual=False)

        next_state_view = state_view_factory.create_view(next_root)

        # Prove that the initial state view is not effected by the change
        self.assertEqual([], initial_state_view.addresses())
        self.assertEqual(['abcd'], next_state_view.addresses())

        # Check that the values can be properly read back
        self.assertEqual('hello', next_state_view.get('abcd').decode())
        self.assertEqual({'abcd': 'hello'.encode()},
                         next_state_view.leaves(''))
