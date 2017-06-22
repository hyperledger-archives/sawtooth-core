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
from sawtooth_validator.journal.block_store import StoreUpdateObserver
from sawtooth_validator.journal.journal import PendingBatchObserver
from sawtooth_validator.protobuf.client_pb2 import BatchStatus


# By default pending batch ids will be kept for one hour
PENDING_KEEP_TIME = 3600


class BatchTracker(StoreUpdateObserver, PendingBatchObserver):
    """Tracks batch statuses for this local validator, allowing interested
    components to check where a batch is in the validation process. It should
    only be relied on for batches submitted locally, and is not persisted
    after restart.

    When a batch moves from one component to another, the appropriate notify
    method should be called in the appropriate component, as specified by the
    relevant Observer class, and implemented here.

    Args:
        block_store (BlockStore): For querying if a batch is committed
    """
    def __init__(self, block_store):
        self._block_store = block_store
        self._pending = TimedCache(keep_time=PENDING_KEEP_TIME)

        self._lock = RLock()
        self._observers = {}

    def notify_store_updated(self):
        """Removes batches from the pending cache if found in the block store,
        and notifies any observers.
        """
        with self._lock:
            for batch_id in set(self._pending):
                if self._block_store.has_batch(batch_id):
                    self._pending.pop(batch_id)
                    self._update_observers(batch_id, BatchStatus.COMMITTED)

    def notify_batch_pending(self, batch_id):
        """Adds a batch to the pending list.

        Args:
            batch_id (str): The id of the pending batch
        """
        with self._lock:
            self._pending[batch_id] = True
            self._update_observers(batch_id, BatchStatus.PENDING)

    def get_status(self, batch_id):
        """Returns the status enum for a batch.

        Args:
            batch_id (str): The id of the batch to get the status for

        Returns:
            int: The status enum
        """
        with self._lock:
            if self._block_store.has_batch(batch_id):
                return BatchStatus.COMMITTED
            if batch_id in self._pending:
                return BatchStatus.PENDING
            return BatchStatus.UNKNOWN

    def get_statuses(self, batch_ids):
        """Returns a statuses dict for the requested batches.

        Args:
            batch_ids (list of str): The ids of the batches to get statuses for

        Returns:
            dict: A dict with keys of batch ids, and values of status enums
        """
        with self._lock:
            return {b: self.get_status(b) for b in batch_ids}

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
                observer.notify_finished(statuses)
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
        return all(s != BatchStatus.PENDING for s in statuses.values())


class BatchFinishObserver(metaclass=abc.ABCMeta):
    """An interface class for components wishing to be notified by a
    BatchTracker whenever a set of batches is finished being processed.

    Observers register what batches they are interested in by calling  a
    BatchTracker's "watch_statuses" method.
    """
    @abc.abstractmethod
    def notify_batches_finished(self, statuses):
        """This method will be called when every Batch in a set of Batches is
        no longer PENDING. Each should be committed or not found.

        Args:
            statuses (dict of int): A dict with keys of batch ids, and values
                of status enums
        """
        raise NotImplementedError('BatchFinishObservers must have a '
                                  '"notify_batches_finished" method')
