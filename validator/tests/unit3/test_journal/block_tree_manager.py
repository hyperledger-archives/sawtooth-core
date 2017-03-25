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

import hashlib
import pprint
import random
import string

import sawtooth_signing as signing

from sawtooth_validator.database.dict_database import DictDatabase

from sawtooth_validator.journal.block_builder import BlockBuilder
from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.journal import BlockPublisher

from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.setting_pb2 import Setting
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader

from test_journal.mock import MockBatchSender
from test_journal.mock import MockBlockSender
from test_journal.mock import MockStateViewFactory
from test_journal.mock import MockTransactionExecutor
from test_journal import mock_consensus

pp = pprint.PrettyPrinter(indent=4)


def _generate_id(length=16):
    return ''.join(
        random.SystemRandom().choice(string.ascii_uppercase + string.digits)
        for _ in range(length))


def _setting_address(key):
    return '000000' + hashlib.sha256(key.encode()).hexdigest()


def _setting_entry(key, value):
    return Setting(
        entries=[Setting.Entry(key=key, value=value)]
    ).SerializeToString()


class BlockTreeManager(object):
    def __str__(self):
        return str(self.block_cache)

    def __repr__(self):
        return repr(self.block_cache)

    def __init__(self):
        self.block_sender = MockBlockSender()
        self.batch_sender = MockBatchSender()
        self.block_store = BlockStore(DictDatabase())
        self.block_cache = BlockCache(self.block_store)
        self.state_db = {}

        # add the mock reference to the consensus
        self.state_db[_setting_address('sawtooth.consensus.algorithm')] = \
            _setting_entry('sawtooth.consensus.algorithm',
                           'test_journal.mock_consensus')

        self.state_view_factory = MockStateViewFactory(self.state_db)
        self.signing_key = signing.generate_privkey()
        self.public_key = signing.generate_pubkey(self.signing_key)

        self.identity_signing_key = signing.generate_privkey()
        self.genesis_block = self._generate_genesis_block()
        self.set_chain_head(self.genesis_block)

        self.block_publisher = BlockPublisher(
            transaction_executor=MockTransactionExecutor(),
            block_cache=self.block_cache,
            state_view_factory=self.state_view_factory,
            block_sender=self.block_sender,
            batch_sender=self.block_sender,
            squash_handler=None,
            chain_head=self.genesis_block,
            identity_signing_key=self.identity_signing_key,
            data_dir=None)

    @property
    def chain_head(self):
        return self.block_store.chain_head

    def set_chain_head(self, block):
        self.block_store.update_chain([block], [])

    def generate_block(self, previous_block=None,
                       add_to_store=False,
                       add_to_cache=False,
                       batch_count=0,
                       status=BlockStatus.Unknown,
                       invalid_consensus=False,
                       invalid_batch=False,
                       invalid_signature=False,
                       weight=0):

        previous = self._get_block(previous_block)
        if previous is None:
            previous = self.chain_head

        self.block_publisher.on_chain_updated(previous)

        while self.block_sender.new_block is None:
            self.block_publisher.on_batch_received(self._generate_batch(''))
            self.block_publisher.on_check_publish_block(True)

        block_from_sender = self.block_sender.new_block
        self.block_sender.new_block = None

        block_wrapper = BlockWrapper(block_from_sender)

        if invalid_signature:
            block_wrapper.block.header_signature = "BAD"

        if invalid_consensus:
            block_wrapper.header.consensus = b'BAD'

        if invalid_batch:
            block_wrapper.block.batches.extend(
                [self._generate_batch('BAD')])

        block_wrapper.weight = weight
        block_wrapper.status = status

        if add_to_cache:
            self.block_cache[block_wrapper.identifier] = block_wrapper

        if add_to_store:
            self.block_store[block_wrapper.identifier] = block_wrapper

        return block_wrapper

    def generate_chain(self, root_block, blocks, params=None):
        """
        Generate a new chain based on the root block and place it in the
        block cache.
        """
        if params is None:
            params = {}

        if root_block is None:
            previous = self._generate_genesis_block()
            self.block_store[previous.identifier] = previous
        else:
            previous = self._get_block(root_block)

        try:
            block_defs = [self._block_def(**params) for _ in range(blocks)]
        except TypeError:
            block_defs = blocks

        out = []
        for block_def in block_defs:
            new_block = self.generate_block(
                previous_block=previous, **block_def)
            out.append(new_block)
            previous = new_block
        return out

    def _generate_block(self, payload, previous_block_id, block_num):
        header = BlockHeader(
            previous_block_id=previous_block_id,
            signer_pubkey=self.public_key,
            block_num=block_num)

        block_builder = BlockBuilder(header)
        block_builder.add_batches([self._generate_batch(payload)])

        header_bytes = block_builder.block_header.SerializeToString()
        signature = signing.sign(header_bytes, self.identity_signing_key)
        block_builder.set_signature(signature)

        return BlockWrapper(block_builder.build_block())

    def _generate_genesis_block(self):
        return self._generate_block(
            payload='Genesis',
            previous_block_id=NULL_BLOCK_IDENTIFIER,
            block_num=0)

    def _block_def(self,
                   add_to_store=False,
                   add_to_cache=False,
                   batch_count=0,
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
        elif isinstance(block, Block) or\
                isinstance(block, BlockWrapper):
            return block.header_signature
        elif isinstance(block, basestring):
            return block
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

    def _generate_batch(self, payload):
        payload_encoded = payload.encode('utf-8')
        hasher = hashlib.sha512()
        hasher.update(payload_encoded)

        header = TransactionHeader()
        header.batcher_pubkey = self.public_key
        # txn.dependencies not yet
        header.family_name = 'test'
        header.family_version = '1'
        header.nonce = _generate_id(16)
        header.payload_encoding = "text"
        header.payload_sha512 = hasher.hexdigest().encode()
        header.signer_pubkey = self.public_key

        txn = Transaction()
        header_bytes = header.SerializeToString()
        txn.header = header_bytes
        txn.header_signature = signing.sign(header_bytes, self.signing_key)
        txn.payload = payload_encoded

        batch_header = BatchHeader()
        batch_header.signer_pubkey = self.public_key
        batch_header.transaction_ids.extend([txn.header_signature])

        batch = Batch()
        header_bytes = batch_header.SerializeToString()
        batch.header = header_bytes
        batch.header_signature = signing.sign(header_bytes, self.signing_key)
        batch.transactions.extend([txn])
        return batch
