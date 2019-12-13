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

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_validator.database.native_lmdb import NativeLmdbDatabase
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.genesis_pb2 import GenesisData
from sawtooth_validator.journal.block_manager import BlockManager
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.chain_id_manager import ChainIdManager
from sawtooth_validator.journal.genesis import GenesisController
from sawtooth_validator.journal.genesis import InvalidGenesisStateError


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
    def make_block_store(blocks=None):
        block_dir = tempfile.mkdtemp()
        block_db = NativeLmdbDatabase(
            os.path.join(block_dir, 'block.lmdb'),
            BlockStore.create_index_configuration())
        block_store = BlockStore(block_db)
        if blocks is not None:
            block_store.put_blocks(blocks)
        return block_store

    def test_requires_genesis(self):
        self._with_empty_batch_file()

        block_store = self.make_block_store()
        block_manager = BlockManager()
        block_manager.add_commit_store(block_store)

        genesis_ctrl = GenesisController(
            context_manager=Mock('context_manager'),
            transaction_executor=Mock('txn_executor'),
            block_store=block_store,  # Empty block store
            state_view_factory=Mock('StateViewFactory'),
            identity_signer=self._signer,
            block_manager=block_manager,
            data_dir=self._temp_dir,
            config_dir=self._temp_dir,
            chain_id_manager=ChainIdManager(self._temp_dir),
            batch_sender=Mock('batch_sender'),
            receipt_store=MagicMock())

        self.assertEqual(True, genesis_ctrl.requires_genesis())

    def test_does_not_require_genesis_block_exists(self):
        block = self._create_block()
        block_store = self.make_block_store([block.block])
        block_manager = BlockManager()
        block_manager.add_commit_store(block_store)

        genesis_ctrl = GenesisController(
            context_manager=Mock('context_manager'),
            transaction_executor=Mock('txn_executor'),
            block_store=block_store,
            state_view_factory=Mock('StateViewFactory'),
            identity_signer=self._signer,
            block_manager=block_manager,
            data_dir=self._temp_dir,
            config_dir=self._temp_dir,
            chain_id_manager=ChainIdManager(self._temp_dir),
            batch_sender=Mock('batch_sender'),
            receipt_store=MagicMock())

        self.assertEqual(False, genesis_ctrl.requires_genesis())

    def test_does_not_require_genesis_join_network(self):
        self._with_network_name('some_network_name')

        block_store = self.make_block_store()
        block_manager = BlockManager()
        block_manager.add_commit_store(block_store)

        genesis_ctrl = GenesisController(
            context_manager=Mock('context_manager'),
            transaction_executor=Mock('txn_executor'),
            block_store=block_store,
            state_view_factory=Mock('StateViewFactory'),
            identity_signer=self._signer,
            block_manager=block_manager,
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
        block_manager = BlockManager()
        block_manager.add_commit_store(block_store)

        genesis_ctrl = GenesisController(
            context_manager=Mock('context_manager'),
            transaction_executor=Mock('txn_executor'),
            block_store=block_store,
            state_view_factory=Mock('StateViewFactory'),
            identity_signer=self._signer,
            block_manager=block_manager,
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
        block_store = self.make_block_store([block.block])
        block_manager = BlockManager()
        block_manager.add_commit_store(block_store)

        genesis_ctrl = GenesisController(
            context_manager=Mock('context_manager'),
            transaction_executor=Mock('txn_executor'),
            block_store=block_store,
            state_view_factory=Mock('StateViewFactory'),
            identity_signer=self._signer,
            block_manager=block_manager,
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
        block_manager = BlockManager()
        block_manager.add_commit_store(block_store)

        genesis_ctrl = GenesisController(
            context_manager=Mock('context_manager'),
            transaction_executor=Mock('txn_executor'),
            block_store=block_store,
            state_view_factory=Mock('StateViewFactory'),
            identity_signer=self._signer,
            block_manager=block_manager,
            data_dir=self._temp_dir,
            config_dir=self._temp_dir,
            chain_id_manager=ChainIdManager(self._temp_dir),
            batch_sender=Mock('batch_sender'),
            receipt_store=MagicMock())

        with self.assertRaises(InvalidGenesisStateError):
            genesis_ctrl.requires_genesis()

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
