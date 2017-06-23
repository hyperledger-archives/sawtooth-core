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

from concurrent.futures import ThreadPoolExecutor
import hashlib
import logging
import os
import signal
import time
import threading

from sawtooth_validator.execution.context_manager import ContextManager
from sawtooth_validator.database.lmdb_nolock_database import LMDBNoLockDatabase
from sawtooth_validator.journal.genesis import GenesisController
from sawtooth_validator.journal.journal import Journal
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.execution import tp_state_handlers
from sawtooth_validator.journal.batch_sender import BroadcastBatchSender
from sawtooth_validator.journal.block_sender import BroadcastBlockSender
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.completer import CompleterGossipHandler
from sawtooth_validator.journal.completer import \
    CompleterGossipBlockResponseHandler
from sawtooth_validator.journal.completer import \
    CompleterGossipBatchResponseHandler
from sawtooth_validator.journal.completer import \
    CompleterBatchListBroadcastHandler
from sawtooth_validator.journal.completer import Completer
from sawtooth_validator.gossip import structure_verifier
from sawtooth_validator.journal.responder import Responder
from sawtooth_validator.journal.responder import BlockResponderHandler
from sawtooth_validator.journal.responder import ResponderBlockResponseHandler
from sawtooth_validator.journal.responder import BatchByBatchIdResponderHandler
from sawtooth_validator.journal.responder import ResponderBatchResponseHandler
from sawtooth_validator.journal.responder import \
    BatchByTransactionIdResponderHandler
from sawtooth_validator.networking.dispatch import Dispatcher
from sawtooth_validator.journal.chain_id_manager import ChainIdManager
from sawtooth_validator.execution.executor import TransactionExecutor
from sawtooth_validator.execution import processor_handlers
from sawtooth_validator.state import client_handlers
from sawtooth_validator.state.batch_tracker import BatchTracker
from sawtooth_validator.state.settings_view import SettingsViewFactory
from sawtooth_validator.state.state_delta_processor import StateDeltaProcessor
from sawtooth_validator.state.state_delta_processor import \
    StateDeltaAddSubscriberHandler
from sawtooth_validator.state.state_delta_processor import \
    StateDeltaSubscriberValidationHandler
from sawtooth_validator.state.state_delta_processor import \
    StateDeltaUnsubscriberHandler
from sawtooth_validator.state.state_delta_processor import \
    GetStateDeltaEventsHandler
from sawtooth_validator.state.state_delta_store import StateDeltaStore
from sawtooth_validator.state.state_view import StateViewFactory
from sawtooth_validator.gossip import signature_verifier
from sawtooth_validator.gossip.permission_verifier import \
    BatchListPermissionVerifier
from sawtooth_validator.networking.interconnect import Interconnect
from sawtooth_validator.gossip.gossip import Gossip
from sawtooth_validator.gossip.gossip_handlers import GossipBroadcastHandler
from sawtooth_validator.gossip.gossip_handlers import GossipMessageHandler
from sawtooth_validator.gossip.gossip_handlers import \
    GossipBlockResponseHandler
from sawtooth_validator.gossip.gossip_handlers import \
    GossipBatchResponseHandler
from sawtooth_validator.gossip.gossip_handlers import PeerRegisterHandler
from sawtooth_validator.gossip.gossip_handlers import PeerUnregisterHandler
from sawtooth_validator.gossip.gossip_handlers import GetPeersRequestHandler
from sawtooth_validator.gossip.gossip_handlers import GetPeersResponseHandler
from sawtooth_validator.networking.handlers import PingHandler
from sawtooth_validator.networking.handlers import ConnectHandler
from sawtooth_validator.networking.handlers import DisconnectHandler


LOGGER = logging.getLogger(__name__)


