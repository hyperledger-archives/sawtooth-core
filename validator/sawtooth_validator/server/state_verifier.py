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

import logging
import os

from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.state.merkle import INIT_ROOT_KEY

from sawtooth_validator.execution import tp_state_handlers
from sawtooth_validator.execution import processor_handlers

from sawtooth_validator.concurrent.threadpool import \
    InstrumentedThreadPoolExecutor
from sawtooth_validator.execution.context_manager import ContextManager

from sawtooth_validator.database.indexed_database import IndexedDatabase
from sawtooth_validator.database.native_lmdb import NativeLmdbDatabase

from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.networking.dispatch import Dispatcher
from sawtooth_validator.execution.executor import TransactionExecutor
from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.state.settings_view import SettingsViewFactory
from sawtooth_validator.state.state_view import StateViewFactory
from sawtooth_validator.networking.interconnect import Interconnect


LOGGER = logging.getLogger(__name__)


class InvalidChainError(Exception):
    pass


class ExecutionError(Exception):
    pass


def get_databases(bind_network, data_dir):
    # Get the global state database to operate on
    global_state_db_filename = os.path.join(
        data_dir, 'merkle-{}.lmdb'.format(bind_network[-2:]))
    LOGGER.debug(
        'verifying state in %s', global_state_db_filename)
    global_state_db = NativeLmdbDatabase(
        global_state_db_filename,
        indexes=MerkleDatabase.create_index_configuration())

    # Get the blockstore
    block_db_filename = os.path.join(
        data_dir, 'block-{}.lmdb'.format(bind_network[-2:]))
    LOGGER.debug('block store file is %s', block_db_filename)
    block_db = IndexedDatabase(
        block_db_filename,
        BlockStore.serialize_block,
        BlockStore.deserialize_block,
        flag='c',
        indexes=BlockStore.create_index_configuration())
    blockstore = BlockStore(block_db)

    return global_state_db, blockstore


def verify_state(global_state_db, blockstore, bind_component, scheduler_type):
    """
    Verify the state root hash of all blocks is in state and if not,
    reconstruct the missing state. Assumes that there are no "holes" in
    state, ie starting from genesis, state is present for all blocks up to some
    point and then not at all. If persist is False, this recomputes state in
    memory for all blocks in the blockstore and verifies the state root
    hashes.

    Raises:
        InvalidChainError: The chain in the blockstore is not valid.
        ExecutionError: An unrecoverable error was encountered during batch
            execution.
    """
    state_view_factory = StateViewFactory(global_state_db)

    # Check if we should do state verification
    start_block, prev_state_root = search_for_present_state_root(
        blockstore, state_view_factory)

    if start_block is None:
        LOGGER.info(
            "Skipping state verification: chain head's state root is present")
        return

    LOGGER.info(
        "Recomputing missing state from block %s with %s scheduler",
        start_block, scheduler_type)

    component_thread_pool = InstrumentedThreadPoolExecutor(
        max_workers=10,
        name='Component')

    component_dispatcher = Dispatcher()
    component_service = Interconnect(
        bind_component,
        component_dispatcher,
        secured=False,
        heartbeat=False,
        max_incoming_connections=20,
        monitor=True,
        max_future_callback_workers=10)

    context_manager = ContextManager(global_state_db)

    transaction_executor = TransactionExecutor(
        service=component_service,
        context_manager=context_manager,
        settings_view_factory=SettingsViewFactory(state_view_factory),
        scheduler_type=scheduler_type,
        invalid_observers=[])

    component_service.set_check_connections(
        transaction_executor.check_connections)

    component_dispatcher.add_handler(
        validator_pb2.Message.TP_RECEIPT_ADD_DATA_REQUEST,
        tp_state_handlers.TpReceiptAddDataHandler(context_manager),
        component_thread_pool)

    component_dispatcher.add_handler(
        validator_pb2.Message.TP_EVENT_ADD_REQUEST,
        tp_state_handlers.TpEventAddHandler(context_manager),
        component_thread_pool)

    component_dispatcher.add_handler(
        validator_pb2.Message.TP_STATE_DELETE_REQUEST,
        tp_state_handlers.TpStateDeleteHandler(context_manager),
        component_thread_pool)

    component_dispatcher.add_handler(
        validator_pb2.Message.TP_STATE_GET_REQUEST,
        tp_state_handlers.TpStateGetHandler(context_manager),
        component_thread_pool)

    component_dispatcher.add_handler(
        validator_pb2.Message.TP_STATE_SET_REQUEST,
        tp_state_handlers.TpStateSetHandler(context_manager),
        component_thread_pool)

    component_dispatcher.add_handler(
        validator_pb2.Message.TP_REGISTER_REQUEST,
        processor_handlers.ProcessorRegisterHandler(
            transaction_executor.processor_manager),
        component_thread_pool)

    component_dispatcher.add_handler(
        validator_pb2.Message.TP_UNREGISTER_REQUEST,
        processor_handlers.ProcessorUnRegisterHandler(
            transaction_executor.processor_manager),
        component_thread_pool)

    component_dispatcher.start()
    component_service.start()

    process_blocks(
        initial_state_root=prev_state_root,
        blocks=blockstore.get_block_iter(
            start_block=start_block, reverse=False),
        transaction_executor=transaction_executor,
        context_manager=context_manager,
        state_view_factory=state_view_factory)

    component_dispatcher.stop()
    component_service.stop()
    component_thread_pool.shutdown(wait=True)
    transaction_executor.stop()
    context_manager.stop()


