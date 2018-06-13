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
# -----------------------------------------------------------------------------

import logging
import os

from sawtooth_poet.poet_consensus.poet_block_publisher \
    import PoetBlockPublisher
from sawtooth_poet.poet_consensus.poet_block_verifier import PoetBlockVerifier
from sawtooth_poet.poet_consensus.poet_fork_resolver import PoetForkResolver

from sawtooth_sdk.consensus.exceptions import UnknownBlock
from sawtooth_sdk.messaging.stream import Stream

import sawtooth_signing as signing
from sawtooth_signing import CryptoFactory
from sawtooth_signing.secp256k1 import Secp256k1PrivateKey

from sawtooth_sdk.protobuf.validator_pb2 import Message

from sawtooth_sdk.protobuf.batch_pb2 import Batch
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader
from sawtooth_sdk.protobuf.client_batch_submit_pb2 \
    import ClientBatchSubmitRequest
from sawtooth_sdk.protobuf.client_block_pb2 \
    import ClientBlockGetByTransactionIdRequest
from sawtooth_sdk.protobuf.client_block_pb2 import ClientBlockGetResponse
from sawtooth_sdk.protobuf.block_pb2 import BlockHeader
from sawtooth_sdk.protobuf.consensus_pb2 import ConsensusBlock


LOGGER = logging.getLogger(__name__)


class PoetOracle:
    '''Wrapper for various PoET structures.'''
    def __init__(self, service):
        # These should eventually be passed in.
        data_dir = '/var/lib/sawtooth/'
        config_dir = '/etc/sawtooth/'
        validator_id = 'this-should-be-the-validator-public-key'
        component_endpoint = 'tcp://validator-0:4004'

        stream = Stream(component_endpoint)

        block_cache = _BlockCacheProxy(service, stream)
        state_view_factory = _StateViewFactoryProxy(service)

        batch_publisher = _BatchPublisherProxy(stream)

        self._publisher = PoetBlockPublisher(
            block_cache=block_cache,
            state_view_factory=state_view_factory,
            batch_publisher=batch_publisher,
            data_dir=data_dir,
            config_dir=config_dir,
            validator_id=validator_id)

        self._verifier = PoetBlockVerifier(
            block_cache=block_cache,
            state_view_factory=state_view_factory,
            data_dir=data_dir,
            config_dir=config_dir,
            validator_id=validator_id)

        self._fork_resolver = PoetForkResolver(
            block_cache=block_cache,
            state_view_factory=state_view_factory,
            data_dir=data_dir,
            config_dir=config_dir,
            validator_id=validator_id)

    def initialize_block(self, block):
        return self._publisher.initialize_block(block)

    def check_publish_block(self, block):
        return self._publisher.check_publish_block(block)

    def finalize_block(self, block):
        return self._publisher.finalize_block(block)

    def verify_block(self, block):
        return self._verifier.verify_block(block)

    def switch_forks(self, cur_fork_head, new_fork_head):
        '''Return whether to switch from the current fork to the new one.'''
        return self._fork_resolver.compare_forks(cur_fork_head, new_fork_head)


class PoetBlock:
    def __init__(self, block):
        # Fields that come with consensus blocks
        self.block_id = block.block_id
        self.previous_id = block.previous_id
        self.signer_id = block.signer_id
        self.block_num = block.block_num
        self.payload = block.payload
        self.summary = block.summary

        # Fields required by PoET
        self.identifier = block.block_id
        self.previous_block_id = block.previous_id.hex()
        self.signer_public_key = block.signer_id.hex()
        self.header = _DummyHeader(block)

        # This is a trick: the real StateViewFactory needs a state
        # root hash, but the proxy needs a block id.
        self.state_root_hash = block.block_id


class _DummyHeader:
    def __init__(self, block):
        self.consensus = block.payload
        self.signer_public_key = block.signer_id.hex()


class _BlockCacheProxy:
    def __init__(self, service, stream):
        self.block_store = _BlockStoreProxy(service, stream)  # public
        self._service = service

    def __getitem__(self, block_id):
        block_id = bytes.fromhex(block_id)
        try:
            return PoetBlock(self._service.get_blocks([block_id])[block_id])
        except UnknownBlock:
            return None


