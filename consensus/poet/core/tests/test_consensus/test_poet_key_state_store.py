# Copyright 2016, 2017 Intel Corporation
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
from unittest.mock import patch
import tempfile
import os
import base64
from importlib import reload

from sawtooth_poet.poet_consensus import poet_key_state_store


class TestPoetKeyStateStore(unittest.TestCase):
    def setUp(self):
        # pylint: disable=invalid-name,global-statement
        global poet_key_state_store
        # Because PoetKeyStateStore uses class variables to hold state
        # we need to reload the module after each test to clear state
        poet_key_state_store = reload(poet_key_state_store)

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_store_verify_db_creation(self, mock_lmdb):
        """Verify that the underlying store LMDB file is created underneath
        the provided data directory and with the correct file creation flag.
        """
        _ = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        # Verify that the database is created in the directory provided
        # and that it is created with the anydb flag for open if exists,
        # create if doesn't exist
        _, kwargs = mock_lmdb.call_args

        self.assertTrue(
            kwargs.get('filename', '').startswith(
                tempfile.gettempdir() + os.sep))
        self.assertEqual(kwargs.get('flag'), 'c')

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_active_key_new_store(self, mock_lmdb):
        """Verify that a brand new key state store does not have an active key
        """
        mock_lmdb.return_value = {}

        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        self.assertIsNone(store.active_key)

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_active_key_not_present(self, mock_lmdb):
        """Verify that trying to set a non-existent key as active fails
        """
        mock_lmdb.return_value = {}

        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        with self.assertRaises(ValueError):
            store.active_key = 'ppk_1'

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_active_key_present(self, mock_lmdb):
        """Verify that setting a present key active succeeds
        """
        mock_lmdb.return_value = {
            'ppk_1':
                poet_key_state_store.PoetKeyState(
                    sealed_signup_data=base64.b64encode(b'sealed_1').decode(),
                    has_been_refreshed=False,
                    signup_nonce='single-use-only')
        }

        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        store.active_key = 'ppk_1'
        self.assertEqual(store.active_key, 'ppk_1')

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_active_key_clear(self, mock_lmdb):
        """Verify that clearing the active succeeds
        """
        mock_lmdb.return_value = {
            'ppk_1':
                poet_key_state_store.PoetKeyState(
                    sealed_signup_data=base64.b64encode(b'sealed_1').decode(),
                    has_been_refreshed=False,
                    signup_nonce='single-use-only')
        }

        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        store.active_key = 'ppk_1'
        self.assertEqual(store.active_key, 'ppk_1')

        store.active_key = None
        self.assertIsNone(store.active_key)

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_active_key_delete(self, mock_lmdb):
        """Verify that deleting the key state for the active key also clears
        the active key
        """
        mock_lmdb.return_value = {
            'ppk_1':
                poet_key_state_store.PoetKeyState(
                    sealed_signup_data=base64.b64encode(b'sealed_1').decode(),
                    has_been_refreshed=False,
                    signup_nonce='single-use-only')
        }

        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        store.active_key = 'ppk_1'
        self.assertEqual(store.active_key, 'ppk_1')

        del store['ppk_1']
        self.assertIsNone(store.active_key)

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_store_nonexistent_key(self, mock_lmdb):
        """Verify that retrieval of a non-existent key raises the appropriate
        exception.
        """
        # Make LMDB return None for all keys
        mock_lmdb.return_value.__getitem__.side_effect = KeyError('bad key')
        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        with self.assertRaises(KeyError):
            _ = store['bad key']

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_store_len(self, mock_lmdb):
        """Verify that len() returns correct values for store.
        """
        # Make LMDB return empty dict
        mock_lmdb.return_value = {}

        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        # Verify that an empty database returns 0
        self.assertEqual(len(store), 0)

        # Set some values and verify that the length reflects it
        store['ppk_1'] = \
            poet_key_state_store.PoetKeyState(
                sealed_signup_data=base64.b64encode(b'sealed_1').decode(),
                has_been_refreshed=False,
                signup_nonce='single-use-only')
        self.assertEqual(len(store), 1)
        store['ppk_2'] =  \
            poet_key_state_store.PoetKeyState(
                sealed_signup_data=base64.b64encode(b'sealed_2').decode(),
                has_been_refreshed=False,
                signup_nonce='single-use-only')
        self.assertEqual(len(store), 2)

        # Delete values and verify that the length reflects it
        del store['ppk_1']
        self.assertEqual(len(store), 1)
        del store['ppk_1']
        self.assertEqual(len(store), 1)
        del store['ppk_2']
        self.assertEqual(len(store), 0)

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_store_del(self, mock_lmdb):
        """Verify that del removes entries from the store
        """
        # Make LMDB return empty dict
        mock_lmdb.return_value = {}

        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        # Delete from an empty store
        del store['ppk_1']

        # Set some values, do some deletes and verify store state is valid
        store['ppk_1'] = \
            poet_key_state_store.PoetKeyState(
                sealed_signup_data=base64.b64encode(b'sealed_1').decode(),
                has_been_refreshed=False,
                signup_nonce='single-use-only')
        store['ppk_2'] =  \
            poet_key_state_store.PoetKeyState(
                sealed_signup_data=base64.b64encode(b'sealed_2').decode(),
                has_been_refreshed=False,
                signup_nonce='single-use-only')

        del store['ppk_1']
        self.assertFalse('ppk_1' in store)
        self.assertTrue('ppk_2' in store)

        del store['ppk_2']
        self.assertFalse('ppk_2' in store)

        # Delete already deleted keys
        del store['ppk_1']
        self.assertFalse('ppk_1' in store)
        self.assertFalse('ppk_2' in store)

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_store_contains(self, mock_lmdb):
        """Verify that in, i.e., key in store, returns correct values
        """
        # Make LMDB return empty dict
        mock_lmdb.return_value = {}

        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        # Verify empty store
        self.assertFalse('ppk_1' in store)

        # Set some values and verify that store has keys
        store['ppk_1'] = \
            poet_key_state_store.PoetKeyState(
                sealed_signup_data=base64.b64encode(b'sealed_1').decode(),
                has_been_refreshed=False,
                signup_nonce='single-use-only')
        self.assertTrue('ppk_1' in store)
        store['ppk_2'] =  \
            poet_key_state_store.PoetKeyState(
                sealed_signup_data=base64.b64encode(b'sealed_2').decode(),
                has_been_refreshed=False,
                signup_nonce='single-use-only')
        self.assertTrue('ppk_1' in store)
        self.assertTrue('ppk_2' in store)

        # Delete values and verify that store does not have keys
        del store['ppk_2']
        self.assertFalse('ppk_2' in store)
        self.assertTrue('ppk_1' in store)
        del store['ppk_1']
        self.assertFalse('ppk_1' in store)
        self.assertFalse('ppk_2' in store)

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_store_iter(self, mock_lmdb):
        """Verify that iterating over store, i.e., for key in store:, iterates
        over all keys.
        """
        # Make LMDB return empty dict
        mock_lmdb.return_value = {}

        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        # Verify empty store
        iterated_ppks = []
        for ppk in store:
            iterated_ppks.append(ppk)

        self.assertEqual(len(iterated_ppks), 0)

        # Add some keys and verify iteration
        ppks = ['ppk_1', 'ppk_2', 'ppk_3', 'ppk_4']
        for ppk in ppks:
            store[ppk] = \
                poet_key_state_store.PoetKeyState(
                    sealed_signup_data=base64.b64encode(
                        'sealed for {}'.format(ppk).encode()).decode(),
                    has_been_refreshed=False,
                    signup_nonce='single-use-only')

        iterated_ppks = []
        for ppk in store:
            iterated_ppks.append(ppk)

        self.assertEqual(len(iterated_ppks), len(store))
        self.assertEqual(sorted(iterated_ppks), sorted(ppks))

        # Delete some keys and verify iteration
        ppks.remove('ppk_1')
        del store['ppk_1']
        ppks.remove('ppk_3')
        del store['ppk_3']

        iterated_ppks = []
        for ppk in store:
            iterated_ppks.append(ppk)

        self.assertEqual(len(iterated_ppks), len(store))
        self.assertEqual(sorted(iterated_ppks), sorted(ppks))

        # Delete remaining keys and verify iteration
        ppks.remove('ppk_2')
        del store['ppk_2']
        ppks.remove('ppk_4')
        del store['ppk_4']

        iterated_ppks = []
        for ppk in store:
            iterated_ppks.append(ppk)

        self.assertEqual(len(iterated_ppks), 0)

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_store_poet_public_keys(self, mock_lmdb):
        """Verify that poet_public_keys property returns a list of the expected
        keys.
        """
        # Make LMDB return empty dict
        mock_lmdb.return_value = {}

        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        self.assertEqual(len(store.poet_public_keys), 0)

        # Add some keys and verify
        ppks = ['ppk_1', 'ppk_2', 'ppk_3', 'ppk_4']
        for ppk in ppks:
            store[ppk] = \
                poet_key_state_store.PoetKeyState(
                    sealed_signup_data=base64.b64encode(
                        'sealed for {}'.format(ppk).encode()).decode(),
                    has_been_refreshed=False,
                    signup_nonce='single-use-only')

        self.assertEqual(len(store.poet_public_keys), len(ppks))
        self.assertEqual(sorted(ppks), sorted(store.poet_public_keys))

        # Delete some keys and verify
        ppks.remove('ppk_1')
        del store['ppk_1']
        ppks.remove('ppk_3')
        del store['ppk_3']

        self.assertEqual(len(store.poet_public_keys), len(ppks))
        self.assertEqual(sorted(ppks), sorted(store.poet_public_keys))

        # Delete remaining keys and verify
        ppks.remove('ppk_2')
        del store['ppk_2']
        ppks.remove('ppk_4')
        del store['ppk_4']

        self.assertEqual(len(store.poet_public_keys), 0)

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_store_set_get(self, mock_lmdb):
        """Verify that retrieving a previously set PoET public key results in
        the same value set.
        """
        # Make LMDB return empty dict
        mock_lmdb.return_value = {}

        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        # Store a key and verify that returns correct value
        store['ppk_1'] = \
            poet_key_state_store.PoetKeyState(
                sealed_signup_data=base64.b64encode(b'sealed_1').decode(),
                has_been_refreshed=False,
                signup_nonce='single-use-only')
        poet_key_state = store['ppk_1']
        self.assertEqual(
            poet_key_state.sealed_signup_data,
            base64.b64encode(b'sealed_1').decode())
        self.assertFalse(poet_key_state.has_been_refreshed)

        # Store another key and verify that returns correct value
        store['ppk_2'] =  \
            poet_key_state_store.PoetKeyState(
                sealed_signup_data=base64.b64encode(b'sealed_2').decode(),
                has_been_refreshed=True,
                signup_nonce='single-use-only')

        poet_key_state = store['ppk_2']
        self.assertEqual(
            poet_key_state.sealed_signup_data,
            base64.b64encode(b'sealed_2').decode())
        self.assertTrue(poet_key_state.has_been_refreshed)

        poet_key_state = store['ppk_1']
        self.assertEqual(
            poet_key_state.sealed_signup_data,
            base64.b64encode(b'sealed_1').decode())
        self.assertFalse(poet_key_state.has_been_refreshed)

        # Delete a key and verify that existing key still returns correct
        # value
        del store['ppk_1']
        poet_key_state = store['ppk_2']
        self.assertEqual(
            poet_key_state.sealed_signup_data,
            base64.b64encode(b'sealed_2').decode())
        self.assertTrue(poet_key_state.has_been_refreshed)

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_store_set_invalid_data(self, mock_lmdb):
        """Verify that attempting to set invalid data fails
        """
        # Make LMDB return empty dict
        mock_lmdb.return_value = {}

        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        # Store a non-PoetKeyState object
        for poet_key_state in [[], {}, (), 1, 1.0, '', False]:
            with self.assertRaises(ValueError):
                store['ppk_1'] = poet_key_state

        # Store invalid sealed_signup_data field
        for sealed_signup_data in [[], {}, (), 1, 1.0, b'', True]:
            with self.assertRaises(ValueError):
                store['ppk_1'] = \
                    poet_key_state_store.PoetKeyState(
                        sealed_signup_data=sealed_signup_data,
                        has_been_refreshed=False,
                        signup_nonce='single-use-only')

        # Store corrupted base64 sealed signup data
        with self.assertRaises(ValueError):
            store['ppk_1'] = \
                poet_key_state_store.PoetKeyState(
                    sealed_signup_data=base64.b64encode(
                        b'sealed_1').decode()[1:],
                    has_been_refreshed=False,
                    signup_nonce='single-use-only')

        # Store non-bool has_been_refreshed field
        sealed_signup_data = base64.b64encode(b'sealed').decode()
        for has_been_refreshed in [[], {}, (), 1, 1.0, '']:
            with self.assertRaises(ValueError):
                store['ppk_1'] = \
                    poet_key_state_store.PoetKeyState(
                        sealed_signup_data=sealed_signup_data,
                        has_been_refreshed=has_been_refreshed,
                        signup_nonce='single-use-only')

    @patch('sawtooth_poet.poet_consensus.poet_key_state_store.'
           'LMDBNoLockDatabase')
    def test_store_get_invalid_data(self, mock_lmdb):
        """Verify that attempting to get invalid data fails
        """

        store = \
            poet_key_state_store.PoetKeyStateStore(
                data_dir=tempfile.gettempdir(),
                validator_id='0123456789abcdef')

        # Underlying data is not a PoetKeyState (or valid tuple)
        for poet_key_state in [[], {}, (), (1,), 1, 1.0, '', False]:
            mock_lmdb.return_value.__getitem__.return_value = poet_key_state
            with self.assertRaises(ValueError):
                _ = store['ppk']

        # Verify an invalid deserialization of sealed signup data
        for sealed_signup_data in [[], {}, (), 1, 1.0, True]:
            mock_lmdb.return_value.__getitem__.return_value = \
                (sealed_signup_data, False)
            with self.assertRaises(ValueError):
                _ = store['ppk']

        # Verify corrupted base64 sealed signup data
        mock_lmdb.return_value.__getitem__.return_value = \
            (base64.b64encode(b'sealed_1').decode()[1:], False)
        with self.assertRaises(ValueError):
            _ = store['ppk']

        # Verify an invalid deserialization of has been revoked
        sealed_signup_data = base64.b64encode(b'sealed').decode()
        for has_been_refreshed in [[], {}, (), 1, 1.0, '']:
            mock_lmdb.return_value.__getitem__.return_value = \
                (sealed_signup_data, has_been_refreshed)
            with self.assertRaises(ValueError):
                _ = store['ppk']

        # Simulate underlying cbor or namedtuple throwing ValueError,
        # TypeError, or AttributeError
        mock_lmdb.return_value.__getitem__.side_effect = ValueError()
        with self.assertRaises(ValueError):
            _ = store['ppk']
        mock_lmdb.return_value.__getitem__.side_effect = TypeError()
        with self.assertRaises(ValueError):
            _ = store['ppk']
        mock_lmdb.return_value.__getitem__.side_effect = AttributeError()
        with self.assertRaises(ValueError):
            _ = store['ppk']
