# Copyright 2018 Intel Corporation
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
import hashlib
import unittest
import os
import shutil
import tempfile
import cbor

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory

from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.database.native_lmdb import NativeLmdbDatabase
from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.journal.block_store import BlockStore
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER

from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_validator.server.state_verifier import verify_state


LOGGER = logging.getLogger(__name__)


def get_signer():
    context = create_context('secp256k1')
    private_key = context.new_random_private_key()
    crypto_factory = CryptoFactory(context)
    return crypto_factory.new_signer(private_key)


def populate_blockstore(blockstore, signer, state_roots):
    txns = [
        create_intkey_transaction("set", str(i), 0, [], signer)
        for i, _ in enumerate(state_roots)
    ]
    batches = [
        create_batch([txn], signer)
        for txn in txns
    ]
    blocks = []

    for i, batch in enumerate(batches):
        if not blocks:
            previous_block_id = NULL_BLOCK_IDENTIFIER
        else:
            previous_block_id = blocks[-1].header_signature
        block = create_block(
            batch=batch,
            block_num=i,
            previous_block_id=previous_block_id,
            state_root_hash=state_roots[i],
            signer=signer)
        blocks.append(block)

    for block in blocks:
        blockstore[block.header_signature] = block


def make_intkey_address(name):
    return INTKEY_ADDRESS_PREFIX + hashlib.sha512(
        name.encode('utf-8')).hexdigest()[-64:]


INTKEY_ADDRESS_PREFIX = hashlib.sha512(
    'intkey'.encode('utf-8')).hexdigest()[0:6]


class IntKeyPayload:
    def __init__(self, verb, name, value):
        self._verb = verb
        self._name = name
        self._value = value

        self._cbor = None
        self._sha512 = None

    def to_hash(self):
        return {
            'Verb': self._verb,
            'Name': self._name,
            'Value': self._value
        }

    def to_cbor(self):
        if self._cbor is None:
            self._cbor = cbor.dumps(self.to_hash(), sort_keys=True)
        return self._cbor

    def sha512(self):
        if self._sha512 is None:
            self._sha512 = hashlib.sha512(self.to_cbor()).hexdigest()
        return self._sha512


def create_intkey_transaction(verb, name, value, deps, signer):
    payload = IntKeyPayload(
        verb=verb, name=name, value=value)

    # The prefix should eventually be looked up from the
    # validator's namespace registry.
    addr = make_intkey_address(name)

    header = TransactionHeader(
        signer_public_key=signer.get_public_key().as_hex(),
        family_name='intkey',
        family_version='1.0',
        inputs=[addr],
        outputs=[addr],
        dependencies=deps,
        payload_sha512=payload.sha512(),
        batcher_public_key=signer.get_public_key().as_hex())

    header_bytes = header.SerializeToString()

    signature = signer.sign(header_bytes)

    transaction = Transaction(
        header=header_bytes,
        payload=payload.to_cbor(),
        header_signature=signature)

    return transaction


def create_batch(transactions, signer):
    transaction_signatures = [t.header_signature for t in transactions]

    header = BatchHeader(
        signer_public_key=signer.get_public_key().as_hex(),
        transaction_ids=transaction_signatures)

    header_bytes = header.SerializeToString()

    signature = signer.sign(header_bytes)

    batch = Batch(
        header=header_bytes,
        transactions=transactions,
        header_signature=signature)

    return batch


def create_block(batch, block_num, previous_block_id, state_root_hash, signer):
    header = BlockHeader(
        block_num=block_num,
        previous_block_id=previous_block_id,
        state_root_hash=state_root_hash,
        signer_public_key=signer.get_public_key().as_hex(),
    ).SerializeToString()

    block = Block(
        header=header,
        batches=[batch],
        header_signature=signer.sign(header))

    block_wrapper = BlockWrapper(block)
    return block_wrapper


class TestStateVerifier(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    def test_state_verifier(self):
        blockstore = BlockStore(DictDatabase(
            indexes=BlockStore.create_index_configuration()))
        global_state_db = NativeLmdbDatabase(
            os.path.join(self._temp_dir, 'test_state_verifier.lmdb'),
            indexes=MerkleDatabase.create_index_configuration())

        precalculated_state_roots = [
            "e35490eac6f77453675c3399da7efe451e791272bbc8cf1b032c75030fb455c3",
            "3a369eb951171895c00ba2ffd04bfa1ef98d6ee651f96a65ae3280cf8d67d5e7",
            "797e70e29915c9129f950b2084ed0e3c09246bd1e6c232571456f51ca85df340",
        ]

        signer = get_signer()
        populate_blockstore(blockstore, signer, precalculated_state_roots)

        verify_state(
            global_state_db,
            blockstore,
            "tcp://eth0:4004",
            "serial")

        # There is a bug in the shutdown code for some component this depends
        # on, which causes it to occassionally hang during shutdown. Just kill
        # the process for now.
        # pylint: disable=protected-access
        os._exit(0)