class _BlockStoreProxy:
    def __init__(self, service, stream):
        self._service = service
        self._stream = stream

    @property
    def chain_head(self):
        return PoetBlock(self._service.get_chain_head())

    def get_block_by_transaction_id(self, transaction_id):
        future = self._stream.send(
            message_type=Message.CLIENT_BLOCK_GET_BY_TRANSACTION_ID_REQUEST,
            content=ClientBlockGetByTransactionIdRequest(
                transaction_id=transaction_id).SerializeToString())

        content = future.result().content

        response = ClientBlockGetResponse()
        response.ParseFromString(content)

        block = response.block

        header = BlockHeader()
        header.ParseFromString(block.header)

        consensus_block = ConsensusBlock(
            block_id=bytes.fromhex(block.header_signature),
            previous_id=bytes.fromhex(header.previous_block_id),
            signer_id=bytes.fromhex(header.signer_public_key),
            block_num=header.block_num,
            payload=header.consensus,
            summary=b'')

        poet_block = PoetBlock(consensus_block)

        return poet_block

    def get_block_iter(self, reverse=True):
        # Ignore the reverse flag, since we can only get blocks
        # starting from the head.

        # where does the chain head come from?
        # block or block_id?
        chain_head = self.chain_head

        yield chain_head

        curr = chain_head

        # assume chain_head is a block (else get the block)
        while curr.previous_id:
            try:
                previous_block = PoetBlock(
                    self._service.get_blocks(
                        [curr.previous_id]
                    )[curr.previous_id])
            except UnknownBlock:
                return

            yield previous_block

            curr = previous_block


class _StateViewFactoryProxy:
    def __init__(self, service):
        self._service = service

    def create_view(self, state_root_hash=None):
        '''The "state_root_hash" is really the block_id.'''
        block_id = state_root_hash

        return _StateViewProxy(self._service, block_id)


class _StateViewProxy:
    def __init__(self, service, block_id):
        self._service = service
        self._block_id = block_id

    def get(self, address):
        result = self._service.get_state(
            block_id=self._block_id,
            addresses=[address])

        return result[address]

    def leaves(self, prefix):
        result = self._service.get_state(
            block_id=self._block_id,
            addresses=[prefix])

        return [
            (address, data)
            for address, data in result.items()
        ]


class _BatchPublisherProxy:
    def __init__(self, stream):
        # These should eventually be passed in.
        key_dir, key_name = '/etc/sawtooth/keys', 'validator'

        self.identity_signer = _load_identity_signer(key_dir, key_name)
        self._stream = stream

    def send(self, transactions):
        txn_signatures = [txn.header_signature for txn in transactions]

        header = BatchHeader(
            signer_public_key=self.identity_signer.get_public_key().as_hex(),
            transaction_ids=txn_signatures
        ).SerializeToString()

        signature = self.identity_signer.sign(header)

        batch = Batch(
            header=header,
            transactions=transactions,
            header_signature=signature)

        self._stream.send(
            message_type=Message.CLIENT_BATCH_SUBMIT_REQUEST,
            content=ClientBatchSubmitRequest(
                batches=[batch]).SerializeToString())


def _load_identity_signer(key_dir, key_name):
    """Loads a private key from the key directory, based on a validator's
    identity.

    Args:
        key_dir (str): The path to the key directory.
        key_name (str): The name of the key to load.

    Returns:
        Signer: the cryptographic signer for the key
    """
    key_path = os.path.join(key_dir, '{}.priv'.format(key_name))

    if not os.path.exists(key_path):
        raise Exception(
            "No such signing key file: {}".format(key_path))
    if not os.access(key_path, os.R_OK):
        raise Exception(
            "Key file is not readable: {}".format(key_path))

    LOGGER.info('Loading signing key: %s', key_path)
    try:
        with open(key_path, 'r') as key_file:
            private_key_str = key_file.read().strip()
    except IOError as e:
        raise Exception(
            "Could not load key file: {}".format(str(e)))

    try:
        private_key = Secp256k1PrivateKey.from_hex(private_key_str)
    except signing.ParseError as e:
        raise Exception(
            "Invalid key in file {}: {}".format(key_path, str(e)))

    context = signing.create_context('secp256k1')
    crypto_factory = CryptoFactory(context)
    return crypto_factory.new_signer(private_key)
