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

# pylint: disable=inconsistent-return-statements

import abc
import ctypes
import logging

from enum import IntEnum

from sawtooth_validator.ffi import PY_LIBRARY, LIBRARY
from sawtooth_validator.ffi import OwnedPointer

LOGGER = logging.getLogger(__name__)


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


class IncomingBatchSenderErrorCode(IntEnum):
    Success = 0
    NullPointerProvided = 0x01
    InvalidInput = 0x02
    Disconnected = 0x03


class Disconnected(Exception):
    """The receiving end of the IncomingBatchQueue hung up."""


class IncomingBatchSender(OwnedPointer):
    def __init__(self, sender_ptr):
        super().__init__("incoming_batch_sender_drop")
        self._ptr = sender_ptr

    def send(self, item):
        res = PY_LIBRARY.call(
            "incoming_batch_sender_send",
            self._ptr,
            ctypes.py_object(item))

        if res == IncomingBatchSenderErrorCode.Success:
            return
        elif res == IncomingBatchSenderErrorCode.NullPointerProvided:
            raise TypeError("Provided null pointer(s)")
        elif res == IncomingBatchSenderErrorCode.InvalidInput:
            raise ValueError("Input was not valid ")
        elif res == IncomingBatchSenderErrorCode.Disconnected:
            raise Disconnected()
        else:
            raise ValueError("An unknown error occurred: {}".format(res))


class ChainHeadLockErrorCode(IntEnum):
    Success = 0
    NullPointerProvided = 0x01


class ChainHeadLock(OwnedPointer):
    def __init__(self, chain_head_lock_ptr):
        super().__init__("chain_head_lock_drop")
        self._ptr = chain_head_lock_ptr
        self._guard = None

    def acquire(self):
        guard_ptr = ctypes.c_void_p()
        res = LIBRARY.call(
            "chain_head_lock_acquire",
            self._ptr,
            ctypes.byref(guard_ptr))

        if res == ChainHeadLockErrorCode.Success:
            self._guard = ChainHeadGuard(guard_ptr)
            return self._guard
        elif res == ChainHeadLockErrorCode.NullPointerProvided:
            raise TypeError("Provided null pointer(s)")
        else:
            raise ValueError("An unknown error occurred: {}".format(res))

    def release(self):
        res = LIBRARY.call(
            "chain_head_guard_drop",
            self._guard.pointer)

        if res == ChainHeadLockErrorCode.Success:
            return
        elif res == ChainHeadLockErrorCode.NullPointerProvided:
            raise TypeError("Provided null pointer(s)")
        else:
            raise ValueError("An unknown error occurred: {}".format(res))


class ChainHeadGuard:
    def __init__(self, guard_ptr):
        self.pointer = guard_ptr

    def notify_on_chain_updated(self,
                                chain_head,
                                committed_batches=None,
                                uncommitted_batches=None):
        res = LIBRARY.call(
            "chain_head_guard_on_chain_updated",
            self.pointer,
            ctypes.py_object(chain_head),
            ctypes.py_object(committed_batches),
            ctypes.py_object(uncommitted_batches))

        if res == ChainHeadLockErrorCode.Success:
            return
        elif res == ChainHeadLockErrorCode.NullPointerProvided:
            raise TypeError("Provided null pointer(s)")
        else:
            raise ValueError("An unknown error occurred: {}".format(res))


class BlockPublisherErrorCode(IntEnum):
    Success = 0
    NullPointerProvided = 0x01
    InvalidInput = 0x02


