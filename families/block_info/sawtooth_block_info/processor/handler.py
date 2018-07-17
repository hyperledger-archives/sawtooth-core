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
import time

from sawtooth_sdk.processor.handler import TransactionHandler
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError

from sawtooth_block_info.protobuf.block_info_pb2 import BlockInfoTxn
from sawtooth_block_info.protobuf.block_info_pb2 import BlockInfo
from sawtooth_block_info.protobuf.block_info_pb2 import BlockInfoConfig

from sawtooth_block_info.common import FAMILY_NAME
from sawtooth_block_info.common import FAMILY_VERSION
from sawtooth_block_info.common import NAMESPACE
from sawtooth_block_info.common import CONFIG_ADDRESS
from sawtooth_block_info.common import DEFAULT_SYNC_TOLERANCE
from sawtooth_block_info.common import DEFAULT_TARGET_COUNT
from sawtooth_block_info.common import create_block_address


LOGGER = logging.getLogger(__name__)


def validate_hex(string, length):
    try:
        int(string, 16)
        return len(string) == length
    except ValueError:
        return False


def validate_timestamp(timestamp, tolerance):
    now = time.time()
    if (timestamp - now) > tolerance:
        raise InvalidTransaction(
            "Timestamp must be less than local time."
            " Expected {0} in ({1}-{2}, {1}+{2})".format(
                timestamp, now, tolerance))


class BlockInfoTransactionHandler(TransactionHandler):
    @property
    def family_name(self):
        return FAMILY_NAME

    @property
    def family_versions(self):
        return [FAMILY_VERSION]

    @property
    def namespaces(self):
        return [NAMESPACE]

    def apply(self, transaction, context):
        # Unpack payload
        txn = BlockInfoTxn()
        txn.ParseFromString(transaction.payload)
        next_block = txn.block

        # Validate block info fields
        if next_block.block_num < 0:
            raise InvalidTransaction(
                "Invalid block num '{}'".format(next_block.block_num))

        if not (validate_hex(next_block.previous_block_id, 128)
                or next_block.previous_block_id == "0000000000000000"):
            raise InvalidTransaction("Invalid previous block id '{}'".format(
                next_block.previous_block_id))

        if not validate_hex(next_block.signer_public_key, 66):
            raise InvalidTransaction("Invalid signer public_key '{}'".format(
                next_block.signer_public_key))

        if not validate_hex(next_block.header_signature, 128):
            raise InvalidTransaction("Invalid header signature '{}'".format(
                next_block.header_signature))

        if next_block.timestamp <= 0:
            raise InvalidTransaction(
                "Invalid timestamp '{}'".format(next_block.timestamp))

        # Get config and previous block (according to the block info in the
        # transaction) from state
        entries = context.get_state([CONFIG_ADDRESS])

        deletes = []
        sets = []
        config = BlockInfoConfig()

        # If there is no config in state, we don't know anything about what's
        # in state, so we have to treat this as the first entry
        if not entries:
            # If sync tolerance or target count were not specified in the txn,
            # use default values.
            config.sync_tolerance = \
                DEFAULT_SYNC_TOLERANCE if txn.sync_tolerance == 0 \
                else txn.sync_tolerance

            config.target_count = \
                DEFAULT_TARGET_COUNT if txn.target_count == 0 \
                else txn.target_count

            config.latest_block = next_block.block_num
            config.oldest_block = next_block.block_num

            validate_timestamp(next_block.timestamp, config.sync_tolerance)

            sets.append((CONFIG_ADDRESS, config.SerializeToString()))
            sets.append((
                create_block_address(next_block.block_num),
                next_block.SerializeToString()))

        else:
            config.ParseFromString(entries[0].data)

            # If the config was changed in this transaction
            if txn.sync_tolerance != 0:
                config.sync_tolerance = txn.sync_tolerance
            if txn.target_count != 0:
                config.target_count = txn.target_count

            if next_block.block_num - 1 != config.latest_block:
                raise InvalidTransaction(
                    "Block number must be one more than previous block's."
                    " Got {} expected {}".format(
                        next_block.block_num, config.latest_block + 1))

            validate_timestamp(next_block.timestamp, config.sync_tolerance)

            entries = context.get_state(
                [create_block_address(config.latest_block)])
            if not entries:
                raise InternalError(
                    "Config and state out of sync. Latest block not found in"
                    " state.")

            prev_block = BlockInfo()
            prev_block.ParseFromString(entries[0].data)
            if prev_block.block_num != config.latest_block:
                raise InternalError(
                    "Block info stored at latest block has incorrect block"
                    " num.")

            if next_block.previous_block_id != prev_block.header_signature:
                raise InvalidTransaction(
                    "Previous block id must match header signature of previous"
                    " block. Go {} expected {}".format(
                        next_block.previous_block_id,
                        prev_block.header_signature))

            if next_block.timestamp < prev_block.timestamp:
                raise InvalidTransaction(
                    "Timestamp must be greater than previous block's."
                    " Got {}, expected >{}".format(
                        next_block.timestamp, prev_block.timestamp))

            config.latest_block = next_block.block_num
            while (config.latest_block - config.oldest_block) \
                    > config.target_count:
                deletes.append(create_block_address(config.oldest_block))
                config.oldest_block = config.oldest_block + 1

            sets.append((CONFIG_ADDRESS, config.SerializeToString()))
            sets.append((
                create_block_address(next_block.block_num),
                next_block.SerializeToString()))

        # If this is not true, something else has modified global state
        if deletes:
            if set(deletes) != set(context.delete_state(deletes)):
                raise InternalError(
                    "Blocks should have been in state but weren't: {}".format(
                        deletes))

        if sets:
            addresses = set(k for k, _ in sets)
            addresses_set = set(context.set_state(
                {k: v for k, v in sets}))
            if addresses != addresses_set:
                raise InternalError("Failed to set addresses.")
