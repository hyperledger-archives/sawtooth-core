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

import hashlib
import time

from sawtooth_validator.journal.batch_injector import BatchInjector
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.block_pb2 import BlockHeader

from sawtooth_validator.protobuf.block_info_pb2 import BlockInfoTxn
from sawtooth_validator.protobuf.block_info_pb2 import BlockInfo

FAMILY_NAME = 'block_info'
FAMILY_VERSION = '1.0'
NAMESPACE = '00b10c'
BLOCK_INFO_NAMESPACE = NAMESPACE + '00'
CONFIG_ADDRESS = NAMESPACE + '01' + '0' * 62
DEFAULT_SYNC_TOLERANCE = 60 * 5
DEFAULT_TARGET_COUNT = 256


class BlockInfoInjector(BatchInjector):
    """Inject BlockInfo transactions at the beginning of blocks."""

    def __init__(self, state_view_factory, signer):
        self._state_view_factory = state_view_factory
        self._signer = signer

    def create_batch(self, block_info):
        payload = BlockInfoTxn(block=block_info).SerializeToString()
        public_key = self._signer.get_public_key().as_hex()
        header = TransactionHeader(
            signer_public_key=public_key,
            family_name=FAMILY_NAME,
            family_version=FAMILY_VERSION,
            inputs=[CONFIG_ADDRESS, BLOCK_INFO_NAMESPACE],
            outputs=[CONFIG_ADDRESS, BLOCK_INFO_NAMESPACE],
            dependencies=[],
            payload_sha512=hashlib.sha512(payload).hexdigest(),
            batcher_public_key=public_key,
        ).SerializeToString()

        transaction_signature = self._signer.sign(header)

        transaction = Transaction(
            header=header,
            payload=payload,
            header_signature=transaction_signature,
        )

        header = BatchHeader(
            signer_public_key=public_key,
            transaction_ids=[transaction_signature],
        ).SerializeToString()

        batch_signature = self._signer.sign(header)

        return Batch(
            header=header,
            transactions=[transaction],
            header_signature=batch_signature,
        )

    def block_start(self, previous_block):
        """Returns an ordered list of batches to inject at the beginning of the
        block. Can also return None if no batches should be injected.

        Args:
            previous_block (Block): The previous block.

        Returns:
            A list of batches to inject.
        """

        previous_header_bytes = previous_block.header
        previous_header = BlockHeader()
        previous_header.ParseFromString(previous_header_bytes)

        block_info = BlockInfo(
            block_num=previous_header.block_num,
            previous_block_id=previous_header.previous_block_id,
            signer_public_key=previous_header.signer_public_key,
            header_signature=previous_block.header_signature,
            timestamp=int(time.time()))

        return [self.create_batch(block_info)]

    def before_batch(self, previous_block, batch):
        pass

    def after_batch(self, previous_block, batch):
        pass

    def block_end(self, previous_block, batches):
        pass


def create_block_address(block_num):
    return BLOCK_INFO_NAMESPACE + hex(block_num)[2:].zfill(62)
