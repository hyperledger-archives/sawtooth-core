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

from sawtooth_signing import secp256k1_signer as signing
from sawtooth_validator.protobuf import genesis_pb2
from sawtooth_validator.protobuf import block_pb2
from sawtooth_validator.journal.block_builder import BlockBuilder
from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.consensus.consensus_factory import \
    ConsensusFactory
from sawtooth_validator.execution.scheduler_serial import SerialScheduler
from sawtooth_validator.exceptions import InvalidGenesisStateError
from sawtooth_validator.exceptions import UnknownConsensusModuleError


LOGGER = logging.getLogger(__name__)


class GenesisController(object):
    def __init__(self,
                 context_manager,
                 transaction_executor,
                 completer,
                 block_store,
                 state_view_factory,
                 identity_key,
                 data_dir,
                 chain_id_manager):
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
            identity_key (str): A private key used for signing blocks, in hex.
            data_dir (str): The directory for data files.
        """
        self._context_manager = context_manager
        self._transaction_executor = transaction_executor
        self._completer = completer
        self._block_store = block_store
        self._state_view_factory = state_view_factory
        self._identity_priv_key = identity_key
        self._data_dir = data_dir
        self._chain_id_manager = chain_id_manager

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
                     genesis_file if has_genesis_batches else 'None')

        chain_head = self._block_store.chain_head
        has_chain_head = chain_head is not None
        LOGGER.debug('chain_head: %s %s', chain_head, has_chain_head)

        block_chain_id = self._chain_id_manager.get_block_chain_id()
        is_genesis_node = block_chain_id is None
        LOGGER.debug('block_chain_id: %s', block_chain_id)

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

        block_builder = GenesisController._generate_genesis_block()
        block_builder.add_batches(genesis_batches)
        block_builder.set_state_hash(state_hash)

        block_publisher = self._get_block_publisher(state_hash)
        block_publisher.initialize_block(block_builder)

        self._sign_block(block_builder)

        block = block_builder.build_block()
        block_publisher.finalize_block(block)

        blkw = BlockWrapper(block=block, status=BlockStatus.Valid)

        LOGGER.info('Genesis block created: %s', blkw)

        self._completer.add_block(block)
        self._block_store.update_chain([blkw])

        self._chain_id_manager.save_block_chain_id(block.header_signature)

        LOGGER.debug('Deleting genesis data.')
        os.remove(genesis_file)

        if on_done is not None:
            on_done()

    def _get_block_publisher(self, state_hash):
        """Returns the block publisher based on the consensus module set by the
        "sawtooth_config" transaction family.

        Args:
            state_hash (str): The current state root hash for reading settings.

        Raises:
            InvalidGenesisStateError: if any errors occur getting the
                BlockPublisher.
        """
        state_view = self._state_view_factory.create_view(state_hash)
        try:
            consensus = ConsensusFactory.get_configured_consensus_module(
                state_view)
            return consensus.BlockPublisher(
                BlockCache(self._block_store),
                state_view=state_view)
        except UnknownConsensusModuleError as e:
            raise InvalidGenesisStateError(e)

    @staticmethod
    def _generate_genesis_block():
        """
        Returns a blocker wrapper with the basics of the block header in place
        """
        genesis_header = block_pb2.BlockHeader(
            previous_block_id=NULL_BLOCK_IDENTIFIER, block_num=0)

        return BlockBuilder(genesis_header)

    def _sign_block(self, block):
        """ The block should be complete and the final
        signature from the publishing validator (this validator) needs to
        be added.
        """
        public_key = signing.encode_pubkey(
            signing.generate_pubkey(self._identity_priv_key), "hex")

        block.block_header.signer_pubkey = public_key
        block_header = block.block_header
        header_bytes = block_header.SerializeToString()
        signature = signing.sign(
            header_bytes,
            self._identity_priv_key)
        block.set_signature(signature)
        return block
