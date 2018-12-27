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

# pylint: disable=invalid-name

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_validator.database.native_lmdb import NativeLmdbDatabase
from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.genesis_pb2 import GenesisData
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.chain_id_manager import ChainIdManager
from sawtooth_validator.journal.genesis import GenesisController
from sawtooth_validator.journal.genesis import InvalidGenesisStateError
from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.state.state_view import StateViewFactory


class TestGenesisController(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None
        self._signer = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()
        context = create_context('secp256k1')
        private_key = context.new_random_private_key()
        crypto_factory = CryptoFactory(context)
        self._signer = crypto_factory.new_signer(private_key)

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    @staticmethod
    def make_block_store(data=None):
        return BlockStore(
            DictDatabase(
                data, indexes=BlockStore.create_index_configuration()))

    def test_requires_genesis(self):
        self._with_empty_batch_file()

        genesis_ctrl = GenesisController(
            Mock('context_manager'),
            Mock('txn_executor'),
            Mock('completer'),
            self.make_block_store(),  # Empty block store
            Mock('StateViewFactory'),
            self._signer,
            data_dir=self._temp_dir,
            config_dir=self._temp_dir,
            chain_id_manager=ChainIdManager(self._temp_dir),
            batch_sender=Mock('batch_sender'),
            receipt_store=MagicMock())

        self.assertEqual(True, genesis_ctrl.requires_genesis())

    def test_does_not_require_genesis_block_exists(self):
        block = self._create_block()
        block_store = self.make_block_store({
            block.header_signature: block
        })

        genesis_ctrl = GenesisController(
            Mock('context_manager'),
            Mock('txn_executor'),
            Mock('completer'),
            block_store,
            Mock('StateViewFactory'),
            self._signer,
            data_dir=self._temp_dir,
            config_dir=self._temp_dir,
            chain_id_manager=ChainIdManager(self._temp_dir),
            batch_sender=Mock('batch_sender'),
            receipt_store=MagicMock())

        self.assertEqual(False, genesis_ctrl.requires_genesis())

    def test_does_not_require_genesis_join_network(self):
        self._with_network_name('some_network_name')

        block_store = self.make_block_store()

        genesis_ctrl = GenesisController(
            Mock('context_manager'),
            Mock('txn_executor'),
            Mock('completer'),
            block_store,
            Mock('StateViewFactory'),
            self._signer,
            data_dir=self._temp_dir,
            config_dir=self._temp_dir,
            chain_id_manager=ChainIdManager(self._temp_dir),
            batch_sender=Mock('batch_sender'),
            receipt_store=MagicMock())

        self.assertEqual(False, genesis_ctrl.requires_genesis())

    def test_does_not_require_genesis_with_no_file_no_network(self):
        """
        In this case, when there is:
         - no genesis.batch file
         - no chain head
         - no network
        the the GenesisController should not require genesis.
        """
        block_store = self.make_block_store()

        genesis_ctrl = GenesisController(
            Mock(name='context_manager'),
            Mock(name='txn_executor'),
            Mock('completer'),
            block_store,
            Mock('StateViewFactory'),
            self._signer,
            data_dir=self._temp_dir,
            config_dir=self._temp_dir,
            chain_id_manager=ChainIdManager(self._temp_dir),
            batch_sender=Mock('batch_sender'),
            receipt_store=MagicMock())

        self.assertEqual(False, genesis_ctrl.requires_genesis())

    def test_requires_genesis_fails_if_block_exists(self):
        """
        In this case, when there is
         - a genesis_batch_file
         - a chain head id
        the validator should produce an assertion, as it already has a
        genesis block and should not attempt to produce another.
        """
        self._with_empty_batch_file()

        block = self._create_block()
        block_store = self.make_block_store({block.header_signature: block})

        genesis_ctrl = GenesisController(
            Mock('context_manager'),
            Mock('txn_executor'),
            Mock('completer'),
            block_store,
            Mock('StateViewFactory'),
            self._signer,
            data_dir=self._temp_dir,
            config_dir=self._temp_dir,
            chain_id_manager=ChainIdManager(self._temp_dir),
            batch_sender=Mock('batch_sender'),
            receipt_store=MagicMock())

        with self.assertRaises(InvalidGenesisStateError):
            genesis_ctrl.requires_genesis()

    def test_requires_genesis_fails_if_joins_network_with_file(self):
        """
        In this case, when there is
         - a genesis_batch_file
         - network id
        the validator should produce an assertion error, as it is joining
        a network, and not a genesis node.
        """
        self._with_empty_batch_file()
        self._with_network_name('some_block_chain_id')

        block_store = self.make_block_store()

        genesis_ctrl = GenesisController(
            Mock('context_manager'),
            Mock('txn_executor'),
            Mock('completer'),
            block_store,
            Mock('StateViewFactory'),
            self._signer,
            data_dir=self._temp_dir,
            config_dir=self._temp_dir,
            chain_id_manager=ChainIdManager(self._temp_dir),
            batch_sender=Mock('batch_sender'),
            receipt_store=MagicMock())

        with self.assertRaises(InvalidGenesisStateError):
            genesis_ctrl.requires_genesis()

    @patch('sawtooth_validator.execution.scheduler_serial'
           '.SerialScheduler.complete')
    def test_empty_batch_file_should_produce_block(
        self, mock_scheduler_complete
    ):
        """
        In this case, the genesis batch, even with an empty list of batches,
        should produce a genesis block.
        Also:
         - the genesis.batch file should be deleted
         - the block_chain_id file should be created and populated
        """
        genesis_file = self._with_empty_batch_file()
        block_store = self.make_block_store()

        state_database = NativeLmdbDatabase(
            os.path.join(self._temp_dir, 'test_genesis.lmdb'),
            indexes=MerkleDatabase.create_index_configuration(),
            _size=10 * 1024 * 1024)
        merkle_db = MerkleDatabase(state_database)

        ctx_mgr = Mock(name='ContextManager')
        ctx_mgr.get_squash_handler.return_value = Mock()
        ctx_mgr.get_first_root.return_value = merkle_db.get_merkle_root()

        txn_executor = Mock(name='txn_executor')
        completer = Mock('completer')
        completer.add_block = Mock('add_block')

        genesis_ctrl = GenesisController(
            ctx_mgr,
            txn_executor,
            completer,
            block_store,
            StateViewFactory(state_database),
            self._signer,
            data_dir=self._temp_dir,
            config_dir=self._temp_dir,
            chain_id_manager=ChainIdManager(self._temp_dir),
            batch_sender=Mock('batch_sender'),
            receipt_store=MagicMock())

        on_done_fn = Mock(return_value='')
        genesis_ctrl.start(on_done_fn)

        self.assertEqual(False, os.path.exists(genesis_file))

        self.assertEqual(True, block_store.chain_head is not None)
        self.assertEqual(1, on_done_fn.call_count)
        self.assertEqual(1, completer.add_block.call_count)
        self.assertEqual(block_store.chain_head.identifier,
                         self._read_block_chain_id())

    def _with_empty_batch_file(self):
        genesis_batch_file = os.path.join(self._temp_dir, 'genesis.batch')
        with open(genesis_batch_file, 'wb') as f:
            f.write(GenesisData().SerializeToString())

        return genesis_batch_file

    def _with_network_name(self, block_chain_id):
        block_chain_id_file = os.path.join(self._temp_dir, 'block-chain-id')
        with open(block_chain_id_file, 'w') as f:
            f.write(block_chain_id)

        return block_chain_id_file

    def _read_block_chain_id(self):
        block_chain_id_file = os.path.join(self._temp_dir, 'block-chain-id')
        with open(block_chain_id_file, 'r') as f:
            return f.read()

    def _create_block(self):
        return BlockWrapper.wrap(
            Block(
                header_signature='some_block_id',
                batches=[],
                header=BlockHeader(
                    block_num=0, previous_block_id=NULL_BLOCK_IDENTIFIER)
                .SerializeToString()))
