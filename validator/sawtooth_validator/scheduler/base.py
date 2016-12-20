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

from abc import ABCMeta
from abc import abstractmethod


class Scheduler(object):
    """Abstract class for scheduling transaction execution.

    Implementations of this class are expected to be thread-safe.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def add_batch(self, batch, state_hash=None):
        """Adds a batch to the scheduler.

        The batch, and thus its associated transactions, will be added to the
        scheduling queue.

        Args:
            batch: A batch_pb2.Batch instance.
            state_hash: The expected resulting state_hash after the
                transactions have been applied.
        """
        raise NotImplementedError

    @abstractmethod
    def batch_status(self, batch_signature):
        """Signifies whether a particular batch is valid, returns
           None if the batch hasn't fully been processed.

        Args:
            batch_signature (str): The batch signature

        Returns:
            BatchStatus: the status of the batch, see BatchStatus below
        """
        raise NotImplementedError

    @abstractmethod
    def set_status(self, txn_signature, status, state_hash=None):
        """Called by the executor after inform txn has been validated.

        Args:
            txn_signature (str): the signature of the last txn
            status (Boolean): whether the batch passed or failed
            state_hash (str): the state hash (may be virtual)
        """
        raise NotImplementedError

    @abstractmethod
    def next_transaction(self):
        """Returns the next transaction, if any, that can be processed.

        Returns:
            A Transaction object or None if there is not a transaction which
            can be processed.  A value of None does not necessarily indicate
            there are no more transactions, only that there are no
            transactions which have had their dependencies met.
        """
        raise NotImplementedError

    @abstractmethod
    def mark_as_applied(self, transaction_signature):
        """Instruct the scheduler that the transaction has been applied.

        The scheduler must know when transactions have been applied so that it
        can determine which transactions will become eligible for processing.

        Args:
            transaction_signature: The signature of the transaction, which
                must match the signature field of the Transaction object
                which was part of the added Batch.

        Raises:
            ValueError: Thrown if transaction_signature does not match a
            transaction.
        """
        raise NotImplementedError

    @abstractmethod
    def finalize(self):
        """Tell the scheduler that no more batches/transactions will be added.

        This will change the state of the scheduler.  After this call and all
        transactions are marked applied, complete() will return True.  After
        finalize() is called, batches can no longer be added to the scheduler.
        """
        raise NotImplementedError

    @abstractmethod
    def complete(self):
        """Returns True if all transactions have been marked as applied.

        Returns:
            True if all transactions have been marked as applied and that the
            finalize() as been called.
        """
        raise NotImplementedError

    @abstractmethod
    def __iter__(self):
        """Returns a Transaction iterator.

        All schedulers must be iterable, with the iterator returning the
        transactions, with the iteration blocking if finalize() has not been
        called.  Multiple iterators are allowed and each will start from
        the first transaction regardless of whether it has been marked as
        applied.

        Returns:
             An Transaction iterator.
        """
        raise NotImplementedError


class SchedulerIterator(object):
    def __init__(self, scheduler, condition, start_index=0):
        self._scheduler = scheduler
        self._condition = condition
        self._next_index = start_index

    def __next__(self):
        with self._condition:
            # Catch-up.  This will return transactions that have already been
            # scheduled.
            if self._next_index < self._scheduler.count():
                txn = self._scheduler.get_transaction(self._next_index)
                self._next_index += 1
                return txn

            # Return the next transaction, potentially blocking with wait().
            # Exit by throwing StopIteration when the scheduler is complete
            # and we have returned all the scheduler's transactions.
            while True:
                if (self._scheduler.complete()
                        and self._scheduler.count() == self._next_index):
                    raise StopIteration

                txn = self._scheduler.next_transaction()
                if txn is not None:
                    self._next_index += 1
                    return txn

                self._condition.wait()


class BatchStatus(object):
    """BatchStatus to send to journal to inform about the
    status of a batch
    attributes:
        valid (boolean): whether the batch is valid
        state_hash (str): the state hash after the batch
                          and will be None if the batch is invalid.
                         Could be a virtual state hash
    """
    def __init__(self, valid, state_hash):
        self.valid = valid
        self.state_hash = state_hash


class TxnInformation(object):
    """Information about a transaction from the
     scheduler to the executor.
    Attributes:
        txn transaction_pb2.Transaction protobuf class
        new_state_hash (Boolean): whether a new state
            hash needs to be generated.
        inform (Boolean): Whether a batch has been
              processed
    """
    def __init__(self, txn, new_state_hash, inform):
        self.txn = txn
        self.new_state_hash = new_state_hash
        self.inform = inform
