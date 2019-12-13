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

from sawtooth_validator import ffi
from sawtooth_validator.ffi import PY_LIBRARY, LIBRARY
from sawtooth_validator.ffi import OwnedPointer

from sawtooth_validator.journal.block_wrapper import BlockWrapper

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
        res = LIBRARY.call(
            "incoming_batch_sender_send",
            self._ptr,
            ctypes.py_object(item))

        if res == IncomingBatchSenderErrorCode.Success:
            return

        if res == IncomingBatchSenderErrorCode.NullPointerProvided:
            raise TypeError("Provided null pointer(s)")
        if res == IncomingBatchSenderErrorCode.InvalidInput:
            raise ValueError("Input was not valid ")
        if res == IncomingBatchSenderErrorCode.Disconnected:
            raise Disconnected()

        raise ValueError("An unknown error occurred: {}".format(res))

    def has_batch(self, batch_id):
        has = ctypes.c_bool(False)
        c_batch_id = ctypes.c_char_p(batch_id.encode())

        LIBRARY.call(
            'incoming_batch_sender_has_batch',
            self.pointer,
            c_batch_id,
            ctypes.byref(has))

        return has


class ChainHeadLockErrorCode(IntEnum):
    Success = 0
    NullPointerProvided = 0x01


class ChainHeadLock(OwnedPointer):
    def __init__(self, chain_head_lock_ptr):
        super().__init__("chain_head_lock_drop")
        self._ptr = chain_head_lock_ptr
        self._guard = None


class BlockPublisherErrorCode(IntEnum):
    Success = 0
    NullPointerProvided = 0x01
    InvalidInput = 0x02
    BlockInProgress = 0x03
    BlockNotInitialized = 0x04
    BlockEmpty = 0x05
    MissingPredecessor = 0x07


class BlockEmpty(Exception):
    """There are no batches in the block."""


class BlockInProgress(Exception):
    """There is already a block in progress."""


class BlockNotInitialized(Exception):
    """There is no block in progress to finalize."""


class MissingPredecessor(Exception):
    """A predecessor was missing"""


class BlockPublisher(OwnedPointer):
    """
    Responsible for generating new blocks and publishing them when the
    Consensus deems it appropriate.
    """

    def __init__(self,
                 block_store,
                 block_manager,
                 transaction_executor,
                 state_view_factory,
                 block_sender,
                 batch_sender,
                 identity_signer,
                 data_dir,
                 config_dir,
                 permission_verifier,
                 batch_observers,
                 batch_injector_factory=None):
        """
        Initialize the BlockPublisher object

        Args:
            block_store (:obj: `BlockStore`): A BlockStore instance
            block_manager (:obj:`BlockManager`): A BlockManager instance
            transaction_executor (:obj:`TransactionExecutor`): A
                TransactionExecutor instance.
            state_view_factory (:obj:`NativeStateViewFactory`):
                NativeStateViewFactory for read-only state views.
            block_sender (:obj:`BlockSender`): The BlockSender instance.
            batch_sender (:obj:`BatchSender`): The BatchSender instance.
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

        if block_store.chain_head is not None:
            chain_head = BlockWrapper.wrap(block_store.chain_head)
            chain_head_block = chain_head.block
        else:
            chain_head_block = None

        self._to_exception(PY_LIBRARY.call(
            'block_publisher_new',
            block_store.pointer,
            block_manager.pointer,
            ctypes.py_object(transaction_executor),
            state_view_factory.pointer,
            ctypes.py_object(block_sender),
            ctypes.py_object(batch_sender),
            ctypes.py_object(chain_head_block),
            ctypes.py_object(identity_signer),
            ctypes.py_object(data_dir),
            ctypes.py_object(config_dir),
            ctypes.py_object(permission_verifier),
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
        if res == BlockPublisherErrorCode.NullPointerProvided:
            raise TypeError("Provided null pointer(s)")
        if res == BlockPublisherErrorCode.InvalidInput:
            raise ValueError("Input was not valid ")
        elif res == BlockPublisherErrorCode.BlockInProgress:
            raise BlockInProgress("A block is already in progress")
        elif res == BlockPublisherErrorCode.BlockNotInitialized:
            raise BlockNotInitialized("A block is not initialized")
        elif res == BlockPublisherErrorCode.BlockEmpty:
            raise BlockEmpty("The block is empty")
        elif res == BlockPublisherErrorCode.MissingPredecessor:
            raise MissingPredecessor("A predecessor was missing")

    def start(self):
        sender_ptr = ctypes.c_void_p()
        self._call('start', ctypes.byref(sender_ptr))
        return IncomingBatchSender(sender_ptr)

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

    def on_batch_received(self, batch):
        self._py_call(
            'on_batch_received',
            ctypes.py_object(batch))

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

    def initialize_block(self, block):
        self._call('initialize_block', ctypes.py_object(block))

    def summarize_block(self, force=False):
        (vec_ptr, vec_len, vec_cap) = ffi.prepare_vec_result()
        self._call(
            'summarize_block',
            ctypes.c_bool(force),
            ctypes.byref(vec_ptr),
            ctypes.byref(vec_len),
            ctypes.byref(vec_cap))

        return ffi.from_rust_vec(vec_ptr, vec_len, vec_cap)

    def finalize_block(self, consensus=None, force=False):
        (vec_ptr, vec_len, vec_cap) = ffi.prepare_vec_result()
        self._call(
            'finalize_block',
            consensus, len(consensus),
            ctypes.c_bool(force),
            ctypes.byref(vec_ptr),
            ctypes.byref(vec_len),
            ctypes.byref(vec_cap))

        return ffi.from_rust_vec(vec_ptr, vec_len, vec_cap).decode('utf-8')

    def cancel_block(self):
        self._call("cancel_block")
