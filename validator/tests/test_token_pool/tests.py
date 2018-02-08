# Copyright 2018 Intel Corporation
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

from sawtooth_validator.gossip.token_pool import TokenPool
from sawtooth_validator.gossip.token_pool import NoTokenAvailable


class TestTokenPool(unittest.TestCase):

    def test_acquire_and_release(self):
        """Tests acquiring and releasing of a token.

        - Create a TokenPool of size 1.
        - verify that tokens are available
        - acquire token by a bearer id of "test_id"
        - verify that tokens are no longer available
        - verify that additional tokens are not allowed
        - release the token owned by "test_id"
        - verify tokens are available again
        """
        token_pool = TokenPool(1)

        self.assertTrue(token_pool.has_available_tokens())

        token_pool.acquire_token('test_id')

        self.assertFalse(token_pool.has_available_tokens())

        with self.assertRaises(NoTokenAvailable):
            token_pool.acquire_token('test_id2')

        token_pool.release_token('test_id')

        self.assertTrue(token_pool.has_available_tokens())

    def test_update_max_available_tokens(self):
        """Tests that the max available tokens can be updated

        - Create a TokenPool of size 1.
        - verify that tokens are available
        - acquire token by a bearer id of "test_id"
        - verify that tokens are no longer available
        - updated the max available tokens to 2
        - verify that tokens are available
        - acquire token by a bearer id of "test_id2"
        - verify that tokens are no longer available
        """
        token_pool = TokenPool(1)

        self.assertTrue(token_pool.has_available_tokens())

        token_pool.acquire_token('test_id')

        self.assertFalse(token_pool.has_available_tokens())

        token_pool.update_max_available_tokens(2)

        self.assertTrue(token_pool.has_available_tokens())

        token_pool.acquire_token('test_id2')

        self.assertFalse(token_pool.has_available_tokens())

    def test_idempotent_acquire_and_release(self):
        """Test that the same id can acquire and release a token more than
        once without consuming additional tokens (nor being rejected).

        - Create a TokenPool of size 1.
        - verify that tokens are available
        - acquire token by a bearer id of "test_id"
        - verify that tokens are no longer available
        - attempt to acquire a token with id "test_id" again
        - verify that additional tokens are not allowed
        - release the token owned by "test_id"
        - verify tokens are available again
        - release the token owned by "test_id" again, with no effect
        """
        token_pool = TokenPool(1)

        self.assertTrue(token_pool.has_available_tokens())

        token_pool.acquire_token('test_id')

        self.assertFalse(token_pool.has_available_tokens())

        token_pool.acquire_token('test_id')

        with self.assertRaises(NoTokenAvailable):
            token_pool.acquire_token('test_id2')

        token_pool.release_token('test_id')
        self.assertTrue(token_pool.has_available_tokens())
        token_pool.release_token('test_id')
