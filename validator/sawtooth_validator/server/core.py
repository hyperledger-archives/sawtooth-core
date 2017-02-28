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
from concurrent.futures import ProcessPoolExecutor
import hashlib
import logging
import os
import time

from sawtooth_signing import secp256k1_signer as signing

from sawtooth_validator.execution.context_manager import ContextManager
from sawtooth_validator.database.lmdb_nolock_database import LMDBNoLockDatabase
from sawtooth_validator.journal.genesis import GenesisController
from sawtooth_validator.journal.journal import Journal
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.execution import tp_state_handlers
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.completer import CompleterGossipHandler
from sawtooth_validator.journal.completer import \
    CompleterBatchListBroadcastHandler
from sawtooth_validator.journal.completer import Completer
from sawtooth_validator.journal.responder import Responder
from sawtooth_validator.journal.responder import BlockResponderHandler
from sawtooth_validator.journal.responder import BatchByBatchIdResponderHandler
from sawtooth_validator.journal.responder import \
    BatchByTransactionIdResponderHandler
from sawtooth_validator.networking.dispatch import Dispatcher
from sawtooth_validator.journal.block_sender import BroadcastBlockSender
from sawtooth_validator.journal.chain_id_manager import ChainIdManager
from sawtooth_validator.execution.executor import TransactionExecutor
from sawtooth_validator.execution import processor_handlers
from sawtooth_validator.state import client_handlers
from sawtooth_validator.state.state_view import StateViewFactory
from sawtooth_validator.gossip import signature_verifier
from sawtooth_validator.networking.interconnect import Interconnect
from sawtooth_validator.gossip.gossip import Gossip
from sawtooth_validator.gossip.gossip_handlers import GossipBroadcastHandler
from sawtooth_validator.gossip.gossip_handlers import GossipMessageHandler
from sawtooth_validator.gossip.gossip_handlers import PeerRegisterHandler
from sawtooth_validator.gossip.gossip_handlers import PeerUnregisterHandler
from sawtooth_validator.gossip.gossip_handlers import PingHandler

LOGGER = logging.getLogger(__name__)


DEFAULT_KEY_NAME = 'validator'
"""Default key name for a validator's block signing key."""


