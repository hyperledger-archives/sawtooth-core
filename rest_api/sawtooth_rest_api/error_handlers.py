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
# ------------------------------------------------------------------------------

from sawtooth_rest_api.protobuf import client_transaction_pb2
from sawtooth_rest_api.protobuf import client_batch_submit_pb2
from sawtooth_rest_api.protobuf import client_state_pb2
from sawtooth_rest_api.protobuf import client_block_pb2
from sawtooth_rest_api.protobuf import client_batch_pb2
from sawtooth_rest_api.protobuf import client_receipt_pb2
import sawtooth_rest_api.exceptions as errors


class _ErrorTrap:
    """Provides an interface for route handlers to communicate specific
    response statuses they are interested in throwing an error on. Child
    classes should not define any methods, instead defining two class
    variables which the parent `check` method will reference. As `check` is
    a class method, there is no need to instantiate ErrorTraps.

    Attributes:
        trigger (int, enum): A protobuf enum status to check for.
        error (class): The type of error to raise.
    """
    trigger = None
    error = None

    @classmethod
    def check(cls, status):
        """Checks if a status enum matches the trigger originally set, and
        if so, raises the appropriate error.

        Args:
            status (int, enum): A protobuf enum response status to check.

        Raises:
            AssertionError: If trigger or error were not set.
            _ApiError: If the statuses don't match. Do not catch. Will be
                caught automatically and sent back to the client.
        """
        assert cls.trigger is not None, 'Invalid ErrorTrap, trigger not set'
        assert cls.error is not None, 'Invalid ErrorTrap, error not set'

        if status == cls.trigger:
            # pylint: disable=not-callable
            # cls.error will be callable at runtime
            raise cls.error()


class StatusResponseMissing(_ErrorTrap):
    trigger = client_batch_submit_pb2.ClientBatchStatusResponse.NO_RESOURCE
    error = errors.StatusResponseMissing


class BatchInvalidTrap(_ErrorTrap):
    trigger = client_batch_submit_pb2.ClientBatchSubmitResponse.INVALID_BATCH
    error = errors.SubmittedBatchesInvalid


class BatchQueueFullTrap(_ErrorTrap):
    trigger = client_batch_submit_pb2.ClientBatchSubmitResponse.QUEUE_FULL
    error = errors.BatchQueueFull


class InvalidAddressTrap(_ErrorTrap):
    trigger = client_state_pb2.ClientStateGetResponse.INVALID_ADDRESS
    error = errors.InvalidStateAddress


class BlockNotFoundTrap(_ErrorTrap):
    trigger = client_block_pb2.ClientBlockGetResponse.NO_RESOURCE
    error = errors.BlockNotFound


class BatchNotFoundTrap(_ErrorTrap):
    trigger = client_batch_pb2.ClientBatchGetResponse.NO_RESOURCE
    error = errors.BatchNotFound


class TransactionNotFoundTrap(_ErrorTrap):
    trigger = client_transaction_pb2.ClientTransactionGetResponse.NO_RESOURCE
    error = errors.TransactionNotFound


class ReceiptNotFoundTrap(_ErrorTrap):
    trigger = client_receipt_pb2.ClientReceiptGetResponse.NO_RESOURCE
    error = errors.ReceiptNotFound


class StateNotFoundTrap(_ErrorTrap):
    trigger = client_state_pb2.ClientStateGetResponse.NO_RESOURCE
    error = errors.StateNotFound
