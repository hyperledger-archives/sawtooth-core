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

import abc


class PendingBatchObserver(metaclass=abc.ABCMeta):
    """An interface class for components wishing to be notified when a Batch
    has begun being processed.
    """

    @abc.abstractmethod
    def notify_batch_pending(self, batch):
        """This method will be called when a Batch has passed initial
        validation and is queued to be processed by the Publisher.

        Args:
            batch (Batch): The Batch that has been added to the Publisher
        """
        raise NotImplementedError('PendingBatchObservers must have a '
                                  '"notify_batch_pending" method')


class InvalidTransactionObserver(metaclass=abc.ABCMeta):
    """An interface class for components wishing to be notified when a
    Transaction Processor finds a Transaction is invalid.
    """

    @abc.abstractmethod
    def notify_txn_invalid(self, txn_id, message=None, extended_data=None):
        """This method will be called when a Transaction Processor sends back
        a Transaction with the status INVALID_TRANSACTION, and includes any
        error message or extended data sent back.

        Args:
            txn_id (str): The id of the invalid Transaction
            message (str, optional): Message explaining why it is invalid
            extended_data (bytes, optional): Additional error data
        """
        raise NotImplementedError('InvalidTransactionObservers must have a '
                                  '"notify_txn_invalid" method')
