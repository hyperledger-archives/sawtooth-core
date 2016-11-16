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
import threading

from collections import namedtuple
from datetime import datetime

from sawtooth_signing import pbct_nativerecover as signing
from sawtooth.simulator_workload import SawtoothWorkload
from txnintegration.integer_key_client import IntegerKeyClient


LOGGER = logging.getLogger(__name__)

IntKeyState = namedtuple('IntKeyState', ['name', 'client', 'value'])


class IntegerKeyWorkload(SawtoothWorkload):
    """
    This workload is for the Sawtooth Integer Key transaction family.  In
    order to guarantee that transactions are submitted at a relatively-
    constant rate, when the transaction callbacks occur the following
    actions occur:

    1.  If there are no pending transactions (on_all_transactions_committed),
        a new key is created.
    2.  If a transaction is committed, the corresponding key is > 1000000
        either a increment is made (if < 10000000) or a new
        key is created (if >= 10000000).
    3.  If a transaction's status has been checked and it has not been
        committed, create a key  (to get a new transaction) and let
        the simulator know that the old transaction should be put back in
        the queue to be checked again.
    """

    def __init__(self, delegate, config):
        super(IntegerKeyWorkload, self).__init__(delegate, config)

        self._clients = []
        self._pending_transactions = {}
        self._lock = threading.Lock()

    def on_will_start(self):
        pass

    def on_will_stop(self):
        pass

    def on_validator_discovered(self, url):
        # We need a key file for the client, but as soon as the client is
        # created, we don't need it any more.  Then create a new client and
        # add it to our cadre of clients to use

        keystring = signing.encode_privkey(
            signing.generate_privkey(), 'wif')
        with self._lock:
            self._clients.append(IntegerKeyClient(
                baseurl=url,
                keystring=keystring))

    def on_validator_removed(self, url):
        with self._lock:
            # Remove validator from our list of clients so that we don't try
            # to submit new transactions to it.
            self._clients = [c for c in self._clients if c.base_url != url]

            # Remove any pending transactions for the validator that has been
            # removed.
            self._pending_transactions = \
                {t: g for t, g in self._pending_transactions.iteritems()
                 if g.client.base_url != url}

    def on_all_transactions_committed(self):
        # Since there are no outstanding transactions, we are going to create a
        # new key
        self._create_new_key()

    def on_transaction_committed(self, transaction_id):
        # Look up the transaction ID to find the key.  Since we will no longer
        # track this transaction, we can remove it from the dictionary.
        with self._lock:
            key = self._pending_transactions.pop(transaction_id, None)

        if key is not None:
            # If the key is not at max value, we will increment it,
            # update the key state, and add a new pending transaction
            if key.value < 1000000:
                new_transaction_id = key.client.inc(
                    key.name, 1)
                LOGGER.info('Increment key %s on validator %s with '
                            'transaction ID %s',
                            key.name,
                            key.client.base_url,
                            new_transaction_id)

                # Map the new transaction ID to the key state so we can look
                # it up later and let the delegate know that there is a new
                # pending transaction
                with self._lock:
                    self._pending_transactions[new_transaction_id] = \
                        IntKeyState(
                            name=key.name,
                            client=key.client,
                            value=key.value + 1)

                self.delegate.on_new_transaction(
                    new_transaction_id, key.client)
            # Otherwise, create new key.
            else:
                LOGGER.info('Key %s completed', key.name)
                self._create_new_key()

    def on_transaction_not_yet_committed(self, transaction_id):
        # Because we want to generate transactions at the rate requested, let's
        # create a new key
        self._create_new_key()

        # Let the caller know that we want the transaction checked again
        return True

    def _create_new_key(self):
        # Pick a random client for the key.  So that we don't have to ensure
        # that the entire validator network has the transactions for a key
        # committed, all of the transaction for a particular key will be
        # submitted to a single client.
        with self._lock:
            client = \
                random.choice(self._clients) \
                if len(self._clients) > 0 else None

        if client is not None:
            name = datetime.now().isoformat()
            transaction_id = client.set(name, 0)

            if transaction_id is not None:
                LOGGER.info('New key %s with transaction ID %s on %s',
                            name,
                            transaction_id,
                            client.base_url)

                # Map the transaction ID to the key state so we can look it
                # up later and let the delegate know that there is a new
                # pending transaction
                with self._lock:
                    self._pending_transactions[transaction_id] = \
                        IntKeyState(name=name, client=client, value=0)
                self.delegate.on_new_transaction(transaction_id, client)