def search_for_present_state_root(blockstore, state_view_factory):
    """
    Search through the blockstore and return a tuple containing:
        - the first block with a missing state root
        - the state root of that blocks predecessor
    """
    # If there is no chain to process, then we are done.
    block = blockstore.chain_head
    if block is None:
        return None, None

    # Check the head first
    if state_db_has_root(state_view_factory, block.state_root_hash):
        return None, None

    prev_state_root = INIT_ROOT_KEY
    for block in blockstore.get_block_iter(reverse=False):
        if not state_db_has_root(state_view_factory, block.state_root_hash):
            return block, prev_state_root
        prev_state_root = block.state_root_hash

    # This should never happen, since we already checked that the chain head
    # didn't have a state root
    raise ExecutionError(
        "Chain head state both missing but all blocks had state root present")


def state_db_has_root(state_view_factory, root):
    try:
        state_view_factory.create_view(root)
    except KeyError:
        return False
    return True


def process_blocks(
    initial_state_root,
    blocks,
    transaction_executor,
    context_manager,
    state_view_factory,
):
    prev_state_root = initial_state_root
    for block in blocks:
        LOGGER.info("Verifying state for block %s", block)
        try:
            # If we can create the view, all is good, move on to next block
            state_view_factory.create_view(block.state_root_hash)

        except KeyError:
            # If creating the view fails, the root is missing so we should
            # recompute it and verify it
            new_root = execute_batches(
                previous_state_root=prev_state_root,
                transaction_executor=transaction_executor,
                context_manager=context_manager,
                batches=block.batches)

            if new_root != block.state_root_hash:
                raise InvalidChainError(
                    "Computed state root {} does not match state root in block"
                    " {}".format(new_root, block.state_root_hash))

        prev_state_root = block.state_root_hash


def execute_batches(
    previous_state_root,
    transaction_executor,
    context_manager,
    batches
):
    scheduler = transaction_executor.create_scheduler(
        previous_state_root,
        always_persist=True)

    transaction_executor.execute(scheduler)

    for batch in batches:
        scheduler.add_batch(batch)

    scheduler.finalize()
    scheduler.complete(block=True)

    state_root = None
    for batch in batches:
        batch_id = batch.header_signature
        result = scheduler.get_batch_execution_result(batch_id)
        if result is None:
            raise ExecutionError(
                "Batch {} did not execute".format(batch_id))

        if not result.is_valid:
            raise ExecutionError(
                "Batch {} was invalid".format(batch_id))

        if result.state_hash is not None:
            if state_root is not None:
                raise ExecutionError(
                    "More than one batch had state root; First state root was"
                    " {}, second state root was from batch {} with state root"
                    " {}".format(state_root, batch_id, result.state_hash))

            state_root = result.state_hash

    if state_root is None:
        raise ExecutionError("No state root found in execution results")

    return state_root
