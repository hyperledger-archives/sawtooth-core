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

import logging
import os
from pathlib import Path

from sawtooth_signing import pbct as signing
from sawtooth_validator.protobuf import genesis_pb2
from sawtooth_validator.protobuf import block_pb2
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import BlockState
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.journal import NULLIDENTIFIER
from sawtooth_validator.execution.scheduler_serial import SerialScheduler
from sawtooth_validator.exceptions import InvalidGenesisStateError


LOGGER = logging.getLogger(__name__)


class GenesisController(object):
    def __init__(self,
                 context_manager,
                 transaction_executor,
                 completer,
                 block_store,
                 data_dir):
        """
        Creates a GenesisController
        Params:
            context_manager - a ContextManager instance
            transaction_executor - a TransactionExecutor instance
            completer - a Completer instance
            block_store - the block store, with dict-like access
            data_dir - the directory for data files
        """
        self._context_manager = context_manager
        self._transaction_executor = transaction_executor
        self._completer = completer
        self._block_store = block_store
        self._data_dir = data_dir

    def requires_genesis(self):
        """
        Determines if the system should be put in genesis mode
        """

        genesis_file = os.path.join(self._data_dir, 'genesis.batch')
        has_genesis_batches = Path(genesis_file).is_file()
        LOGGER.debug('genesis_batch_file: %s',
                     genesis_file if has_genesis_batches else 'None')

        has_chain_head = "chain_head_id" in self._block_store
        LOGGER.debug(
            'chain_head: %s',
            self._block_store['chain_head_id'] if has_chain_head else 'None')

        block_chain_id = self._get_block_chain_id()
        is_genesis_node = block_chain_id is None
        LOGGER.debug('network_name: %s', block_chain_id)

        if has_genesis_batches and has_chain_head:
            raise InvalidGenesisStateError(
                'Cannot have a genesis_batch_file and an existing chain')

        if has_genesis_batches and not is_genesis_node:
            raise InvalidGenesisStateError(
                'Cannot have a genesis_batch_file and join an existing network'
            )

        ret = has_genesis_batches and not has_chain_head and is_genesis_node
        LOGGER.debug('Requires genesis: %s', ret)
        return ret

    def start(self, on_done):
        """
        Starts the genesis block creation process.  Will call the given
        `on_done` callback on successful completion.
        Params:
            on_done - a function called on completion
        """
        genesis_file = os.path.join(self._data_dir, 'genesis.batch')
        try:
            with open(genesis_file, 'rb') as batch_file:
                genesis_data = genesis_pb2.GenesisData()
                genesis_data.ParseFromString(batch_file.read())
            LOGGER.info('Producing genesis block from %s', genesis_file)
        except IOError:
            raise InvalidGenesisStateError(
                "Genesis File {} specified, but unreadable".format(
                    genesis_file))

        initial_state_root = self._context_manager.get_first_root()

        block = GenesisController._generate_genesis_block()
        genesis_batches = [batch for batch in genesis_data.batches]
        if len(genesis_batches) > 0:
            scheduler = SerialScheduler(
                self._context_manager.get_squash_handler(),
                initial_state_root)

            LOGGER.debug('Adding %s batches', len(genesis_data.batches))
            for batch in genesis_data.batches:
                scheduler.add_batch(batch)

            self._transaction_executor.execute(scheduler,
                                               require_txn_processors=True)

            scheduler.finalize()
            scheduler.complete(block=True)

        state_hash = initial_state_root
        for batch in genesis_batches:
            result = scheduler.get_batch_execution_result(
                batch.header_signature)
            if result is None or not result.is_valid:
                raise InvalidGenesisStateError(
                    'Unable to create genesis block, due to batch {}'
                    .format(batch.header_signature))

            state_hash = result.state_hash
        LOGGER.debug('Produced state hash %s for genesis block.',
                     state_hash)

        block.add_batches(genesis_batches)
        block.set_state_hash(state_hash)

        GenesisController._sign_block(block)

        LOGGER.info('genesis block created: %s', block.header_signature)
        self._completer.add_block(block.get_block())
        self._block_store['chain_head_id'] = block.header_signature

        block_state = BlockState(block_wrapper=block, weight=0,
                                 status=BlockStatus.Valid)
        self._block_store[block.header_signature] = block_state

        self._save_block_chain_id(block.header_signature)

        LOGGER.debug('deleting genesis data')
        os.remove(genesis_file)

        if on_done is not None:
            on_done()

    def _get_block_chain_id(self):
        block_chain_id_file = os.path.join(self._data_dir, 'block-chain-id')
        if not Path(block_chain_id_file).is_file():
            return None

        try:
            with open(block_chain_id_file, 'r') as f:
                block_chain_id = f.read()
                return block_chain_id if block_chain_id else None
        except IOError:
            raise InvalidGenesisStateError(
                'The block-chain-id file exists, but is unreadable')

    def _save_block_chain_id(self, block_chain_id):
        LOGGER.debug('writing block chain id')
        block_chain_id_file = os.path.join(self._data_dir, 'block-chain-id')
        try:
            with open(block_chain_id_file, 'w') as f:
                f.write(block_chain_id)
        except IOError:
            raise InvalidGenesisStateError(
                'The block-chain-id file exists, but is unwriteable')

    @staticmethod
    def _generate_genesis_block():
        """
        Returns a blocker wrapper with the basics of the block header in place
        """
        genesis_header = block_pb2.BlockHeader(
            previous_block_id=NULLIDENTIFIER, block_num=0)

        block = BlockWrapper(genesis_header)

        return block

    @staticmethod
    def _sign_block(block):
        """ The block should be complete and the final
        signature from the publishing validator (this validator) needs to
        be added.
        """
        temp_key = signing.generate_privkey()
        public_key = signing.encode_pubkey(
            signing.generate_pubkey(temp_key), "hex")

        block.block_header.signer_pubkey = public_key
        block_header = block.block_header
        header_bytes = block_header.SerializeToString()
        signature = signing.sign(
            header_bytes,
            temp_key)
        block.set_signature(signature)
        return block