class Validator(object):
    def __init__(self, network_endpoint, component_endpoint, peer_list,
                 data_dir, key_dir):
        """Constructs a validator instance.

        Args:
            network_endpoint (str): the network endpoint
            component_endpoint (str): the component endpoint
            peer_list (list of str): a list of peer addresses
            data_dir (str): path to the data directory
            key_dir (str): path to the key directory
        """
        db_filename = os.path.join(data_dir,
                                   'merkle-{}.lmdb'.format(
                                       network_endpoint[-2:]))
        LOGGER.debug('database file is %s', db_filename)

        merkle_db = LMDBNoLockDatabase(db_filename, 'n')
        context_manager = ContextManager(merkle_db)
        state_view_factory = StateViewFactory(merkle_db)

        block_db_filename = os.path.join(data_dir, 'block-{}.lmdb'.format(
                                         network_endpoint[-2:]))
        LOGGER.debug('block store file is %s', block_db_filename)

        block_db = LMDBNoLockDatabase(block_db_filename, 'n')
        block_store = BlockStore(block_db)

        # setup network
        self._dispatcher = Dispatcher()

        thread_pool = ThreadPoolExecutor(max_workers=10)
        process_pool = ProcessPoolExecutor(max_workers=3)

        self._service = Interconnect(component_endpoint,
                                     self._dispatcher,
                                     secured=False)
        executor = TransactionExecutor(self._service, context_manager)

        identity = hashlib.sha512(
            time.time().hex().encode()).hexdigest()[:23]

        identity_signing_key = Validator.load_identity_signing_key(
            key_dir,
            DEFAULT_KEY_NAME)

        network_thread_pool = ThreadPoolExecutor(max_workers=10)

        self._network_dispatcher = Dispatcher()

        # Server public and private keys are hardcoded here due to
        # the decision to avoid having separate identities for each
        # validator's server socket. This is appropriate for a public
        # network. For a permissioned network with requirements for
        # server endpoint authentication at the network level, this can
        # be augmented with a local lookup service for side-band provided
        # endpoint, public_key pairs and a local configuration option
        # for 'server' side private keys.
        self._network = Interconnect(
            network_endpoint,
            dispatcher=self._network_dispatcher,
            identity=identity,
            peer_connections=peer_list,
            secured=True,
            server_public_key=b'wFMwoOt>yFqI/ek.G[tfMMILHWw#vXB[Sv}>l>i)',
            server_private_key=b'r&oJ5aQDj4+V]p2:Lz70Eu0x#m%IwzBdP(}&hWM*')

        self._gossip = Gossip(self._network)

        completer = Completer(block_store, self._gossip)

        block_sender = BroadcastBlockSender(completer, self._gossip)
        chain_id_manager = ChainIdManager(data_dir)
        # Create and configure journal
        self._journal = Journal(
            block_store=block_store,
            state_view_factory=StateViewFactory(merkle_db),
            block_sender=block_sender,
            transaction_executor=executor,
            squash_handler=context_manager.get_squash_handler(),
            identity_signing_key=identity_signing_key,
            chain_id_manager=chain_id_manager
        )

        self._genesis_controller = GenesisController(
            context_manager=context_manager,
            transaction_executor=executor,
            completer=completer,
            block_store=block_store,
            state_view_factory=state_view_factory,
            identity_key=identity_signing_key,
            data_dir=data_dir,
            chain_id_manager=chain_id_manager
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
            thread_pool
        )

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_PING,
            PingHandler(),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_REGISTER,
            PeerRegisterHandler(),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_UNREGISTER,
            PeerUnregisterHandler(),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_MESSAGE,
            GossipMessageHandler(),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_MESSAGE,
            signature_verifier.GossipMessageSignatureVerifier(),
            process_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_MESSAGE,
            GossipBroadcastHandler(
                gossip=self._gossip),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_MESSAGE,
            CompleterGossipHandler(
                completer),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BLOCK_REQUEST,
            BlockResponderHandler(responder, self._gossip),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BATCH_BY_BATCH_ID_REQUEST,
            BatchByBatchIdResponderHandler(responder, self._gossip),
            network_thread_pool)

        self._network_dispatcher.add_handler(
            validator_pb2.Message.GOSSIP_BATCH_BY_TRANSACTION_ID_REQUEST,
            BatchByTransactionIdResponderHandler(responder, self._gossip),
            network_thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
            signature_verifier.BatchListSignatureVerifier(),
            process_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
            CompleterBatchListBroadcastHandler(
                completer, self._gossip),
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
            validator_pb2.Message.CLIENT_BLOCK_GET_REQUEST,
            client_handlers.BlockGetRequest(self._journal.get_block_store()),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_BLOCK_LIST_REQUEST,
            client_handlers.BlockListRequest(self._journal.get_block_store()),
            thread_pool)

        self._dispatcher.add_handler(
            validator_pb2.Message.CLIENT_STATE_CURRENT_REQUEST,
            client_handlers.StateCurrentRequest(
                self._journal.get_current_root), thread_pool)

    def start(self):
        self._dispatcher.start()
        self._service.start()
        if self._genesis_controller.requires_genesis():
            self._genesis_controller.start(self._start)
        else:
            self._start()

    def _start(self):
        self._network_dispatcher.start()
        self._network.start(daemon=True)
        self._gossip.start()
        self._journal.start()

    def stop(self):
        self._service.stop()
        self._network.stop()
        self._journal.stop()

    @staticmethod
    def load_identity_signing_key(key_dir, key_name):
        """Loads a private key from the key director, based on a validator's
        identity.

        Args:
            key_dir (str): The path to the key directory.
            key_name (str): The name of the key to load.

        Returns:
            str: the private signing key, in hex.
        """
        key_path = os.path.join(key_dir, '{}.wif'.format(key_name))

        if os.path.exists(key_path):
            LOGGER.debug('Found signing key %s', key_path)
            with open(key_path, 'r') as key_file:
                wif_key = key_file.read().strip()
                return signing.encode_privkey(
                    signing.decode_privkey(wif_key), 'hex')
        else:
            LOGGER.info('No signing key found. Generating %s', key_path)
            priv_key = signing.generate_privkey()
            with open(key_path, 'w') as key_file:
                key_file.write(signing.encode_privkey(priv_key))

            return signing.encode_privkey(priv_key, 'hex')
