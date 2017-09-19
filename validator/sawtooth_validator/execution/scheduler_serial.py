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

from collections import deque
from threading import Condition

from sawtooth_validator.execution.scheduler import BatchExecutionResult
from sawtooth_validator.execution.scheduler import TxnExecutionResult
from sawtooth_validator.execution.scheduler import TxnInformation
from sawtooth_validator.execution.scheduler import Scheduler
from sawtooth_validator.execution.scheduler import SchedulerIterator
from sawtooth_validator.execution.scheduler_exceptions import SchedulerError

from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader


class SerialScheduler(Scheduler):
    """Serial scheduler which returns transactions in the natural order.

    This scheduler will schedule one transaction at a time (only one may be
    unapplied), in the exact order provided as batches were added to the
    scheduler.

    This scheduler is intended to be used for comparison to more complex
    schedulers - for tests related to performance, correctness, etc.
    """
    def __init__(self, squash_handler, first_state_hash, always_persist):
        self._txn_queue = SimpleQueue()
        self._scheduled_transactions = []
        self._batch_statuses = {}
        self._txn_to_batch = {}
        self._batch_by_id = {}
        self._txn_results = {}
        self._in_progress_transaction = None
        self._final = False
        self._cancelled = False
        self._previous_context_id = None
        self._previous_valid_batch_c_id = None
        self._squash = squash_handler
        self._condition = Condition()
        # contains all txn.signatures where txn is
        # last in it's associated batch
        self._last_in_batch = []
        self._previous_state_hash = first_state_hash
        # The state hashes here are the ones added in add_batch, and
        # are the state hashes that correspond with block boundaries.
        self._required_state_hashes = {}
        self._already_calculated = False
        self._always_persist = always_persist

    def __del__(self):
        self.cancel()

    def __iter__(self):
        return SchedulerIterator(self, self._condition)

    def set_transaction_execution_result(
            self, txn_signature, is_valid, context_id, state_changes=None,
            events=None, data=None, error_message="", error_data=b""):
        with self._condition:
            if (self._in_progress_transaction is None or
                    self._in_progress_transaction != txn_signature):
                raise ValueError("transaction not in progress: {}".format(
                                 txn_signature))
            self._in_progress_transaction = None

            if txn_signature not in self._txn_to_batch:
                raise ValueError("transaction not in any batches: {}".format(
                    txn_signature))

            if txn_signature not in self._txn_results:
                self._txn_results[txn_signature] = TxnExecutionResult(
                    signature=txn_signature,
                    is_valid=is_valid,
                    context_id=context_id if is_valid else None,
                    state_hash=self._previous_state_hash if is_valid else None,
                    state_changes=state_changes,
                    events=events,
                    data=data,
                    error_message=error_message,
                    error_data=error_data)

            batch_signature = self._txn_to_batch[txn_signature]
            if is_valid:
                self._previous_context_id = context_id

            else:
                # txn is invalid, preemptively fail the batch
                self._batch_statuses[batch_signature] = \
                    BatchExecutionResult(is_valid=False, state_hash=None)
            if txn_signature in self._last_in_batch:
                if batch_signature not in self._batch_statuses:
                    # because of the else clause above, txn is valid here
                    self._previous_valid_batch_c_id = self._previous_context_id
                    state_hash = self._calculate_state_root_if_required(
                        batch_id=batch_signature)
                    self._batch_statuses[batch_signature] = \
                        BatchExecutionResult(is_valid=True,
                                             state_hash=state_hash)
                else:
                    self._previous_context_id = self._previous_valid_batch_c_id

            self._condition.notify_all()

    def add_batch(self, batch, state_hash=None):
        with self._condition:
            if self._final:
                raise SchedulerError("Scheduler is finalized. Cannot take"
                                     " new batches")
            batch_signature = batch.header_signature
            self._batch_by_id[batch_signature] = batch
            if state_hash is not None:
                self._required_state_hashes[batch_signature] = state_hash
            batch_length = len(batch.transactions)
            for idx, txn in enumerate(batch.transactions):
                if idx == batch_length - 1:
                    self._last_in_batch.append(txn.header_signature)
                self._txn_to_batch[txn.header_signature] = batch_signature
                self._txn_queue.put(txn)
            self._condition.notify_all()

    def get_batch_execution_result(self, batch_signature):
        with self._condition:
            return self._batch_statuses.get(batch_signature)

    def get_transaction_execution_results(self, batch_signature):
        with self._condition:
            batch_status = self._batch_statuses.get(batch_signature)
            if batch_status is None:
                return None

            batch = self._batch_by_id.get(batch_signature)
            if batch is None:
                return None

            results = []
            for txn in batch.transactions:
                result = self._txn_results.get(txn.header_signature)
                if result is not None:
                    results.append(result)
            return results

    def count(self):
        with self._condition:
            return len(self._scheduled_transactions)

    def get_transaction(self, index):
        with self._condition:
            return self._scheduled_transactions[index]

    def _get_dependencies(self, transaction):
        header = TransactionHeader()
        header.ParseFromString(transaction.header)
        return list(header.dependencies)

    def _set_batch_result(self, txn_id, valid, state_hash):
        batch_id = self._txn_to_batch[txn_id]
        self._batch_statuses[batch_id] = BatchExecutionResult(
            is_valid=valid,
            state_hash=state_hash)
        batch = self._batch_by_id[batch_id]
        for txn in batch.transactions:
            if txn.header_signature not in self._txn_results:
                self._txn_results[txn.header_signature] = TxnExecutionResult(
                    txn.header_signature, is_valid=False)

    def _get_batch_result(self, txn_id):
        batch_id = self._txn_to_batch[txn_id]
        return self._batch_statuses[batch_id]

    def _dep_is_known(self, txn_id):
        return txn_id in self._txn_to_batch

    def _in_invalid_batch(self, txn_id):
        if self._txn_to_batch[txn_id] in self._batch_statuses:
            dependency_result = self._get_batch_result(txn_id)
            return not dependency_result.is_valid
        return False

    def _handle_fail_fast(self, txn):
        self._set_batch_result(
            txn.header_signature,
            False,
            None)
        self._check_change_last_good_context_id(txn)

    def _check_change_last_good_context_id(self, txn):
        if txn.header_signature in self._last_in_batch:
            self._previous_context_id = self._previous_valid_batch_c_id

    def next_transaction(self):
        with self._condition:
            if self._in_progress_transaction is not None:
                return None

            txn = None
            while txn is None:
                try:
                    txn = self._txn_queue.get()
                except EmptyQueue:
                    if self._final:
                        raise StopIteration()
                    return None
                # Handle this transaction being invalid based on a
                # dependency.
                if any(self._dep_is_known(d) and self._in_invalid_batch(d)
                        for d in self._get_dependencies(txn)):
                    self._set_batch_result(
                        txn.header_signature,
                        False,
                        None)
                    self._check_change_last_good_context_id(txn=txn)
                    txn = None
                    continue
                # Handle fail fast.
                if self._in_invalid_batch(txn.header_signature):
                    self._handle_fail_fast(txn)
                    txn = None

            self._in_progress_transaction = txn.header_signature
            base_contexts = [] if self._previous_context_id is None \
                else [self._previous_context_id]
            txn_info = TxnInformation(txn=txn,
                                      state_hash=self._previous_state_hash,
                                      base_context_ids=base_contexts)
            self._scheduled_transactions.append(txn_info)
            return txn_info

    def finalize(self):
        with self._condition:
            self._final = True
            self._condition.notify_all()

    def _compute_merkle_root(self, required_state_root):
        """Computes the merkle root of the state changes in the context
        corresponding with _last_valid_batch_c_id as applied to
        _previous_state_hash.

        Args:
            required_state_root (str): The merkle root that these txns
                should equal.

        Returns:
            state_hash (str): The merkle root calculated from the previous
                state hash and the state changes from the context_id
        """

        state_hash = None
        if self._previous_valid_batch_c_id is not None:
            publishing_or_genesis = self._always_persist or \
                                    required_state_root is None
            state_hash = self._squash(
                state_root=self._previous_state_hash,
                context_ids=[self._previous_valid_batch_c_id],
                persist=self._always_persist, clean_up=publishing_or_genesis)
            if self._always_persist is True:
                return state_hash
            if state_hash == required_state_root:
                self._squash(state_root=self._previous_state_hash,
                             context_ids=[self._previous_valid_batch_c_id],
                             persist=True, clean_up=True)
        return state_hash

    def _calculate_state_root_if_not_already_done(self):
        if not self._already_calculated:
            if not self._last_in_batch:
                return
            last_txn_signature = self._last_in_batch[-1]
            batch_id = self._txn_to_batch[last_txn_signature]
            required_state_hash = self._required_state_hashes.get(
                batch_id)

            state_hash = self._compute_merkle_root(required_state_hash)
            self._already_calculated = True
            for t_id in self._last_in_batch[::-1]:
                b_id = self._txn_to_batch[t_id]
                if self._batch_statuses[b_id].is_valid:
                    self._batch_statuses[b_id].state_hash = state_hash
                    # found the last valid batch, so break out
                    break

    def _calculate_state_root_if_required(self, batch_id):
        required_state_hash = self._required_state_hashes.get(
            batch_id)
        state_hash = None
        if required_state_hash is not None:
            state_hash = self._compute_merkle_root(required_state_hash)
            self._already_calculated = True
        return state_hash

    def _complete(self):
        return self._final and \
               len(self._txn_results) == len(self._txn_to_batch)

    def complete(self, block):
        with self._condition:
            if not self._final:
                return False
            if self._complete():
                self._calculate_state_root_if_not_already_done()
                return True
            if block:
                self._condition.wait_for(self._complete)
                self._calculate_state_root_if_not_already_done()
                return True
            return False

    def cancel(self):
        with self._condition:
            self._cancelled = True
            self._condition.notify_all()

    def is_cancelled(self):
        with self._condition:
            return self._cancelled


class SimpleQueue(object):

    def __init__(self):
        self._queue = deque()

    def get(self):
        try:
            return self._queue.popleft()
        except IndexError:
            raise EmptyQueue

    def put(self, item):
        self._queue.append(item)


class EmptyQueue(Exception):
    pass
