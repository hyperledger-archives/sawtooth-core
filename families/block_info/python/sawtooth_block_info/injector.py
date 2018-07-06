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

from sawtooth_block_info.protobuf.block_info_pb2 import BlockInfoTxn
from sawtooth_block_info.protobuf.block_info_pb2 import BlockInfo

from sawtooth_block_info.common import FAMILY_NAME
from sawtooth_block_info.common import FAMILY_VERSION
from sawtooth_block_info.common import CONFIG_ADDRESS
from sawtooth_block_info.common import BLOCK_INFO_NAMESPACE


class BlockInfoInjector(BatchInjector):
    """Inject BlockInfo transactions at the beginning of blocks."""

    def __init__(self, block_cache, state_view_factory, signer):
        self._block_cache = block_cache
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

    def block_start(self, previous_block_id):
        """Returns an ordered list of batches to inject at the beginning of the
        block. Can also return None if no batches should be injected.

        Args:
            previous_block_id (str): The signature of the previous block.

        Returns:
            A list of batches to inject.
        """
        previous_block = self._block_cache[previous_block_id].get_block()
        previous_header = BlockHeader()
        previous_header.ParseFromString(previous_block.header)

        block_info = BlockInfo(
            block_num=previous_header.block_num,
            previous_block_id=previous_header.previous_block_id,
            signer_public_key=previous_header.signer_public_key,
            header_signature=previous_block.header_signature,
            timestamp=int(time.time()))

        return [self.create_batch(block_info)]

    def before_batch(self, previous_block_id, batch):
        pass

    def after_batch(self, previous_block_id, batch):
        pass

    def block_end(self, previous_block_id, batches):
        pass
