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

from sawtooth_validator.exceptions import InvalidGenesisStateError
from sawtooth_validator.exceptions import InvalidGenesisConsensusError
from sawtooth_validator.exceptions import UnknownConsensusModuleError

from sawtooth_validator.execution.scheduler_serial import SerialScheduler

from sawtooth_validator.journal.block_builder import BlockBuilder
from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.consensus.consensus_factory import \
    ConsensusFactory
from sawtooth_validator.protobuf import genesis_pb2
from sawtooth_validator.protobuf import block_pb2
from sawtooth_validator.protobuf import transaction_receipt_pb2


LOGGER = logging.getLogger(__name__)


class GenesisController:
    def __init__(self,
                 context_manager,
                 transaction_executor,
                 completer,
                 block_store,
                 state_view_factory,
                 identity_signer,
                 data_dir,
                 config_dir,
                 chain_id_manager,
                 batch_sender,
                 receipt_store):
        """Creates a GenesisController.

        Args:
            context_manager (:obj:`ContextManager`): A `ContextManager`
                instance.
            transaction_executor (:obj:`TransactionExecutor`): A
                TransactionExecutor instance.
            completer (:obj:`Completer`): A Completer instance.
            block_store (:obj:): The block store, with dict-like access.
            state_view_factory (:obj:`StateViewFactory`): The state view
                factory for creating state views during processing.
            identity_signer (:obj:`Signer`): A cryptographic signer used for
                signing blocks.
            data_dir (str): The directory for data files.
            config_dir (str): The directory for config files.
            chain_id_manager (ChainIdManager): utility class to manage the
            chain id file.
            batch_sender: interface to broadcast batches to the network.
            receipt_store: (TransactionReceiptStore): store for transaction
                state deltas and events
        """
        self._context_manager = context_manager
        self._transaction_executor = transaction_executor
        self._completer = completer
        self._block_store = block_store
        self._state_view_factory = state_view_factory
        self._identity_signer = identity_signer
        self._data_dir = data_dir
        self._config_dir = config_dir
        self._chain_id_manager = chain_id_manager
        self._batch_sender = batch_sender
        self._txn_receipt_store = receipt_store

    def requires_genesis(self):
        """
        Determines if the system should be put in genesis mode

        Returns:
            bool: return whether or not a genesis block is required to be
                generated.

        Raises:
            InvalidGenesisStateError: raises this error if there is invalid
                combination of the following: genesis.batch, existing chain
                head, and block chain id.
        """

        genesis_file = os.path.join(self._data_dir, 'genesis.batch')
        has_genesis_batches = Path(genesis_file).is_file()
        LOGGER.debug('genesis_batch_file: %s',
                     genesis_file if has_genesis_batches else 'not found')

        chain_head = self._block_store.chain_head
        has_chain_head = chain_head is not None
        if has_chain_head:
            LOGGER.debug('chain_head: %s', chain_head)

        block_chain_id = self._chain_id_manager.get_block_chain_id()
        is_genesis_node = block_chain_id is None
        LOGGER.debug(
            'block_chain_id: %s',
            block_chain_id if not is_genesis_node else 'not yet specified')

        if has_genesis_batches and has_chain_head:
            raise InvalidGenesisStateError(
                'Cannot have a genesis_batch_file and an existing chain')

        if has_genesis_batches and not is_genesis_node:
            raise InvalidGenesisStateError(
                'Cannot have a genesis_batch_file and join an existing network'
            )

        if not has_genesis_batches and not has_chain_head:
            LOGGER.info('No chain head and not the genesis node: '
                        'starting in peering mode')

        return has_genesis_batches and not has_chain_head and is_genesis_node

    def start(self, on_done):
        """
        Starts the genesis block creation process.  Will call the given
        `on_done` callback on successful completion.

        Args:
            on_done (function): a function called on completion

        Raises:
            InvalidGenesisStateError: raises this error if a genesis block is
                unable to be produced, or the resulting block-chain-id saved.
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

        genesis_batches = [batch for batch in genesis_data.batches]
        if genesis_batches:
            scheduler = SerialScheduler(
                self._context_manager.get_squash_handler(),
                initial_state_root,
                always_persist=True)

            LOGGER.debug('Adding %s batches', len(genesis_data.batches))
            for batch in genesis_data.batches:
                scheduler.add_batch(batch)

            self._transaction_executor.execute(scheduler)

            scheduler.finalize()
            scheduler.complete(block=True)

        txn_receipts = []
        state_hash = initial_state_root
        for batch in genesis_batches:
            result = scheduler.get_batch_execution_result(
                batch.header_signature)
            if result is None or not result.is_valid:
                raise InvalidGenesisStateError(
                    'Unable to create genesis block, due to batch {}'
                    .format(batch.header_signature))
            if result.state_hash is not None:
                state_hash = result.state_hash

            txn_results = scheduler.get_transaction_execution_results(
                batch.header_signature)
            txn_receipts += self._make_receipts(txn_results)

        LOGGER.debug('Produced state hash %s for genesis block.', state_hash)

        block_builder = self._generate_genesis_block()
        block_builder.add_batches(genesis_batches)
        block_builder.set_state_hash(state_hash)

        block_publisher = self._get_block_publisher(initial_state_root)
        if not block_publisher.initialize_block(block_builder.block_header):
            LOGGER.error('Consensus refused to initialize consensus block.')
            raise InvalidGenesisConsensusError(
                'Consensus refused to initialize genesis block.')

        if not block_publisher.finalize_block(block_builder.block_header):
            LOGGER.error('Consensus refused to finalize genesis block.')
            raise InvalidGenesisConsensusError(
                'Consensus refused to finalize genesis block.')

        self._sign_block(block_builder)

        block = block_builder.build_block()

        blkw = BlockWrapper(block=block, status=BlockStatus.Valid)

        LOGGER.info('Genesis block created: %s', blkw)

        self._completer.add_block(block)
        self._block_store.update_chain([blkw])

        self._txn_receipt_store.chain_update(block, txn_receipts)
        self._chain_id_manager.save_block_chain_id(block.header_signature)

        LOGGER.debug('Deleting genesis data.')
        os.remove(genesis_file)

        if on_done is not None:
            on_done()

    def _get_block_publisher(self, state_hash):
        """Returns the block publisher based on the consensus module set by the
        "sawtooth_settings" transaction family.

        Args:
            state_hash (str): The current state root hash for reading settings.

        Raises:
            InvalidGenesisStateError: if any errors occur getting the
                BlockPublisher.
        """
        state_view = self._state_view_factory.create_view(state_hash)
        try:
            class BatchPublisher:
                def send(self, transactions):
                    # Consensus implementations are expected to have handling
                    # in place for genesis operation. This should includes
                    # adding any authorization and registrations required
                    # for the genesis node to the Genesis Batch list and
                    # detecting validation of the Genesis Block and handle it
                    # correctly. Batch publication is not allowed during
                    # genesis operation since there is no network to validate
                    # the batch yet.
                    raise InvalidGenesisConsensusError(
                        'Consensus cannot send transactions during genesis.')

            consensus = ConsensusFactory.get_configured_consensus_module(
                NULL_BLOCK_IDENTIFIER,
                state_view)
            return consensus.BlockPublisher(
                BlockCache(self._block_store),
                state_view_factory=self._state_view_factory,
                batch_publisher=BatchPublisher(),
                data_dir=self._data_dir,
                config_dir=self._config_dir,
                validator_id=self._identity_signer.get_public_key().as_hex())
        except UnknownConsensusModuleError as e:
            raise InvalidGenesisStateError(e)

    def _generate_genesis_block(self):
        """
        Returns a blocker wrapper with the basics of the block header in place
        """
        genesis_header = block_pb2.BlockHeader(
            block_num=0,
            previous_block_id=NULL_BLOCK_IDENTIFIER,
            signer_public_key=self._identity_signer.get_public_key().as_hex())

        return BlockBuilder(genesis_header)

    def _sign_block(self, block):
        """ The block should be complete and the final
        signature from the publishing validator (this validator) needs to
        be added.
        """
        block_header = block.block_header
        header_bytes = block_header.SerializeToString()
        signature = self._identity_signer.sign(header_bytes)
        block.set_signature(signature)
        return block

    def _make_receipts(self, results):
        receipts = []
        for result in results:
            receipt = transaction_receipt_pb2.TransactionReceipt()
            receipt.data.extend([data for data in result.data])
            receipt.state_changes.extend(result.state_changes)
            receipt.events.extend(result.events)
            receipt.transaction_id = result.signature
            receipts.append(receipt)
        return receipts
