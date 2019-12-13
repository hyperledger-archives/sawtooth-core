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

# pylint: disable=no-else-return
# pylint: disable=no-value-for-parameter
# pylint: disable=abstract-class-instantiated

import logging
import hashlib
import os
import random
import string
import tempfile

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory

from sawtooth_validator.database.native_lmdb import NativeLmdbDatabase

from sawtooth_validator.journal.block_builder import BlockBuilder
from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.journal.block_manager import BlockManager
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.publisher import BlockPublisher

from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.setting_pb2 import Setting
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.state.state_view import NativeStateViewFactory

from test_journal import mock_consensus

from test_journal.mock import MockBatchSender
from test_journal.mock import MockBlockSender
from test_journal.mock import MockTransactionExecutor
from test_journal.mock import MockPermissionVerifier


LOGGER = logging.getLogger(__name__)


def dumps_batch(batch):
    out = '\tbatch: {}\n'.format(batch.header_signature[:8])
    for txn in batch.transactions:
        out += '\t\ttxn: {} {}\n'.format(
            txn.header_signature[:8], txn.payload)
    return out


def dumps_block(block):
    out = 'block: {}\n'.format(block)
    for batch in block.batches:
        out += dumps_batch(batch)
    return out


def _generate_id(length=16):
    return ''.join(
        random.SystemRandom().choice(string.ascii_uppercase + string.digits)
        for _ in range(length))


def _setting_entry(key, value):
    return Setting(
        entries=[Setting.Entry(key=key, value=value)]
    ).SerializeToString()


