# Copyright 2017 Intel Corporation
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
# -----------------------------------------------------------------------------

import abc
from threading import RLock
from sawtooth_validator.journal.timed_cache import TimedCache
from sawtooth_validator.journal.chain import ChainObserver
from sawtooth_validator.execution.executor import InvalidTransactionObserver
from sawtooth_validator.journal.publisher import PendingBatchObserver
from sawtooth_validator.protobuf.client_batch_submit_pb2 \
    import ClientBatchStatus


# By default invalid batch info will be kept for one hour
CACHE_KEEP_TIME = 3600


class BatchTracker(ChainObserver,
                   InvalidTransactionObserver,
                   PendingBatchObserver):
    """Tracks batch statuses for this local validator, allowing interested
    components to check where a batch is in the validation process. It should
    only be relied on for batches submitted locally, and is not persisted
    after restart.

    When a batch moves from one component to another, the appropriate notify
    method should be called in the appropriate component, as specified by the
    relevant Observer class, and implemented here.

    Args:
        batch_committed (fn() -> bool): For querying if a batch is committed
        cache_keep_time (float): Time in seconds to keep values in TimedCaches
        cache_purge_frequency (float): Time between purging the TimedCaches
    """

    def __init__(self,
                 batch_committed,
                 cache_keep_time=600,
                 cache_purge_frequency=30):
        self._batch_committed = batch_committed
        self._batch_info = TimedCache(cache_keep_time, cache_purge_frequency)
        self._invalid = TimedCache(cache_keep_time, cache_purge_frequency)
        self._pending = set()

        self._lock = RLock()
        self._observers = {}

    def chain_update(self, block, receipts):
        """Removes batches from the pending cache if found in the block store,
        and notifies any observers.
        """
        with self._lock:
            for batch_id in self._pending.copy():
                if self._batch_committed(batch_id):
                    self._pending.remove(batch_id)
                    self._update_observers(batch_id,
                                           ClientBatchStatus.COMMITTED)

    def notify_txn_invalid(self, txn_id, message=None, extended_data=None):
        """Adds a batch id to the invalid cache along with the id of the
        transaction that was rejected and any error message or extended data.
        Removes that batch id from the pending set. The cache is only
        temporary, and the batch info will be purged after one hour.

        Args:
            txn_id (str): The id of the invalid batch
            message (str, optional): Message explaining why batch is invalid
            extended_data (bytes, optional): Additional error data
        """
        invalid_txn_info = {'id': txn_id}
        if message is not None:
            invalid_txn_info['message'] = message
        if extended_data is not None:
            invalid_txn_info['extended_data'] = extended_data

        with self._lock:
            for batch_id, txn_ids in self._batch_info.items():
                if txn_id in txn_ids:
                    if batch_id not in self._invalid:
                        self._invalid[batch_id] = [invalid_txn_info]
                    else:
                        self._invalid[batch_id].append(invalid_txn_info)
                    self._pending.discard(batch_id)
                    self._update_observers(batch_id, ClientBatchStatus.INVALID)
                    return

    def notify_batch_pending(self, batch):
        """Adds a Batch id to the pending cache, with its transaction ids.

        Args:
            batch (str): The id of the pending batch
        """
        txn_ids = {t.header_signature for t in batch.transactions}
        with self._lock:
            self._pending.add(batch.header_signature)
            self._batch_info[batch.header_signature] = txn_ids
            self._update_observers(batch.header_signature,
                                   ClientBatchStatus.PENDING)

    def get_status(self, batch_id):
        """Returns the status enum for a batch.

        Args:
            batch_id (str): The id of the batch to get the status for

        Returns:
            int: The status enum
        """
        with self._lock:
            if self._batch_committed(batch_id):
                return ClientBatchStatus.COMMITTED
            if batch_id in self._invalid:
                return ClientBatchStatus.INVALID
            if batch_id in self._pending:
                return ClientBatchStatus.PENDING
            return ClientBatchStatus.UNKNOWN

    def get_statuses(self, batch_ids):
        """Returns a statuses dict for the requested batches.

        Args:
            batch_ids (list of str): The ids of the batches to get statuses for

        Returns:
            dict: A dict with keys of batch ids, and values of status enums
        """
        with self._lock:
            return {b: self.get_status(b) for b in batch_ids}

    def get_invalid_txn_info(self, batch_id):
        """Fetches the id of the Transaction that failed within a particular
        Batch, as well as any error message or other data about the failure.

        Args:
            batch_id (str): The id of the Batch containing an invalid txn

        Returns:
            list of dict: A list of dicts with three possible keys:
                * 'id' - the header_signature of the invalid Transaction
                * 'message' - the error message sent by the TP
                * 'extended_data' - any additional data sent by the TP
        """
        with self._lock:
            return [info.copy() for info in self._invalid.get(batch_id, [])]

    def watch_statuses(self, observer, batch_ids):
        """Allows a component to register to be notified when a set of
        batches is no longer PENDING. Expects to be able to call the
        "notify_batches_finished" method on the registered component, sending
        the statuses of the batches.

        Args:
            observer (object): Must implement "notify_batches_finished" method
            batch_ids (list of str): The ids of the batches to watch
        """
        with self._lock:
            statuses = self.get_statuses(batch_ids)
            if self._has_no_pendings(statuses):
                observer.notify_batches_finished(statuses)
            else:
                self._observers[observer] = statuses

    def _update_observers(self, batch_id, status):
        """Updates each observer tracking a particular batch with its new
        status. If all statuses are no longer pending, notifies the observer
        and removes it from the list.
        """
        for observer, statuses in self._observers.copy().items():
            if batch_id in statuses:
                statuses[batch_id] = status
                if self._has_no_pendings(statuses):
                    observer.notify_batches_finished(statuses)
                    self._observers.pop(observer)

    def _has_no_pendings(self, statuses):
        """Returns True if a statuses dict has no PENDING statuses.
        """
        return all(s != ClientBatchStatus.PENDING for s in statuses.values())


class BatchFinishObserver(metaclass=abc.ABCMeta):
    """An interface class for components wishing to be notified by a
    BatchTracker whenever a set of batches is finished being processed.

    Observers register what batches they are interested in by calling  a
    BatchTracker's "watch_statuses" method.
    """

    @abc.abstractmethod
    def notify_batches_finished(self, statuses):
        """This method will be called when every Batch in a set of Batches is
        no longer PENDING. Each should be committed, invalid, or not found.

        Args:
            statuses (dict of int): A dict with keys of batch ids, and values
                of status enums
        """
        raise NotImplementedError('BatchFinishObservers must have a '
                                  '"notify_batches_finished" method')
