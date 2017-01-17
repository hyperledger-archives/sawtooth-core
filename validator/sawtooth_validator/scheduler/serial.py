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

import queue
from threading import Condition

from sawtooth_validator.scheduler.base import BatchStatus
from sawtooth_validator.scheduler.base import TxnInformation
from sawtooth_validator.scheduler.base import Scheduler
from sawtooth_validator.scheduler.base import SchedulerIterator
from sawtooth_validator.scheduler.exceptions import SchedulerError


class SerialScheduler(Scheduler):
    """Serial scheduler which returns transactions in the natural order.

    This scheduler will schedule one transaction at a time (only one may be
    unapplied), in the exact order provided as batches were added to the
    scheduler.

    This scheduler is intended to be used for comparison to more complex
    schedulers - for tests related to performance, correctness, etc.
    """
    def __init__(self, squash_handler, first_state_hash):
        self._txn_queue = queue.Queue()
        self._scheduled_transactions = []
        self._batch_statuses = {}
        self._txn_to_batch = {}
        self._in_progress_transaction = None
        self._final = False
        self._complete = False
        self._squash = squash_handler
        self._condition = Condition()
        # contains all txn.signatures where txn is
        # last in it's associated batch
        self._last_in_batch = []
        self._last_state_hash = first_state_hash

    def __iter__(self):
        return SchedulerIterator(self, self._condition)

    def set_status(self, txn_signature, status, context_id):
        """the control flow is that on every valid txn a new state root is
        generated. If the txn is invalid the batch status is set,
        if the txn is the last txn in the batch, is valid, and no
         prior txn failed the batch, the
        batch is valid
        """
        with self._condition:
            if (self._in_progress_transaction is None or
                    self._in_progress_transaction != txn_signature):
                raise ValueError("transaction not in progress: {}",
                                 txn_signature)
            self._in_progress_transaction = None

            if txn_signature not in self._txn_to_batch:
                raise ValueError("transaction not in any batches: {}".format(
                    txn_signature))
            if status is True:
                # txn is valid, get a new state hash
                state_hash = self._squash(self._last_state_hash, [context_id])
                self._last_state_hash = state_hash
            else:
                # txn is invalid, pre-emptively fail the batch
                batch_signature = self._txn_to_batch[txn_signature]
                batch_status = BatchStatus(status, None)
                self._batch_statuses[batch_signature] = batch_status
            if txn_signature in self._last_in_batch:
                batch_signature = self._txn_to_batch[txn_signature]
                if batch_signature not in self._batch_statuses:
                    # because of the else clause above, txn is valid here
                    batch_status = BatchStatus(status, self._last_state_hash)
                    self._batch_statuses[batch_signature] = batch_status

            if self._final and self._txn_queue.empty():
                self._complete = True
            self._condition.notify_all()

    def add_batch(self, batch, state_hash=None):
        with self._condition:
            if self._final:
                raise SchedulerError("Scheduler is finalized. Cannnot take"
                                     " new batches")
            batch_signature = batch.header_signature
            batch_length = len(batch.transactions)
            for idx, txn in enumerate(batch.transactions):
                if idx == batch_length - 1:
                    self._last_in_batch.append(txn.header_signature)
                self._txn_to_batch[txn.header_signature] = batch_signature
                self._txn_queue.put(txn)

    def batch_status(self, batch_signature):
        with self._condition:
            return self._batch_statuses.get(batch_signature)

    def count(self):
        with self._condition:
            return len(self._scheduled_transactions)

    def get_transaction(self, index):
        with self._condition:
            return self._scheduled_transactions[index]

    def next_transaction(self):
        with self._condition:
            if self._in_progress_transaction is not None:
                return None
            try:
                txn = self._txn_queue.get(block=False)
            except queue.Empty:
                return None

            self._in_progress_transaction = txn.header_signature
            txn_info = TxnInformation(txn, self._last_state_hash)
            self._scheduled_transactions.append(txn_info)
            return txn_info

    def finalize(self):
        with self._condition:
            self._final = True
            self._condition.notify_all()

    def complete(self, block):
        with self._condition:
            if not self._final:
                return False
            if self._complete:
                return True
            if block:
                self._condition.wait_for(lambda: self._complete)
                return True
            return False
