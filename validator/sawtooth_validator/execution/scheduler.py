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


class Scheduler(metaclass=ABCMeta):
    """Abstract class for scheduling transaction execution.

    Implementations of this class are expected to be thread-safe.
    """

    @abstractmethod
    def add_batch(self, batch, state_hash=None, required=False):
        """Adds a batch to the scheduler.

        The batch, and thus its associated transactions, will be added to the
        scheduling queue.

        Args:
            batch: A batch_pb2.Batch instance.
            state_hash: The expected resulting state_hash after the
                transactions have been applied.
            required: The given batch must be included in the completed
                schedule.  That is, it will not be removed when a call to
                `unschedule_incomplete_batches` is made.  Defaults to `False`.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_batch_execution_result(self, batch_signature):
        """Signifies whether a particular batch is valid, returns
           None if the batch hasn't fully been processed.

        Args:
            batch_signature (str): The signature of the batch, which must match
                the header_signature field of the Batch.

        Returns:
            BatchExecutionResult: The result of batch execution.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_transaction_execution_results(self, batch_signature):
        """Get all TransactionExecutionResults for a batch. If the batch isn't
        finished or is invalid, returns None.

        Args:
            batch_signature (str): The signature of the batch, which must match
                the header_signature field of the Batch.

        Returns:
            list of :obj:`TransactionExecutionResult`: The results of all
                transactions executed in the batch.
        """
        raise NotImplementedError()

    @abstractmethod
    def set_transaction_execution_result(
            self, txn_signature, is_valid, context_id, state_changes, events,
            data, error_message, error_data):
        """Set the status of an executed transaction.

        Called by the executor after a transaction has been processed.

        The scheduler must know when transactions have finished being
        applied so that it can determine which transactions will become
        eligible for processing.

        Args:
            txn_signature (str): The signature of the transaction, which
                must match the header_signature field of the Transaction
                object which was part of the added Batch.
            is_valid (bool): True if transaction applied successfully or False
                if the transaction failed and was not applied.
            context_id (str): If status is True, contains the context_id
                associated with the state changes made by the transaction.
                If status is False, this should be set to None.

        Raises:
            ValueError: Thrown if transaction_signature does not match a
            transaction.
        """
        raise NotImplementedError()

    @abstractmethod
    def next_transaction(self):
        """Returns the next transaction, if any, that can be processed.

        Returns:
            A Transaction object or None if there is not a transaction which
            can be processed.  A value of None does not necessarily indicate
            there are no more transactions, only that there are no
            transactions which have had their dependencies met.
        """
        raise NotImplementedError()

    @abstractmethod
    def unschedule_incomplete_batches(self):
        """Remove any incomplete batches from the schedule.
        """
        raise NotImplementedError()

    @abstractmethod
    def is_transaction_in_schedule(self, txn_signature):
        """Returns True if a transaction is in this schedule.

        Args:
            txn_signature (str): The signature of the transaction, which
                must match the header_signature field of the Transaction
                object which was part of the added Batch.
        """
        raise NotImplementedError()

    @abstractmethod
    def finalize(self):
        """Tell the scheduler that no more batches/transactions will be added.

        This will change the state of the scheduler.  After this call and all
        transactions are marked applied, complete() will return True.  After
        finalize() is called, batches can no longer be added to the scheduler.
        """
        raise NotImplementedError()

    @abstractmethod
    def complete(self, block):
        """Returns True if all transactions have been marked as applied.

        Args:
            block (bool): If True, block until complete, or if False return
                the completion status.

        Returns:
            True if all transactions have been marked as applied and that the
            finalize() has been called.
        """
        raise NotImplementedError()

    @abstractmethod
    def cancel(self):
        """Cancels the schedule of transactions. The cancelling of a scheduler
        is an idempotent operation. The iterator will raise
        StopIteration, completing iteration on the iterator.
        Returns:
            None
        """
        raise NotImplementedError()

    @abstractmethod
    def is_cancelled(self):
        """Returns whether .cancel() has been called on this scheduler.


        Returns:
            A bool specifing if the scheduler's .cancel() method has been
            called.
        """
        raise NotImplementedError()

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
        raise NotImplementedError()

    @abstractmethod
    def get_transaction(self, index):
        """Returns the scheduled Transaction at index.

        This is used by SchedulerIterator to return a consistent order of
        Transactions.  Once the Scheduler has picked

        Returns:
            Returns the Transaction at index.
        """
        raise NotImplementedError()

    @abstractmethod
    def count(self):
        """The count of transactions which have been scheduled.

        Returns:
            An integer.
        """
        raise NotImplementedError()


class SchedulerIterator:
    def __init__(self, scheduler, condition, start_index=0):
        self._scheduler = scheduler
        self._condition = condition
        self._next_index = start_index

    # pylint: disable=inconsistent-return-statements
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
            # and we have returned all the scheduler's transactions or the
            # scheduler was cancelled.
            while True:
                if (self._scheduler.complete(block=False)
                        and self._scheduler.count() == self._next_index
                        or self._scheduler.is_cancelled()):
                    raise StopIteration()

                txn = self._scheduler.next_transaction()
                if txn is not None:
                    self._next_index += 1
                    return txn

                self._condition.wait()


class BatchExecutionResult:
    """The resulting execution data from running the batch's transactions
    through the executor.

    Attributes:
        is_valid (bool): True if the batch is valid, False otherwise.
        state_hash (str): The state hash from applying the state changes from
            the transactions in this batch and all prior transactions in valid
            batches since the last state hash was returned. Will always be
            in the BatchExecutionResult for batches that were added to
            add_batch with a state hash.
    """

    def __init__(self, is_valid, state_hash):
        self.is_valid = is_valid
        self.state_hash = state_hash


class TxnExecutionResult:
    """The resulting execution data from running the transaction through the
    executor.

    Attributes:
        signature (str): The header signature of the transaction.
        is_valid (bool): True if the transaction is valid, False otherwise.
        context_id (str): The context id against which the transaction was run.
        state_hash (str): The state hash against which the transaction was run.
        state_changes (list of :obj:`transaction_receipt_pb2.StateChange`): The
            state changes that were a result of applying this transaction.
        events (list of :obj:`client_event_pb2.Event`): The events that were
            returned while executing this transaction.
        data (list of (str, bytes)): Opaque data that was returned while
            executing this transaction.
        error_message (str): An error message that was returned while executing
            this transaction.
        error_data (bytes): Error data that was returned while executing this
            transaction.
    """

    def __init__(self, signature, is_valid, context_id=None, state_hash=None,
                 state_changes=None, events=None, data=None,
                 error_message=None, error_data=None):

        if is_valid and context_id is None:
            raise ValueError(
                "There must be a context_id for valid transactions")
        if not is_valid and context_id is not None:
            raise ValueError(
                "context_id must be None for invalid transactions")
        if not is_valid and state_hash is not None:
            raise ValueError(
                "state_hash must be None for invalid transactions")

        self.signature = signature
        self.is_valid = is_valid
        self.context_id = context_id
        self.state_hash = state_hash
        self.state_changes = state_changes if state_changes is not None else []
        self.events = events if events is not None else []
        self.data = data if data is not None else []
        self.error_message = error_message if error_message is not None else ''
        self.error_data = error_data if error_data is not None else b''


class TxnInformation:
    """Information about a transaction from the
     scheduler to the executor.
    Attributes:
        txn transaction_pb2.Transaction protobuf class
        state_hash (str): the state hash that
                                 this txn should be applied against
    """

    def __init__(self, txn, state_hash, base_context_ids):
        self.txn = txn
        self.state_hash = state_hash
        self.base_context_ids = base_context_ids