class BlockTreeManager:
    def __str__(self):
        return str(self.block_cache)

    def __repr__(self):
        return repr(self.block_cache)

    def __init__(self, with_genesis=True):
        self.block_sender = MockBlockSender()
        self.batch_sender = MockBatchSender()
        self.dir = tempfile.mkdtemp()
        self.block_db = NativeLmdbDatabase(
            os.path.join(self.dir, 'block.lmdb'),
            BlockStore.create_index_configuration())
        self.block_store = BlockStore(self.block_db)
        self.block_cache = BlockCache(self.block_store)
        self.state_db = NativeLmdbDatabase(
            os.path.join(self.dir, "merkle.lmdb"),
            MerkleDatabase.create_index_configuration())

        self.state_view_factory = NativeStateViewFactory(self.state_db)

        self.block_manager = BlockManager()
        self.block_manager.add_commit_store(self.block_store)

        context = create_context('secp256k1')
        private_key = context.new_random_private_key()
        crypto_factory = CryptoFactory(context)
        self.signer = crypto_factory.new_signer(private_key)

        identity_private_key = context.new_random_private_key()
        self.identity_signer = crypto_factory.new_signer(identity_private_key)
        chain_head = None
        if with_genesis:
            self.genesis_block = self.generate_genesis_block()
            chain_head = self.genesis_block
            self.block_manager.put([chain_head.block])
            self.block_manager.persist(
                chain_head.block.header_signature,
                "commit_store")

        self.block_publisher = BlockPublisher(
            block_store=self.block_store,
            block_manager=self.block_manager,
            transaction_executor=MockTransactionExecutor(),
            state_view_factory=self.state_view_factory,
            block_sender=self.block_sender,
            batch_sender=self.block_sender,
            identity_signer=self.identity_signer,
            data_dir=None,
            config_dir=None,
            permission_verifier=MockPermissionVerifier(),
            batch_observers=[])

    @property
    def chain_head(self):
        return self.block_store.chain_head

    def generate_block(self, previous_block=None,
                       add_to_store=False,
                       add_to_cache=False,
                       batch_count=1,
                       batches=None,
                       status=BlockStatus.Unknown,
                       invalid_consensus=False,
                       invalid_batch=False,
                       invalid_signature=False,
                       weight=0):

        previous = self._get_block(previous_block)
        if previous is None:
            previous = self.chain_head

        header = BlockHeader(
            previous_block_id=previous.identifier,
            signer_public_key=self.identity_signer.get_public_key().as_hex(),
            block_num=previous.block_num + 1)

        block_builder = BlockBuilder(header)
        if batches:
            block_builder.add_batches(batches)

        if batch_count != 0:
            block_builder.add_batches(
                [self._generate_batch()
                    for _ in range(batch_count)])

        if invalid_batch:
            block_builder.add_batches(
                [self._generate_batch_from_payload('BAD')])

        block_builder.set_state_hash('0' * 70)

        consensus = mock_consensus.BlockPublisher()
        consensus.finalize_block(block_builder.block_header, weight=weight)

        if invalid_consensus:
            block_builder.block_header.consensus = b'BAD'

        header_bytes = block_builder.block_header.SerializeToString()
        if invalid_signature:
            block_builder.set_signature('BAD')
        else:
            signature = self.identity_signer.sign(header_bytes)
            block_builder.set_signature(signature)

        block_wrapper = BlockWrapper(block_builder.build_block())

        if batches:
            block_wrapper.block.batches.extend(batches)

        if batch_count:
            block_wrapper.block.batches.extend(
                [self.generate_batch() for _ in range(batch_count)])

        if invalid_signature:
            block_wrapper.block.header_signature = "BAD"

        if invalid_consensus:
            block_wrapper.header.consensus = b'BAD'

        block_wrapper.status = status

        self.block_manager.put([block_wrapper.block])
        if add_to_cache:
            self.block_cache[block_wrapper.identifier] = block_wrapper

        if add_to_store:
            self.block_store.put_blocks([block_wrapper.block])

        LOGGER.debug("Generated %s", dumps_block(block_wrapper))
        return block_wrapper

    def generate_chain(self, root_block, blocks, params=None,
                       exclude_head=True):
        """
        Generate a new chain based on the root block and place it in the
        block cache.
        """
        if params is None:
            params = {}

        if root_block is None:
            previous = self.generate_genesis_block()
            self.block_store.put_blocks([previous.block])
        else:
            previous = self._get_block(root_block)

        try:
            block_defs = [self._block_def(**params) for _ in range(blocks)]
            if exclude_head:
                block_defs[-1] = self._block_def()
        except TypeError:
            block_defs = blocks

        out = []
        for block_def in block_defs:
            new_block = self.generate_block(
                previous_block=previous, **block_def)
            out.append(new_block)
            previous = new_block
        return out

    def create_block(self, payload='payload', batch_count=1,
                     previous_block_id=NULL_BLOCK_IDENTIFIER, block_num=0):
        header = BlockHeader(
            previous_block_id=previous_block_id,
            signer_public_key=self.identity_signer.get_public_key().as_hex(),
            block_num=block_num)

        block_builder = BlockBuilder(header)
        block_builder.add_batches(
            [self._generate_batch_from_payload(payload)
                for _ in range(batch_count)])
        block_builder.set_state_hash('0' * 70)

        header_bytes = block_builder.block_header.SerializeToString()
        signature = self.identity_signer.sign(header_bytes)
        block_builder.set_signature(signature)

        block_wrapper = BlockWrapper(block_builder.build_block())
        LOGGER.debug("Generated %s", dumps_block(block_wrapper))
        return block_wrapper

    def generate_genesis_block(self):
        return self.create_block(
            payload='Genesis',
            previous_block_id=NULL_BLOCK_IDENTIFIER,
            block_num=0)

    def _block_def(self,
                   add_to_store=False,
                   add_to_cache=False,
                   batch_count=1,
                   status=BlockStatus.Unknown,
                   invalid_consensus=False,
                   invalid_batch=False,
                   invalid_signature=False,
                   weight=0):
        return {
            "add_to_cache": add_to_cache,
            "add_to_store": add_to_store,
            "batch_count": batch_count,
            "status": status,
            "invalid_consensus": invalid_consensus,
            "invalid_batch": invalid_batch,
            "invalid_signature": invalid_signature,
            "weight": weight
        }

    def _get_block_id(self, block):
        if block is None:
            return None
        elif isinstance(block, (Block, BlockWrapper)):
            return block.header_signature
        else:
            return str(block)

    def _get_block(self, block):
        if block is None:
            return None
        elif isinstance(block, Block):
            return BlockWrapper(block)
        elif isinstance(block, BlockWrapper):
            return block
        elif isinstance(block, str):
            return self.block_cache[block]
        else:  # WTF try something crazy
            return self.block_cache[str(block)]

    def generate_batch(self, txn_count=2, missing_deps=False,
                       txns=None):

        batch = self._generate_batch(txn_count, missing_deps, txns)

        LOGGER.debug("Generated Batch:\n%s", dumps_batch(batch))

        return batch

    def _generate_batch(self, txn_count=2, missing_deps=False,
                        txns=None):
        if txns is None:
            txns = []

        if txn_count != 0:
            txns += [
                self.generate_transaction('txn_' + str(i))
                for i in range(txn_count)
            ]

        if missing_deps:
            target_txn = txns[-1]
            txn_missing_deps = self.generate_transaction(
                payload='this one has a missing dependency',
                deps=[target_txn.header_signature])
            # replace the targeted txn with the missing deps txn
            txns[-1] = txn_missing_deps

        batch_header = BatchHeader(
            signer_public_key=self.signer.get_public_key().as_hex(),
            transaction_ids=[txn.header_signature for txn in txns]
        ).SerializeToString()

        batch = Batch(
            header=batch_header,
            header_signature=self.signer.sign(batch_header),
            transactions=txns)

        return batch

    def generate_transaction(self, payload='txn', deps=None):
        payload_encoded = payload.encode('utf-8')
        hasher = hashlib.sha512()
        hasher.update(payload_encoded)

        txn_header = TransactionHeader(
            dependencies=([] if deps is None else deps),
            batcher_public_key=self.signer.get_public_key().as_hex(),
            family_name='test',
            family_version='1',
            nonce=_generate_id(16),
            payload_sha512=hasher.hexdigest().encode(),
            signer_public_key=self.signer.get_public_key().as_hex()
        ).SerializeToString()

        txn = Transaction(
            header=txn_header,
            header_signature=self.signer.sign(txn_header),
            payload=payload_encoded)

        return txn

    def _generate_batch_from_payload(self, payload):
        txn = self.generate_transaction(payload)

        batch_header = BatchHeader(
            signer_public_key=self.signer.get_public_key().as_hex(),
            transaction_ids=[txn.header_signature]
        ).SerializeToString()

        batch = Batch(
            header=batch_header,
            header_signature=self.signer.sign(batch_header),
            transactions=[txn])
        return batch
