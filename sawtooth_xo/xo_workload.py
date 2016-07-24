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

import random
import logging

from collections import namedtuple
from datetime import datetime

from sawtooth.simulator_workload import SawtoothWorkload
from sawtooth_xo.xo_client import XoClient


LOGGER = logging.getLogger(__name__)

GameState = namedtuple('GameState', ['name', 'client', 'spaces_taken'])


class XoWorkload(SawtoothWorkload):
    """
    This workload is for the Sawtooth XO transaction family.  In
    order to guarantee that transactions are submitted at a relatively-
    constant rate, when the transaction callbacks occur the following
    actions occur:

    1.  If there are no pending transactions (on_all_transactions_committed),
        a new game is started.
    2.  If a transaction is committed, the corresponding game is found and
        either a new space is taken (if all spaces are not taken) or a new
        game is started (if all spaces are taken).
    3.  If a transaction's status has been checked and it has not been
        committed, create a new game (to get a new transaction) and let
        the simulator know that the old transaction should be put back in
        the queue to be checked again.
    """

    # This is the order to take spaces so that we guarantee that we get to
    # use all 9 spaces (makes game management easier)
    _space_order = [1, 2, 3, 6, 9, 8, 7, 4, 5]

    def __init__(self, delegate, config):
        super(XoWorkload, self).__init__(delegate, config)

        self._clients = []
        self._games = {}
        self._pending_transactions = {}

    def on_will_start(self):
        pass

    def on_will_stop(self):
        pass

    def on_validator_discovered(self, url):
        # We need a key file for the client, but as soon as the client is
        # created, we don't need it any more.  Then create a new client and
        # add it to our cadre of clients to use
        with self._create_temporary_key_file() as key_file:
            self._clients.append(XoClient(url, key_file.name))

    def on_validator_removed(self, url):
        # Remove validator from our list of clients so that we don't try to
        # submit new transactions to it.
        self._clients = [c for c in self._clients if c.base_url != url]

        # Remove any pending transactions for the validator that has been
        # removed.
        self._pending_transactions = \
            {t: g for t, g in self._pending_transactions.iteritems()
             if g.client.base_url != url}

    def on_all_transactions_committed(self):
        # Since there are no outstanding transactions, we are going to create a
        # new game
        self._create_new_game()

    def on_transaction_committed(self, transaction_id):
        # Look up the transaction ID to find the game.  Since we will no longer
        # track this transaction, we can remove it from the dictionary.
        game = self._pending_transactions.pop(transaction_id, None)
        if game is not None:
            # If the game board is not full, we will take a new space,
            # update the game state, and add a new pending transaction
            if game.spaces_taken < len(self._space_order):
                new_transaction_id = game.client.take(
                    game.name, self._space_order[game.spaces_taken])

                LOGGER.info('Take space %d in game %s on validator %s with '
                            'transaction ID %s',
                            self._space_order[game.spaces_taken],
                            game.name,
                            game.client.base_url,
                            new_transaction_id)

                # Map the new transaction ID to the game state so we can look
                # it up later and let the delegate know that there is a new
                # pending transaction
                self._pending_transactions[new_transaction_id] = \
                    GameState(
                        name=game.name,
                        client=game.client,
                        spaces_taken=game.spaces_taken + 1)

                self.delegate.on_new_transaction(
                    new_transaction_id, game.client)
            # Otherwise, start a new game.
            else:
                LOGGER.info('Game %s completed', game.name)
                self._create_new_game()

    def on_transaction_not_yet_committed(self, transaction_id):
        # Because we want to generate transactions at the rate requested, let's
        # create a new game
        self._create_new_game()

        # Let the caller know that we want the transaction checked again
        return True

    def _create_new_game(self):
        # Pick a random client for the game.  So that we don't have to ensure
        # that the entire validator network has the transactions for a game
        # committed, all of the transaction for a particular game will be
        # submitted to a single client.
        if len(self._clients) > 0:
            client = self._clients[random.randint(0, len(self._clients) - 1)]

            name = datetime.now().isoformat()
            transaction_id = client.create(name)

            if transaction_id is not None:
                LOGGER.info('New game %s with transaction ID %s on %s',
                            name,
                            transaction_id,
                            client.base_url)

                # Map the transaction ID to the game state so we can look it
                # up later and let the delegate know that there is a new
                # pending transaction
                self._pending_transactions[transaction_id] = \
                    GameState(name=name, client=client, spaces_taken=0)
                self.delegate.on_new_transaction(transaction_id, client)