class Validator(object):
    def __init__(self, bind_network, bind_component, endpoint,
                 peering, seeds_list, peer_list, data_dir, config_dir,
                 identity_signing_key, network_public_key=None,
                 network_private_key=None):
        """Constructs a validator instance.

        Args:
            bind_network (str): the network endpoint
            bind_component (str): the component endpoint
            endpoint (str): the zmq-style URI of this validator's
                publically reachable endpoint
            peering (str): The type of peering approach. Either 'static'
                or 'dynamic'. In 'static' mode, no attempted topology
                buildout occurs -- the validator only attempts to initiate
                peering connections with endpoints specified in the
                peer_list. In 'dynamic' mode, the validator will first
                attempt to initiate peering connections with endpoints
                specified in the peer_list and then attempt to do a
                topology buildout starting with peer lists obtained from
                endpoints in the seeds_list. In either mode, the validator
                will accept incoming peer requests up to max_peers.
            seeds_list (list of str): a list of addresses to connect
                to in order to perform the initial topology buildout
            peer_list (list of str): a list of peer addresses
            data_dir (str): path to the data directory
            config_dir (str): path to the config directory
            identity_signing_key (str): key validator uses for signing
        """
        db_filename = os.path.join(data_dir,
                                   'merkle-{}.lmdb'.format(
                                       bind_network[-2:]))
        LOGGER.debug('database file is %s', db_filename)

        merkle_db = LMDBNoLockDatabase(db_filename, 'c')

        delta_db_filename = os.path.join(data_dir,
                                         'state-deltas-{}.lmdb'.format(
                                             bind_network[-2:]))
        LOGGER.debug('state delta store file is %s', delta_db_filename)
        state_delta_db = LMDBNoLockDatabase(delta_db_filename, 'c')

        state_delta_store = StateDeltaStore(state_delta_db)

        context_manager = ContextManager(merkle_db, state_delta_store)
        self._context_manager = context_manager

        state_view_factory = StateViewFactory(merkle_db)

        block_db_filename = os.path.join(data_dir, 'block-{}.lmdb'.format(
                                         bind_network[-2:]))
        LOGGER.debug('block store file is %s', block_db_filename)

        block_db = LMDBNoLockDatabase(block_db_filename, 'c')
        block_store = BlockStore(block_db)

        batch_tracker = BatchTracker(block_store)
        block_store.add_update_observer(batch_tracker)

        # setup network
        self._dispatcher = Dispatcher()

        thread_pool = ThreadPoolExecutor(max_workers=10)
        sig_pool = ThreadPoolExecutor(max_workers=3)

        self._thread_pool = thread_pool
        self._sig_pool = sig_pool

        self._service = Interconnect(bind_component,
                                     self._dispatcher,
                                     secured=False,
                                     heartbeat=False,
                                     max_incoming_connections=20,
                                     monitor=True)

        executor = TransactionExecutor(
            service=self._service,
            context_manager=context_manager,
            settings_view_factory=SettingsViewFactory(
                StateViewFactory(merkle_db)),
            invalid_observers=[batch_tracker])
        self._executor = executor
        self._service.set_check_connections(executor.check_connections)

        state_delta_processor = StateDeltaProcessor(self._service,
                                                    state_delta_store,
                                                    block_store)

        zmq_identity = hashlib.sha512(
            time.time().hex().encode()).hexdigest()[:23]

        network_thread_pool = ThreadPoolExecutor(max_workers=10)
        self._network_thread_pool = network_thread_pool

        self._network_dispatcher = Dispatcher()

        secure = False
        if network_public_key is not None and network_private_key is not None:
            secure = True

        self._network = Interconnect(
            bind_network,
            dispatcher=self._network_dispatcher,
            zmq_identity=zmq_identity,
            secured=secure,
            server_public_key=network_public_key,
            server_private_key=network_private_key,
            heartbeat=True,
            public_endpoint=endpoint,
            connection_timeout=30,
            max_incoming_connections=100)

        self._gossip = Gossip(self._network,
                              endpoint=endpoint,
                              peering_mode=peering,
                              initial_seed_endpoints=seeds_list,
                              initial_peer_endpoints=peer_list,
                              minimum_peer_connectivity=3,
                              maximum_peer_connectivity=10,
                              topology_check_frequency=1)

        completer = Completer(block_store, self._gossip)

        block_sender = BroadcastBlockSender(completer, self._gossip)
        batch_sender = BroadcastBatchSender(completer, self._gossip)
        chain_id_manager = ChainIdManager(data_dir)
        # Create and configure journal
        self._journal = Journal(
            block_store=block_store,
            state_view_factory=StateViewFactory(merkle_db),
            block_sender=block_sender,
            batch_sender=batch_sender,
            transaction_executor=executor,
            squash_handler=context_manager.get_squash_handler(),
            identity_signing_key=identity_signing_key,
            chain_id_manager=chain_id_manager,
            state_delta_processor=state_delta_processor,
            data_dir=data_dir,
            config_dir=config_dir,
            check_publish_block_frequency=0.1,
            block_cache_purge_frequency=30,
            block_cache_keep_time=300,
            batch_observers=[batch_tracker]
        )

        self._genesis_controller = GenesisController(
            context_manager=context_manager,
            transaction_executor=executor,
            completer=completer,
            block_store=block_store,
            state_view_factory=state_view_factory,
            identity_key=identity_signing_key,
            data_dir=data_dir,
            config_dir=config_dir,
            chain_id_manager=chain_id_manager,
            batch_sender=batch_sender
        )

        responder = Responder(completer)

        completer.set_on_batch_received(self._journal.on_batch_received)
        completer.set_on_block_received(self._journal.on_block_received)

        self._dispatcher.add_handler(
            validator_pb2.Message.TP_STATE_GET_REQUEST,
            tp_state_handlers.TpStateGetHandler(context_manager),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.TP_STATE_SET_REQUEST,
            tp_state_handlers.TpStateSetHandler(context_manager),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.TP_REGISTER_REQUEST,
            processor_handlers.ProcessorRegisterHandler(executor.processors),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.TP_UNREGISTER_REQUEST,
            processor_handlers.ProcessorUnRegisterHandler(executor.processors),
            thread_pool)

        # Set up base network handlers
        self._network_dispatcher.add_handler(
            validator_pb2.Message.NETWORK_PING,
            PingHandler(),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.NETWORK_CONNECT,
            ConnectHandler(network=self._network),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.NETWORK_DISCONNECT,
            DisconnectHandler(network=self._network),
            network_thread_pool)

        # Set up gossip handlers
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_GET_PEERS_REQUEST,
            GetPeersRequestHandler(gossip=self._gossip),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_GET_PEERS_RESPONSE,
            GetPeersResponseHandler(gossip=self._gossip),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_REGISTER,
            PeerRegisterHandler(gossip=self._gossip),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_UNREGISTER,
            PeerUnregisterHandler(gossip=self._gossip),
            network_thread_pool)

        # GOSSIP_MESSAGE 1) Sends acknowledgement to the sender
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_MESSAGE,
            GossipMessageHandler(),
            network_thread_pool)

        # GOSSIP_MESSAGE 2) Verifies signature
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_MESSAGE,
            signature_verifier.GossipMessageSignatureVerifier(),
            sig_pool)

        # GOSSIP_MESSAGE 3) Verifies batch structure
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_MESSAGE,
            structure_verifier.GossipHandlerStructureVerifier(),
            network_thread_pool)

        # GOSSIP_MESSAGE 4) Determines if we should broadcast the
        # message to our peers. It is important that this occur prior
        # to the sending of the message to the completer, as this step
        # relies on whether the  gossip message has previously been
        # seen by the validator to determine whether or not forwarding
        # should occur
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_MESSAGE,
            GossipBroadcastHandler(
                gossip=self._gossip,
                completer=completer),
            network_thread_pool)

        # GOSSIP_MESSAGE 5) Send message to completer
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_MESSAGE,
            CompleterGossipHandler(
                completer),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BLOCK_REQUEST,
            BlockResponderHandler(responder, self._gossip),
            network_thread_pool)

        # GOSSIP_BLOCK_RESPONSE 1) Sends ack to the sender
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BLOCK_RESPONSE,
            GossipBlockResponseHandler(),
            network_thread_pool)

        # GOSSIP_BLOCK_RESPONSE 2) Verifies signature
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BLOCK_RESPONSE,
            signature_verifier.GossipBlockResponseSignatureVerifier(),
            sig_pool)

        # GOSSIP_BLOCK_RESPONSE 3) Check batch structure
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BLOCK_RESPONSE,
            structure_verifier.GossipBlockResponseStructureVerifier(),
            network_thread_pool)

        # GOSSIP_BLOCK_RESPONSE 4) Send message to completer
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BLOCK_RESPONSE,
            CompleterGossipBlockResponseHandler(
                completer),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BLOCK_RESPONSE,
            ResponderBlockResponseHandler(responder, self._gossip),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BATCH_BY_BATCH_ID_REQUEST,
            BatchByBatchIdResponderHandler(responder, self._gossip),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BATCH_BY_TRANSACTION_ID_REQUEST,
            BatchByTransactionIdResponderHandler(responder, self._gossip),
            network_thread_pool)

        # GOSSIP_BATCH_RESPONSE 1) Sends ack to the sender
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
            GossipBatchResponseHandler(),
            network_thread_pool)

        # GOSSIP_BATCH_RESPONSE 2) Verifies signature
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
            signature_verifier.GossipBatchResponseSignatureVerifier(),
            sig_pool)

        # GOSSIP_BATCH_RESPONSE 3) Check batch structure
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
            structure_verifier.GossipBatchResponseStructureVerifier(),
            network_thread_pool)

        # GOSSIP_BATCH_RESPONSE 4) Send message to completer
        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
            CompleterGossipBatchResponseHandler(
                completer),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BATCH_RESPONSE,
            ResponderBatchResponseHandler(responder, self._gossip),
            network_thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
            BatchListPermissionVerifier(
                settings_view_factory=SettingsViewFactory(
                    StateViewFactory(merkle_db)),
                current_root_func=self._journal.get_current_root,
            ),
            sig_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
            signature_verifier.BatchListSignatureVerifier(),
            sig_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
            structure_verifier.BatchListStructureVerifier(),
            network_thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
            CompleterBatchListBroadcastHandler(
                completer, self._gossip),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
            client_handlers.BatchSubmitFinisher(batch_tracker),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_BATCH_STATUS_REQUEST,
            client_handlers.BatchStatusRequest(batch_tracker),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_STATE_LIST_REQUEST,
            client_handlers.StateListRequest(
                merkle_db,
                self._journal.get_block_store()),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_STATE_GET_REQUEST,
            client_handlers.StateGetRequest(
                merkle_db,
                self._journal.get_block_store()),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_BLOCK_LIST_REQUEST,
            client_handlers.BlockListRequest(self._journal.get_block_store()),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_BLOCK_GET_REQUEST,
            client_handlers.BlockGetRequest(self._journal.get_block_store()),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_BATCH_LIST_REQUEST,
            client_handlers.BatchListRequest(self._journal.get_block_store()),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_BATCH_GET_REQUEST,
            client_handlers.BatchGetRequest(self._journal.get_block_store()),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_TRANSACTION_LIST_REQUEST,
            client_handlers.TransactionListRequest(
                self._journal.get_block_store()),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_TRANSACTION_GET_REQUEST,
            client_handlers.TransactionGetRequest(
                self._journal.get_block_store()),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_STATE_CURRENT_REQUEST,
            client_handlers.StateCurrentRequest(
                self._journal.get_current_root), thread_pool)

        # State Delta Subscription Handlers
        self._dispatcher.add_handler(
            validator_pb2.Message.STATE_DELTA_SUBSCRIBE_REQUEST,
            StateDeltaSubscriberValidationHandler(state_delta_processor),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.STATE_DELTA_SUBSCRIBE_REQUEST,
            StateDeltaAddSubscriberHandler(state_delta_processor),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.STATE_DELTA_UNSUBSCRIBE_REQUEST,
            StateDeltaUnsubscriberHandler(state_delta_processor),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.STATE_DELTA_GET_EVENTS_REQUEST,
            GetStateDeltaEventsHandler(block_store, state_delta_store),
            thread_pool)

    def start(self):
        self._dispatcher.start()
        self._service.start()
        if self._genesis_controller.requires_genesis():
            self._genesis_controller.start(self._start)
        else:
            self._start()

    def _start(self):
        self._network_dispatcher.start()
        self._network.start()

        self._gossip.start()
        self._journal.start()

        signal_event = threading.Event()

        signal.signal(signal.SIGTERM,
                      lambda sig, fr: signal_event.set())
        # This is where the main thread will be during the bulk of the
        # validator's life.
        while not signal_event.is_set():
            signal_event.wait(timeout=20)

    def stop(self):
        self._gossip.stop()
        self._dispatcher.stop()
        self._network_dispatcher.stop()
        self._network.stop()

        self._service.stop()

        self._network_thread_pool.shutdown(wait=True)
        self._thread_pool.shutdown(wait=True)
        self._sig_pool.shutdown(wait=True)

        self._executor.stop()
        self._context_manager.stop()

        self._journal.stop()

        threads = threading.enumerate()

        # This will remove the MainThread, which will exit when we exit with
        # a sys.exit() or exit of main().
        threads.remove(threading.current_thread())

        while threads:
            if len(threads) < 4:
                LOGGER.info(
                    "remaining threads: %s",
                    ", ".join(
                        ["{} ({})".format(x.name, x.__class__.__name__)
                         for x in threads]))
            for t in threads.copy():
                if not t.is_alive():
                    t.join()
                    threads.remove(t)
                if threads:
                    time.sleep(1)

        LOGGER.info("All threads have been stopped and joined")