class BlockPublisher(OwnedPointer):
    """
    Responsible for generating new blocks and publishing them when the
    Consensus deems it appropriate.
    """

    def __init__(self,
                 transaction_executor,
                 block_cache,
                 state_view_factory,
                 settings_cache,
                 block_sender,
                 batch_sender,
                 chain_head,
                 identity_signer,
                 data_dir,
                 config_dir,
                 permission_verifier,
                 check_publish_block_frequency,
                 batch_observers,
                 batch_injector_factory=None):
        """
        Initialize the BlockPublisher object

        Args:
            transaction_executor (:obj:`TransactionExecutor`): A
                TransactionExecutor instance.
            block_cache (:obj:`BlockCache`): A BlockCache instance.
            state_view_factory (:obj:`StateViewFactory`): StateViewFactory for
                read-only state views.
            block_sender (:obj:`BlockSender`): The BlockSender instance.
            batch_sender (:obj:`BatchSender`): The BatchSender instance.
            chain_head (:obj:`BlockWrapper`): The initial chain head.
            chain_head_lock (:obj:`RLock`): The chain head lock.
            identity_signer (:obj:`Signer`): Cryptographic signer for signing
                blocks
            data_dir (str): path to location where persistent data for the
                consensus module can be stored.
            config_dir (str): path to location where configuration can be
                found.
            batch_injector_factory (:obj:`BatchInjectorFatctory`): A factory
                for creating BatchInjectors.
        """
        super(BlockPublisher, self).__init__('block_publisher_drop')

        self._to_exception(PY_LIBRARY.call(
            'block_publisher_new',
            ctypes.py_object(transaction_executor),
            ctypes.py_object(block_cache),
            ctypes.py_object(state_view_factory),
            ctypes.py_object(settings_cache),
            ctypes.py_object(block_sender),
            ctypes.py_object(batch_sender),
            ctypes.py_object(chain_head),
            ctypes.py_object(identity_signer),
            ctypes.py_object(data_dir),
            ctypes.py_object(config_dir),
            ctypes.py_object(permission_verifier),
            ctypes.py_object(check_publish_block_frequency * 1000),
            ctypes.py_object(batch_observers),
            ctypes.py_object(batch_injector_factory),
            ctypes.byref(self.pointer)))

    def _call(self, method, *args, library=LIBRARY):
        self._to_exception(library.call(
            'block_publisher_' + method,
            self.pointer,
            *args))

    def _py_call(self, method, *args):
        self._call(method, *args, library=PY_LIBRARY)

    @staticmethod
    def _to_exception(res):
        if res == BlockPublisherErrorCode.Success:
            return
        elif res == BlockPublisherErrorCode.NullPointerProvided:
            raise TypeError("Provided null pointer(s)")
        elif res == BlockPublisherErrorCode.InvalidInput:
            raise ValueError("Input was not valid ")

    def batch_sender(self):
        sender_ptr = ctypes.c_void_p()
        self._call(
            'batch_sender',
            ctypes.byref(sender_ptr))
        return IncomingBatchSender(sender_ptr)

    def start(self):
        self._call('start')

    def stop(self):
        self._call('stop')

    def pending_batch_info(self):
        """Returns a tuple of the current size of the pending batch queue
        and the current queue limit.
        """
        c_length = ctypes.c_int(0)
        c_limit = ctypes.c_int(0)
        self._call(
            'pending_batch_info',
            ctypes.byref(c_length),
            ctypes.byref(c_limit))

        return (c_length.value, c_limit.value)

    @property
    def chain_head_lock(self):
        chain_head_lock_ptr = ctypes.c_void_p()
        self._call('chain_head_lock', ctypes.byref(chain_head_lock_ptr))
        return ChainHeadLock(chain_head_lock_ptr)

    def on_chain_updated(self, chain_head,
                         committed_batches=None,
                         uncommitted_batches=None):
        """
        The existing chain has been updated, the current head block has
        changed.

        :param chain_head: the new head of block_chain, can be None if
        no block publishing is desired.
        :param committed_batches: the set of batches that were committed
         as part of the new chain.
        :param uncommitted_batches: the list of transactions if any that are
        now de-committed when the new chain was selected.
        :return: None
        """
        try:
            self._py_call(
                'on_chain_updated',
                ctypes.py_object(chain_head),
                ctypes.py_object(committed_batches),
                ctypes.py_object(uncommitted_batches))

        # pylint: disable=broad-except
        except Exception:
            LOGGER.exception(
                "Unhandled exception in BlockPublisher.on_chain_updated")

    def has_batch(self, batch_id):
        has = ctypes.c_bool(False)
        c_batch_id = ctypes.c_char_p(batch_id.encode())

        self._call(
            'has_batch',
            c_batch_id,
            ctypes.byref(has))

        return has
