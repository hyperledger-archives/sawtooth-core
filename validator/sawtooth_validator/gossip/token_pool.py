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

from threading import Lock

from sawtooth_validator.execution.executor import InvalidTransactionObserver
from sawtooth_validator.journal.chain import ChainObserver
from sawtooth_validator.journal.publisher import PendingBatchQueueObserver

DEFAULT_POOL_SIZE = 60
"""The default number of tokens in a TokenPool.
"""


class NoTokenAvailable(Exception):
    """This exception is raised when there are no tokens available in a
    TokenPool when a caller tries to acquire a token.
    """


class TokenPool:
    """A pool of tokens that is decremented and incremented.
    """

    def __init__(self, initial_max_tokens=DEFAULT_POOL_SIZE):
        """Creates a TokenPool, with a given max number of tokens.
        """
        self._lock = Lock()
        self._max_tokens = initial_max_tokens
        self._token_bearers = set()

    def has_available_tokens(self):
        """Queries if there are any tokens available in this pool.

        Returns:
            boolean: True, if there are tokens remaining in the pool, False
                otherwise.
        """
        with self._lock:
            return len(self._token_bearers) < self._max_tokens

    def update_max_available_tokens(self, new_max):
        """Updates the maximum number of tokens available to this pool.

        Args:
            new_max (int): the new maximum number of tokens available.
        """
        with self._lock:
            self._max_tokens = new_max

    def acquire_token(self, token_bearer_id):
        """Consumes a token from the pool for a given bearer id.

        A token is acquired by a given bearer, denoted by their id.  This
        token is considered consumed.  If a bearer id is used more than once,
        it does not consume an additional token.

        Args:
            token_bearer_id (str): the id of the token bearer

        Raises:
            NoTokenAvailable: if there are no tokens in the pool.
        """
        with self._lock:
            if token_bearer_id in self._token_bearers:
                return

            if len(self._token_bearers) >= self._max_tokens:
                raise NoTokenAvailable()

            self._token_bearers.add(token_bearer_id)

    def release_token(self, token_bearer_id):
        """Returns a token back to the pool.

        The token bearer releases its hold on the token and token is returned
        to the pool. If the id provided is not of a current token bearer, it
        is ignored.

        Args:
            token_bearer_id (str): the id of the token bearer.
        """
        with self._lock:
            # Ignore any unknown token_bearers
            self._token_bearers.discard(token_bearer_id)


class BatchTokenPoolUpdater(InvalidTransactionObserver,
                            ChainObserver,
                            PendingBatchQueueObserver):
    """A series of observer interfaces that are wrapped around a token pool.

    The observers will be used to track changes in the state of batches or
    change the number of tokens available to a pool.
    """

    def __init__(self, token_pool):
        """Wraps a given TokenPool and returns tokens to the pool or updates
        its maximum available tokens, depending on events in the validator.
        """
        self._token_pool = token_pool

    def notify_txn_invalid(self, txn_id, batch_id,
                           message=None, extended_data=None):
        """On a transaction being marked as invalid, immediately release the
        token for the batch, such that more batches can be accepted.
        """
        self._token_pool.release_token(batch_id)

    def notify_pending_batch_queue_limit(self, limit):
        """On pending batch queue limit updates, the number of available
        tokens will be adjusted.
        """
        self._token_pool.update_max_available_tokens(limit)

    def chain_update(self, block, receipts):
        """On a block update, this observer will release tokens from any
        batches that were included in the given block.
        """
        for batch in block.batches:
            self._token_pool.release_token(batch.header_signature)
