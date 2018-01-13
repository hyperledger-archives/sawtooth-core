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

import hashlib
import logging
import os
import signal
import time
import threading

from sawtooth_validator.concurrent.threadpool import \
    InstrumentedThreadPoolExecutor
from sawtooth_validator.execution.context_manager import ContextManager
from sawtooth_validator.database.indexed_database import IndexedDatabase
from sawtooth_validator.database.lmdb_nolock_database import LMDBNoLockDatabase
from sawtooth_validator.journal.publisher import BlockPublisher
from sawtooth_validator.journal.chain import ChainController
from sawtooth_validator.journal.genesis import GenesisController
from sawtooth_validator.journal.batch_sender import BroadcastBatchSender
from sawtooth_validator.journal.block_sender import BroadcastBlockSender
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.journal.completer import Completer
from sawtooth_validator.journal.responder import Responder
from sawtooth_validator.journal.batch_injector import \
    DefaultBatchInjectorFactory
from sawtooth_validator.networking.dispatch import Dispatcher
from sawtooth_validator.journal.chain_id_manager import ChainIdManager
from sawtooth_validator.execution.executor import TransactionExecutor
from sawtooth_validator.state.batch_tracker import BatchTracker
from sawtooth_validator.state.settings_view import SettingsViewFactory
from sawtooth_validator.state.settings_cache import SettingsObserver
from sawtooth_validator.state.settings_cache import SettingsCache
from sawtooth_validator.state.identity_view import IdentityViewFactory
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
    def __init__(self,
                 bind_network,
                 bind_component,
                 endpoint,
                 peering,
                 seeds_list,
                 peer_list,
                 data_dir,
                 config_dir,
                 identity_signer,
                 scheduler_type,
                 permissions,
                 minimum_peer_connectivity,
                 maximum_peer_connectivity,
                 network_public_key=None,
                 network_private_key=None,
                 roles=None,
                 metrics_registry=None):
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
            identity_signer (str): cryptographic signer the validator uses for
                signing
        """

        # -- Setup Global State Database and Factory -- #
        global_state_db_filename = os.path.join(
            data_dir, 'merkle-{}.lmdb'.format(bind_network[-2:]))
        LOGGER.debug(
            'global state database file is %s', global_state_db_filename)
        global_state_db = LMDBNoLockDatabase(global_state_db_filename, 'c')
        state_view_factory = StateViewFactory(global_state_db)

        # -- Setup Receipt Store -- #
        receipt_db_filename = os.path.join(
            data_dir, 'txn_receipts-{}.lmdb'.format(bind_network[-2:]))
        LOGGER.debug('txn receipt store file is %s', receipt_db_filename)
        receipt_db = LMDBNoLockDatabase(receipt_db_filename, 'c')
        receipt_store = TransactionReceiptStore(receipt_db)

        # -- Setup Block Store -- #
        block_db_filename = os.path.join(
            data_dir, 'block-{}.lmdb'.format(bind_network[-2:]))
        LOGGER.debug('block store file is %s', block_db_filename)
        block_db = IndexedDatabase(
            block_db_filename,
            BlockStore.serialize_block,
            BlockStore.deserialize_block,
            flag='c',
            indexes=BlockStore.create_index_configuration())
        block_store = BlockStore(block_db)
        block_cache = BlockCache(
            block_store, keep_time=300, purge_frequency=30)

        # -- Setup Thread Pools -- #
        component_thread_pool = InstrumentedThreadPoolExecutor(
            max_workers=10, name='Component')
        network_thread_pool = InstrumentedThreadPoolExecutor(
            max_workers=10, name='Network')
        sig_pool = InstrumentedThreadPoolExecutor(
            max_workers=3, name='Signature')

        # -- Setup Dispatchers -- #
        component_dispatcher = Dispatcher(metrics_registry=metrics_registry)
        network_dispatcher = Dispatcher(metrics_registry=metrics_registry)

        # -- Setup Services -- #
        component_service = Interconnect(
            bind_component,
            component_dispatcher,
            secured=False,
            heartbeat=False,
            max_incoming_connections=20,
            monitor=True,
            max_future_callback_workers=10,
            metrics_registry=metrics_registry)

        zmq_identity = hashlib.sha512(
            time.time().hex().encode()).hexdigest()[:23]

        secure = False
        if network_public_key is not None and network_private_key is not None:
            secure = True

        network_service = Interconnect(
            bind_network,
            dispatcher=network_dispatcher,
            zmq_identity=zmq_identity,
            secured=secure,
            server_public_key=network_public_key,
            server_private_key=network_private_key,
            heartbeat=True,
            public_endpoint=endpoint,
            connection_timeout=120,
            max_incoming_connections=100,
            max_future_callback_workers=10,
            authorize=True,
            signer=identity_signer,
            roles=roles,
            metrics_registry=metrics_registry)

        # -- Setup Transaction Execution Platform -- #
        context_manager = ContextManager(global_state_db)

        batch_tracker = BatchTracker(block_store)

        settings_cache = SettingsCache(
            SettingsViewFactory(state_view_factory),
        )

        executor = TransactionExecutor(
            service=component_service,
            context_manager=context_manager,
            settings_view_factory=SettingsViewFactory(state_view_factory),
            scheduler_type=scheduler_type,
            invalid_observers=[batch_tracker],
            metrics_registry=metrics_registry)

        component_service.set_check_connections(executor.check_connections)

        event_broadcaster = EventBroadcaster(
            component_service, block_store, receipt_store)

        # -- Setup P2P Networking -- #
        gossip = Gossip(
            network_service,
            settings_cache,
            block_store.chain_head_state_root,
            endpoint=endpoint,
            peering_mode=peering,
            initial_seed_endpoints=seeds_list,
            initial_peer_endpoints=peer_list,
            minimum_peer_connectivity=minimum_peer_connectivity,
            maximum_peer_connectivity=maximum_peer_connectivity,
            topology_check_frequency=1
        )

        completer = Completer(block_store, gossip)

        block_sender = BroadcastBlockSender(completer, gossip)
        batch_sender = BroadcastBatchSender(completer, gossip)
        chain_id_manager = ChainIdManager(data_dir)

        identity_view_factory = IdentityViewFactory(
            StateViewFactory(global_state_db))

        id_cache = IdentityCache(identity_view_factory)

        # -- Setup Permissioning -- #
        permission_verifier = PermissionVerifier(
            permissions,
            block_store.chain_head_state_root,
            id_cache)

        identity_observer = IdentityObserver(
            to_update=id_cache.invalidate,
            forked=id_cache.forked)

        settings_observer = SettingsObserver(
            to_update=settings_cache.invalidate,
            forked=settings_cache.forked)

        # -- Setup Journal -- #
        batch_injector_factory = DefaultBatchInjectorFactory(
            block_store=block_store,
            state_view_factory=state_view_factory,
            signer=identity_signer)

        block_publisher = BlockPublisher(
            transaction_executor=executor,
            block_cache=block_cache,
            state_view_factory=state_view_factory,
            settings_cache=settings_cache,
            block_sender=block_sender,
            batch_sender=batch_sender,
            squash_handler=context_manager.get_squash_handler(),
            chain_head=block_store.chain_head,
            identity_signer=identity_signer,
            data_dir=data_dir,
            config_dir=config_dir,
            permission_verifier=permission_verifier,
            check_publish_block_frequency=0.1,
            batch_observers=[batch_tracker],
            batch_injector_factory=batch_injector_factory,
            metrics_registry=metrics_registry)

        chain_controller = ChainController(
            block_sender=block_sender,
            block_cache=block_cache,
            state_view_factory=state_view_factory,
            transaction_executor=executor,
            chain_head_lock=block_publisher.chain_head_lock,
            on_chain_updated=block_publisher.on_chain_updated,
            squash_handler=context_manager.get_squash_handler(),
            chain_id_manager=chain_id_manager,
            identity_signer=identity_signer,
            data_dir=data_dir,
            config_dir=config_dir,
            permission_verifier=permission_verifier,
            chain_observers=[
                event_broadcaster,
                receipt_store,
                batch_tracker,
                identity_observer,
                settings_observer
            ],
            metrics_registry=metrics_registry)

        genesis_controller = GenesisController(
            context_manager=context_manager,
            transaction_executor=executor,
            completer=completer,
            block_store=block_store,
            state_view_factory=state_view_factory,
            identity_signer=identity_signer,
            data_dir=data_dir,
            config_dir=config_dir,
            chain_id_manager=chain_id_manager,
            batch_sender=batch_sender)

        responder = Responder(completer)

        completer.set_on_batch_received(block_publisher.queue_batch)
        completer.set_on_block_received(chain_controller.queue_block)
        completer.set_chain_has_block(chain_controller.has_block)

        # -- Register Message Handler -- #
        network_handlers.add(
            network_dispatcher, network_service, gossip, completer,
            responder, network_thread_pool, sig_pool,
            chain_controller.has_block, block_publisher.has_batch,
            permission_verifier, block_publisher)

        component_handlers.add(
            component_dispatcher, gossip, context_manager, executor, completer,
            block_store, batch_tracker, global_state_db,
            self.get_chain_head_state_root_hash, receipt_store,
            event_broadcaster, permission_verifier, component_thread_pool,
            sig_pool, block_publisher, metrics_registry)

        # -- Store Object References -- #
        self._component_dispatcher = component_dispatcher
        self._component_service = component_service
        self._component_thread_pool = component_thread_pool

        self._network_dispatcher = network_dispatcher
        self._network_service = network_service
        self._network_thread_pool = network_thread_pool

        self._sig_pool = sig_pool

        self._context_manager = context_manager
        self._executor = executor
        self._genesis_controller = genesis_controller
        self._gossip = gossip

        self._block_publisher = block_publisher
        self._chain_controller = chain_controller

    def start(self):
        self._component_dispatcher.start()
        self._component_service.start()
        if self._genesis_controller.requires_genesis():
            self._genesis_controller.start(self._start)
        else:
            self._start()

    def _start(self):
        self._network_dispatcher.start()
        self._network_service.start()

        self._gossip.start()
        self._block_publisher.start()
        self._chain_controller.start()

        signal_event = threading.Event()

        signal.signal(signal.SIGTERM,
                      lambda sig, fr: signal_event.set())
        # This is where the main thread will be during the bulk of the
        # validator's life.
        while not signal_event.is_set():
            signal_event.wait(timeout=20)

    def stop(self):
        self._gossip.stop()
        self._component_dispatcher.stop()
        self._network_dispatcher.stop()
        self._network_service.stop()

        self._component_service.stop()

        self._network_thread_pool.shutdown(wait=True)
        self._component_thread_pool.shutdown(wait=True)
        self._sig_pool.shutdown(wait=True)

        self._executor.stop()
        self._context_manager.stop()

        self._block_publisher.stop()
        self._chain_controller.stop()

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

    def get_chain_head_state_root_hash(self):
        return self._chain_controller.chain_head.state_root_hash
