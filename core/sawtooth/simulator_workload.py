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

# pylint: disable=no-self-use

from tempfile import NamedTemporaryFile

import pybitcointools


class SawtoothWorkload(object):
    """
       This is meant to be an abstract base class for all workload
       generators.  As such, it doesn't do anything useful besides
       define the interface that the workload simulator expects and
       hold onto one property for derived classes.
    """

    def __init__(self, delegate, config):
        """
        Initializes the base class.

        Args:
            delegate: The object that supports delegate methods
            config: A Config object that has run-time configuration

        The workload generator uses the delegate object to alert the
        simulator of certain events.

        on_new_transaction(transaction_id, client) is called when a
        workload generator creates a new transaction.

        transaction_id - the transaction ID for the new transaction
        client - an instance of a class that derives from SawtoothClient.
        This client is the one to which the transaction was submitted.
        """
        self._delegate = delegate
        self._config = config

    @property
    def delegate(self):
        return self._delegate

    @property
    def config(self):
        return self._config

    @staticmethod
    def _create_temporary_key_file():
        """
        A useful helper method for derived classes.  Remember to close the
        returned temporary file so that it gets deleted.

        Returns:
            A NamedTemporaryFile object.
        """
        key_file = NamedTemporaryFile()
        private_key = pybitcointools.random_key()
        encoded_key = pybitcointools.encode_privkey(private_key, 'wif')
        key_file.write(encoded_key)
        key_file.write('\n')
        key_file.flush()

        return key_file

    def on_will_start(self):
        """
        Called by the simulator to let the workload generator do any final
        setup before the simulator begins.

        Args:
            base_validator: The base validator used to prime the simulator.

        Returns:
            Nothing
        """
        pass

    def on_will_stop(self):
        """
        Called by the simulator to let the workload generator do any final
        cleanup before the simulator tears down.

        Returns:
            Nothing
        """
        pass

    def on_validator_discovered(self, url):
        """
        Called by the simulator to let the workload generator know that it has
        discovered a new validator in the network.  Note that the simulator
        will begin calling this before on_will_start to let the workload
        generator know about the initial list of clients.

        Args:
            url: The URL for the validator

        Returns:
            Nothing
        """
        pass

    def on_validator_removed(self, url):
        """
        Called by the simulator to let the workload generator know that it has
        detected that a validator has left the network.

        Args:
            url: The URL for the validator

        Returns:
            Nothing
        """
        pass

    def on_all_transactions_committed(self):
        """
        In the normal course of running the simulator loop, this is called
        by the validator to let the workload generator know that all pending
        transactions have been completed.  This is a hint to create a new
        transaction.

        Returns:
            Nothing
        """
        pass

    def on_transaction_committed(self, transaction_id):
        """
        In the normal course of running the simulator loop, this is called
        by the validator to let the workload generator know that a previously-
        pending transaction has been committed by the validator to which it
        was submitted.

        Args:
            transaction_id: The transaction that has been committed.

        Returns:
            Nothing
        """
        pass

    def on_transaction_not_yet_committed(self, transaction_id):
        # pylint: disable=invalid-name
        """
        In the normal course of running the simulator loop, this is called
        by the validator to let the workload generator know that a previously-
        pending transaction's status was checked and it is still pending.

        Args:
            transaction_id: The transaction that was checked.

        Returns:
            True: Put transaction back in the queue of transactions to check
            False: Don't bother checking the transaction's status any more

        """
        return True
