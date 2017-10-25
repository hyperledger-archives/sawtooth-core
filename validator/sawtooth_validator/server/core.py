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

import sawtooth_signing as signing

from sawtooth_validator.execution.context_manager import ContextManager
from sawtooth_validator.database.lmdb_nolock_database import LMDBNoLockDatabase
from sawtooth_validator.journal.genesis import GenesisController
from sawtooth_validator.journal.journal import Journal
from sawtooth_validator.journal.batch_sender import BroadcastBatchSender
from sawtooth_validator.journal.block_sender import BroadcastBlockSender
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.completer import Completer
from sawtooth_validator.journal.responder import Responder
from sawtooth_validator.networking.dispatch import Dispatcher
from sawtooth_validator.journal.chain_id_manager import ChainIdManager
from sawtooth_validator.execution.executor import TransactionExecutor
from sawtooth_validator.state.batch_tracker import BatchTracker
from sawtooth_validator.state.settings_view import SettingsViewFactory
from sawtooth_validator.state.identity_view import IdentityViewFactory
from sawtooth_validator.state.state_delta_processor import StateDeltaProcessor
from sawtooth_validator.state.state_delta_store import StateDeltaStore
from sawtooth_validator.state.state_view import StateViewFactory
from sawtooth_validator.gossip.permission_verifier import PermissionVerifier
from sawtooth_validator.gossip.permission_verifier import IdentityCache
from sawtooth_validator.gossip.identity_observer import IdentityObserver
from sawtooth_validator.networking.interconnect import Interconnect
from sawtooth_validator.gossip.gossip import Gossip

from sawtooth_validator.server.events.broadcaster import EventBroadcaster

from sawtooth_validator.journal.receipt_store import TransactionReceiptStore

from sawtooth_validator.server import network_handlers
from sawtooth_validator.server import component_handlers

LOGGER = logging.getLogger(__name__)


class Validator(object):

    def __init__(self, bind_network, bind_component, endpoint,
                 peering, seeds_list, peer_list, data_dir, config_dir,
                 identity_signing_key, scheduler_type, permissions,
                 network_public_key=None, network_private_key=None,
                 roles=None,
                 metrics_registry=None
                 ):
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

        receipt_db_filename = os.path.join(
            data_dir, 'txn_receipts-{}.lmdb'.format(bind_network[-2:]))
        LOGGER.debug('txn receipt store file is %s', receipt_db_filename)
        receipt_db = LMDBNoLockDatabase(receipt_db_filename, 'c')

        state_delta_store = StateDeltaStore(state_delta_db)
        receipt_store = TransactionReceiptStore(receipt_db)

        context_manager = ContextManager(merkle_db, state_delta_store)
        self._context_manager = context_manager

        state_view_factory = StateViewFactory(merkle_db)

        block_db_filename = os.path.join(data_dir, 'block-{}.lmdb'.format(
                                         bind_network[-2:]))
        LOGGER.debug('block store file is %s', block_db_filename)

        block_db = LMDBNoLockDatabase(block_db_filename, 'c')
        block_store = BlockStore(block_db)

        batch_tracker = BatchTracker(block_store)

        # setup network
        self._dispatcher = Dispatcher(metrics_registry=metrics_registry)

        thread_pool = ThreadPoolExecutor(max_workers=10)
        sig_pool = ThreadPoolExecutor(max_workers=3)

        self._thread_pool = thread_pool
        self._sig_pool = sig_pool

        self._service = Interconnect(bind_component,
                                     self._dispatcher,
                                     secured=False,
                                     heartbeat=False,
                                     max_incoming_connections=20,
                                     monitor=True,
                                     max_future_callback_workers=10,
                                     metrics_registry=metrics_registry)

        executor = TransactionExecutor(
            service=self._service,
            context_manager=context_manager,
            settings_view_factory=SettingsViewFactory(
                StateViewFactory(merkle_db)),
            scheduler_type=scheduler_type,
            invalid_observers=[batch_tracker],
            metrics_registry=metrics_registry)

        self._executor = executor
        self._service.set_check_connections(executor.check_connections)

        state_delta_processor = StateDeltaProcessor(self._service,
                                                    state_delta_store,
                                                    block_store)
        event_broadcaster = EventBroadcaster(self._service,
                                             block_store,
                                             receipt_store)

        zmq_identity = hashlib.sha512(
            time.time().hex().encode()).hexdigest()[:23]

        network_thread_pool = ThreadPoolExecutor(max_workers=10)
        self._network_thread_pool = network_thread_pool

        self._network_dispatcher = Dispatcher(
            metrics_registry=metrics_registry)

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
            max_incoming_connections=100,
            max_future_callback_workers=10,
            authorize=True,
            public_key=signing.generate_public_key(identity_signing_key),
            priv_key=identity_signing_key,
            roles=roles,
            metrics_registry=metrics_registry)

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

        identity_view_factory = IdentityViewFactory(
            StateViewFactory(merkle_db))

        id_cache = IdentityCache(identity_view_factory,
                                 block_store.chain_head_state_root)

        permission_verifier = PermissionVerifier(
            permissions,
            block_store.chain_head_state_root,
            id_cache)

        identity_observer = IdentityObserver(
            to_update=id_cache.invalidate,
            forked=id_cache.forked)

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
            data_dir=data_dir,
            config_dir=config_dir,
            permission_verifier=permission_verifier,
            check_publish_block_frequency=0.1,
            block_cache_purge_frequency=30,
            block_cache_keep_time=300,
            batch_observers=[batch_tracker],
            chain_observers=[
                state_delta_processor,
                event_broadcaster,
                receipt_store,
                batch_tracker,
                identity_observer
            ],
            metrics_registry=metrics_registry
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

        network_handlers.add(
            self._network_dispatcher, self._network, self._gossip, completer,
            responder, network_thread_pool, sig_pool, permission_verifier)

        component_handlers.add(
            self._dispatcher, self._gossip, context_manager, executor,
            completer, self._journal.get_block_store(), batch_tracker,
            merkle_db, self._journal.get_current_root, receipt_store,
            state_delta_processor, state_delta_store, event_broadcaster,
            permission_verifier, thread_pool, sig_pool)

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
