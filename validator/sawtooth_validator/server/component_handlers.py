# Copyright 2016, 2017 Intel Corporation
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

from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.execution import tp_state_handlers

from sawtooth_validator.journal.completer import \
    CompleterBatchListBroadcastHandler
from sawtooth_validator.journal.back_pressure_handlers import \
    ClientBatchSubmitBackpressureHandler

from sawtooth_validator.gossip import structure_verifier

from sawtooth_validator.execution import processor_handlers
from sawtooth_validator.state import client_handlers

from sawtooth_validator.gossip import signature_verifier

from sawtooth_validator.gossip.permission_verifier import \
    BatchListPermissionVerifier

from sawtooth_validator.server.events.handlers import \
    ClientEventsGetRequestHandler
from sawtooth_validator.server.events.handlers \
    import ClientEventsSubscribeHandler
from sawtooth_validator.server.events.handlers \
    import ClientEventsSubscribeValidationHandler
from sawtooth_validator.server.events.handlers \
    import ClientEventsUnsubscribeHandler

from sawtooth_validator.journal.receipt_store \
    import ClientReceiptGetRequestHandler

LOGGER = logging.getLogger(__name__)


def add(
        dispatcher,
        gossip,
        context_manager,
        executor,
        completer,
        block_store,
        batch_tracker,
        merkle_db,
        get_current_root,
        receipt_store,
        event_broadcaster,
        permission_verifier,
        thread_pool,
        client_thread_pool,
        sig_pool,
        block_publisher,
        public_key,
):

    # -- Transaction Processor -- #
    dispatcher.add_handler(
        validator_pb2.Message.TP_RECEIPT_ADD_DATA_REQUEST,
        tp_state_handlers.TpReceiptAddDataHandler(context_manager),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.TP_EVENT_ADD_REQUEST,
        tp_state_handlers.TpEventAddHandler(context_manager),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.TP_STATE_DELETE_REQUEST,
        tp_state_handlers.TpStateDeleteHandler(context_manager),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.TP_STATE_GET_REQUEST,
        tp_state_handlers.TpStateGetHandler(context_manager),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.TP_STATE_SET_REQUEST,
        tp_state_handlers.TpStateSetHandler(context_manager),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.TP_REGISTER_REQUEST,
        processor_handlers.ProcessorRegisterHandler(
            executor.processor_manager),
        thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.TP_UNREGISTER_REQUEST,
        processor_handlers.ProcessorUnRegisterHandler(
            executor.processor_manager),
        thread_pool)

    # -- Client -- #
    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
        BatchListPermissionVerifier(
            permission_verifier=permission_verifier
        ),
        sig_pool)

    # Submit
    dispatcher.set_preprocessor(
        validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
        client_handlers.client_batch_submit_request_preprocessor,
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
        ClientBatchSubmitBackpressureHandler(
            public_key,
            block_publisher.pending_batch_info),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
        signature_verifier.BatchListSignatureVerifier(),
        sig_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
        structure_verifier.BatchListStructureVerifier(),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
        CompleterBatchListBroadcastHandler(
            completer, gossip),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
        client_handlers.BatchSubmitFinisher(batch_tracker),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BATCH_STATUS_REQUEST,
        client_handlers.BatchStatusRequest(batch_tracker),
        client_thread_pool)

    # State
    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_STATE_LIST_REQUEST,
        client_handlers.StateListRequest(
            merkle_db,
            block_store),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_STATE_GET_REQUEST,
        client_handlers.StateGetRequest(
            merkle_db,
            block_store),
        client_thread_pool)

    # Blocks
    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BLOCK_LIST_REQUEST,
        client_handlers.BlockListRequest(block_store),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BLOCK_GET_BY_ID_REQUEST,
        client_handlers.BlockGetByIdRequest(block_store),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BLOCK_GET_BY_NUM_REQUEST,
        client_handlers.BlockGetByNumRequest(block_store),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BLOCK_GET_BY_BATCH_ID_REQUEST,
        client_handlers.BlockGetByBatchRequest(block_store),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BLOCK_GET_BY_TRANSACTION_ID_REQUEST,
        client_handlers.BlockGetByTransactionRequest(block_store),
        client_thread_pool)

    # Batches
    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BATCH_LIST_REQUEST,
        client_handlers.BatchListRequest(block_store),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_BATCH_GET_REQUEST,
        client_handlers.BatchGetRequest(block_store),
        client_thread_pool)

    # Transactions
    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_TRANSACTION_LIST_REQUEST,
        client_handlers.TransactionListRequest(
            block_store),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_TRANSACTION_GET_REQUEST,
        client_handlers.TransactionGetRequest(
            block_store),
        client_thread_pool)

    # Receipts
    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_RECEIPT_GET_REQUEST,
        ClientReceiptGetRequestHandler(receipt_store),
        client_thread_pool)

    # Events
    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_EVENTS_SUBSCRIBE_REQUEST,
        ClientEventsSubscribeValidationHandler(event_broadcaster),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_EVENTS_SUBSCRIBE_REQUEST,
        ClientEventsSubscribeHandler(event_broadcaster),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_EVENTS_UNSUBSCRIBE_REQUEST,
        ClientEventsUnsubscribeHandler(event_broadcaster),
        client_thread_pool)

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_EVENTS_GET_REQUEST,
        ClientEventsGetRequestHandler(event_broadcaster),
        client_thread_pool)

    # Peers

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_PEERS_GET_REQUEST,
        client_handlers.PeersGetRequest(gossip),
        thread_pool)

    # Status

    dispatcher.add_handler(
        validator_pb2.Message.CLIENT_STATUS_GET_REQUEST,
        client_handlers.StatusGetRequest(gossip),
        thread_pool)
