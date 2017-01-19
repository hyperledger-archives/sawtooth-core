# Copyright 2016 Intel Corporation
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
import socket

from sawtooth_validator.context_manager import ContextManager
from sawtooth_validator.database.lmdb_nolock_database import LMDBNoLockDatabase
from sawtooth_validator.journal.consensus.dev_mode import dev_mode_consensus
from sawtooth_validator.journal.journal import Journal
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.server import state
from sawtooth_validator.server.dispatch import Dispatcher
from sawtooth_validator.server.executor import TransactionExecutor
from sawtooth_validator.server.loader import SystemLoadHandler
from sawtooth_validator.server.network import FauxNetwork
from sawtooth_validator.server.network import Network
from sawtooth_validator.server.processor import ProcessorRegisterHandler
from sawtooth_validator.server.interconnect import Interconnect
from sawtooth_validator.server.client import ClientStateCurrentRequestHandler
from sawtooth_validator.server.client import ClientStateGetRequestHandler
from sawtooth_validator.server.client import ClientStateListRequestHandler


LOGGER = logging.getLogger(__name__)


class DefaultHandler(object):
    def handle(self, message, responder):
        print("invalid message {}".format(message.message_type))


class Validator(object):
    def __init__(self, network_endpoint, component_endpoint, peer_list):
        db_filename = os.path.join(os.path.expanduser('~'), 'merkle.lmdb')
        LOGGER.debug('database file is %s', db_filename)

        lmdb = LMDBNoLockDatabase(db_filename, 'n')
        context_manager = ContextManager(lmdb)

        block_db_filename = os.path.join(os.path.expanduser('~'), 'block.lmdb')
        LOGGER.debug('block store file is %s', block_db_filename)
        # block_store = LMDBNoLockDatabase(block_db_filename, 'n')
        # this is not currently being used but will be something like this
        # in the future, when Journal takes a block_store that isn't a dict
        self._service = Interconnect(component_endpoint)

        # setup network
        dispatcher = Dispatcher()
        faux_network = FauxNetwork(dispatcher=dispatcher)

        identity = "{}-{}".format(socket.gethostname(),
                                  os.getpid()).encode('ascii')
        self._network = Network(identity,
                                network_endpoint,
                                peer_list,
                                dispatcher=dispatcher)

        # Create and configure journal
        executor = TransactionExecutor(self._service, context_manager)
        self._journal = Journal(
            consensus=dev_mode_consensus,
            block_store={},
            # -- need to serialize blocks to dicts
            send_message=faux_network.send_message,
            transaction_executor=executor,
            squash_handler=context_manager.get_squash_handler(),
            first_state_root=context_manager.get_first_root())

        dispatcher.on_batch_received = \
            self._journal.on_batch_received
        dispatcher.on_block_received = \
            self._journal.on_block_received
        dispatcher.on_block_request = \
            self._journal.on_block_request

        self._service.add_handler(
            validator_pb2.Message.DEFAULT,
            DefaultHandler())
        self._service.add_handler(
            validator_pb2.Message.TP_STATE_GET_REQUEST,
            state.GetHandler(context_manager))
        self._service.add_handler(
            validator_pb2.Message.TP_STATE_SET_REQUEST,
            state.SetHandler(context_manager))
        self._service.add_handler(
            validator_pb2.Message.TP_REGISTER_REQUEST,
            ProcessorRegisterHandler(self._service))
        self._service.add_handler(
            validator_pb2.Message.CLIENT_BATCH_SUBMIT_REQUEST,
            SystemLoadHandler(faux_network))
        self._service.add_handler(
            validator_pb2.Message.CLIENT_STATE_CURRENT_REQUEST,
            ClientStateCurrentRequestHandler(self._journal.get_current_root))
        self._service.add_handler(
            validator_pb2.Message.CLIENT_STATE_GET_REQUEST,
            ClientStateGetRequestHandler(lmdb))
        self._service.add_handler(
            validator_pb2.Message.CLIENT_STATE_LIST_REQUEST,
            ClientStateListRequestHandler(lmdb))

    def start(self):
        self._service.start()
        self._journal.start()

    def stop(self):
        self._service.stop()
        self._journal.stop()
