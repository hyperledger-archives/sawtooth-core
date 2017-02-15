# copyright 2017 intel corporation
#
# licensed under the apache license, version 2.0 (the "license");
# you may not use this file except in compliance with the license.
# you may obtain a copy of the license at
#
#     http://www.apache.org/licenses/license-2.0
#
# unless required by applicable law or agreed to in writing, software
# distributed under the license is distributed on an "as is" basis,
# without warranties or conditions of any kind, either express or implied.
# see the license for the specific language governing permissions and
# limitations under the license.
# ------------------------------------------------------------------------------

import unittest

from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.protobuf.state_context_pb2 import Entry
from sawtooth_validator.state.merkle import MerkleDatabase

from sawtooth_validator.state.state_view import StateViewFactory


class StateViewTest(unittest.TestCase):
    def setUp(self):
        self._database = DictDatabase()

    def test_state_view(self):
        merkle_db = MerkleDatabase(self._database)

        state_view_factory = StateViewFactory(self._database)

        initial_state_view = state_view_factory.create_view(
            merkle_db.get_merkle_root())

        # test that the intial state view returns empty values
        self.assertEqual([], initial_state_view.addresses())
        self.assertEqual({}, initial_state_view.leaves(''))
        with self.assertRaises(KeyError):
            initial_state_view.get('abcd')

        add_entry = Entry(address='abcd', data='hello'.encode())
        next_root = merkle_db.update({'abcd': add_entry.SerializeToString()},
                                     virtual=False)

        next_state_view = state_view_factory.create_view(next_root)

        # Prove that the initial state view is not effected by the change
        self.assertEqual([], initial_state_view.addresses())
        self.assertEqual(['abcd'], next_state_view.addresses())

        # Test the entry is transf formed
        expected_entry = Entry(address='abcd', data='hello'.encode())
        self.assertEqual(expected_entry, next_state_view.get('abcd'))
        self.assertEqual({'abcd': expected_entry}, next_state_view.leaves(''))
