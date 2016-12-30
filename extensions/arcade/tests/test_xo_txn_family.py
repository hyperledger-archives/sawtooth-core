# Copyright 2016 Intel Corporation
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

import logging
import unittest

from gossip import signed_object
from journal import global_store_manager
from sawtooth_xo.txn_family import XoTransaction


class TestSawtoothXoTxnFamily(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logger = logging.getLogger()

        # We need DEBUG level since some is_valid() failures get logged with
        # DEBUG
        logger.setLevel(logging.DEBUG)

        handler = logging.StreamHandler()
        logger.addHandler(handler)

    def test_xo_transaction_is_valid_no_signature(self):
        store = global_store_manager.KeyValueStore()
        transaction = XoTransaction({
            'Action': 'CREATE',
            'Name': 'game000'
        })

        self.assertFalse(transaction.is_valid(store))

    def test_xo_transaction_is_valid_missing_name(self):
        key = signed_object.generate_signing_key()

        store = global_store_manager.KeyValueStore()
        transaction = XoTransaction({
            'Action': 'CREATE'
        })
        transaction.sign_object(key)

        self.assertFalse(transaction.is_valid(store))

    def test_xo_transaction_is_valid_missing_action(self):
        key = signed_object.generate_signing_key()

        store = global_store_manager.KeyValueStore()
        transaction = XoTransaction({
            'Name': 'game000'
        })
        transaction.sign_object(key)

        self.assertFalse(transaction.is_valid(store))

    def test_xo_transaction_is_valid_invalid_action(self):
        key = signed_object.generate_signing_key()

        store = global_store_manager.KeyValueStore()
        transaction = XoTransaction({
            'Action': 'INVALID',
            'Name': 'game000'
        })
        transaction.sign_object(key)

        self.assertFalse(transaction.is_valid(store))

    def test_xo_transaction_is_valid_create_same_name(self):
        key = signed_object.generate_signing_key()

        store = global_store_manager.KeyValueStore()
        store.set('game000', '{}')
        transaction = XoTransaction({
            'Action': 'CREATE',
            'Name': 'game000'
        })
        transaction.sign_object(key)

        self.assertFalse(transaction.is_valid(store))

    def test_xo_transaction_is_valid_take_missing_space(self):
        key = signed_object.generate_signing_key()

        store = global_store_manager.KeyValueStore()
        store.set('game000', '{}')
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000'
        })
        transaction.sign_object(key)

        self.assertFalse(transaction.is_valid(store))

    def test_xo_transaction_is_valid_invalid_space(self):
        key = signed_object.generate_signing_key()
        store = global_store_manager.KeyValueStore()

        # Create the game
        transaction = XoTransaction({
            'Action': 'CREATE',
            'Name': 'game000'
        })
        transaction.sign_object(key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P1-NEXT')
        self.assertEqual(store['game000']['Board'], '---------')

        for space in [0, 10]:
            transaction = XoTransaction({
                'Action': 'TAKE',
                'Name': 'game000',
                'Space': space
            })
            transaction.sign_object(key)
            self.assertFalse(transaction.is_valid(store))

    def test_xo_transaction_is_valid_no_game(self):
        key = signed_object.generate_signing_key()
        store = global_store_manager.KeyValueStore()

        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 1
        })
        transaction.sign_object(key)
        self.assertFalse(transaction.is_valid(store))

    def test_xo_transaction_game_p1_wins(self):
        player1_key = signed_object.generate_signing_key()
        player2_key = signed_object.generate_signing_key()

        store = global_store_manager.KeyValueStore()

        # Create the game
        transaction = XoTransaction({
            'Action': 'CREATE',
            'Name': 'game000'
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P1-NEXT')
        self.assertEqual(store['game000']['Board'], '---------')

        # Take space 1
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 1
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P2-NEXT')
        self.assertEqual(store['game000']['Board'], 'X--------')

        # Take space 2
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 2
        })
        transaction.sign_object(player2_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P1-NEXT')
        self.assertEqual(store['game000']['Board'], 'XO-------')

        # Make sure it isn't valid to take space 2 again
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 2
        })
        transaction.sign_object(player1_key)
        self.assertFalse(transaction.is_valid(store))

        # Make sure Player 2 can't go on Player 1's turn.
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 3
        })
        transaction.sign_object(player2_key)
        self.assertFalse(transaction.is_valid(store))

        # Take space 4
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 4
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P2-NEXT')
        self.assertEqual(store['game000']['Board'], 'XO-X-----')

        # Make sure Player 1 can't go on Player 2's turn.
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 9
        })
        transaction.sign_object(player1_key)
        self.assertFalse(transaction.is_valid(store))

        # Take space 9
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 9
        })
        transaction.sign_object(player2_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P1-NEXT')
        self.assertEqual(store['game000']['Board'], 'XO-X----O')

        # Take space 7
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 7
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P1-WIN')
        self.assertEqual(store['game000']['Board'], 'XO-X--X-O')

        # Make sure we can't modify the game anymore
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 3
        })
        transaction.sign_object(player2_key)
        self.assertFalse(transaction.is_valid(store))

    def test_xo_transaction_game_p2_wins(self):
        player1_key = signed_object.generate_signing_key()
        player2_key = signed_object.generate_signing_key()

        store = global_store_manager.KeyValueStore()

        # Create the game
        transaction = XoTransaction({
            'Action': 'CREATE',
            'Name': 'game000'
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P1-NEXT')
        self.assertEqual(store['game000']['Board'], '---------')

        # Take space 1
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 1
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P2-NEXT')
        self.assertEqual(store['game000']['Board'], 'X--------')

        # Take space 2
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 2
        })
        transaction.sign_object(player2_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P1-NEXT')
        self.assertEqual(store['game000']['Board'], 'XO-------')

        # Take space 4
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 4
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P2-NEXT')
        self.assertEqual(store['game000']['Board'], 'XO-X-----')

        # Take space 8
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 8
        })
        transaction.sign_object(player2_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P1-NEXT')
        self.assertEqual(store['game000']['Board'], 'XO-X---O-')

        # Take space 9
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 9
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P2-NEXT')
        self.assertEqual(store['game000']['Board'], 'XO-X---OX')

        # Take space 5
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 5
        })
        transaction.sign_object(player2_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P2-WIN')
        self.assertEqual(store['game000']['Board'], 'XO-XO--OX')

    def test_xo_transaction_game_tie(self):
        player1_key = signed_object.generate_signing_key()
        player2_key = signed_object.generate_signing_key()

        store = global_store_manager.KeyValueStore()

        # Create the game
        transaction = XoTransaction({
            'Action': 'CREATE',
            'Name': 'game000'
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P1-NEXT')
        self.assertEqual(store['game000']['Board'], '---------')

        # Take space 1
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 1
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P2-NEXT')
        self.assertEqual(store['game000']['Board'], 'X--------')

        # Take space 2
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 2
        })
        transaction.sign_object(player2_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P1-NEXT')
        self.assertEqual(store['game000']['Board'], 'XO-------')

        # Take space 4
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 4
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P2-NEXT')
        self.assertEqual(store['game000']['Board'], 'XO-X-----')

        # Take space 5
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 5
        })
        transaction.sign_object(player2_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P1-NEXT')
        self.assertEqual(store['game000']['Board'], 'XO-XO----')

        # Take space 8
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 8
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P2-NEXT')
        self.assertEqual(store['game000']['Board'], 'XO-XO--X-')

        # Take space 7
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 7
        })
        transaction.sign_object(player2_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P1-NEXT')
        self.assertEqual(store['game000']['Board'], 'XO-XO-OX-')

        # Take space 3
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 3
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P2-NEXT')
        self.assertEqual(store['game000']['Board'], 'XOXXO-OX-')

        # Take space 6
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 6
        })
        transaction.sign_object(player2_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'P1-NEXT')
        self.assertEqual(store['game000']['Board'], 'XOXXOOOX-')

        # Take space 9
        transaction = XoTransaction({
            'Action': 'TAKE',
            'Name': 'game000',
            'Space': 9
        })
        transaction.sign_object(player1_key)
        self.assertTrue(transaction.is_valid(store))
        transaction.apply(store)
        self.assertIn('game000', store)
        self.assertIn('Board', store['game000'])
        self.assertIn('State', store['game000'])
        self.assertEqual(store['game000']['State'], 'TIE')
        self.assertEqual(store['game000']['Board'], 'XOXXOOOXX')
