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

import time

from sawtooth_processor_test.transaction_processor_test_case \
    import TransactionProcessorTestCase
from sawtooth_processor_test.message_factory import MessageFactory

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


def create_block_info(block_num,
                      signer_public_key="2" * 66,
                      header_signature="1" * 128,
                      timestamp=None,
                      previous_block_id="0" * 128):
    if timestamp is None:
        timestamp = int(time.time())

    return BlockInfo(
        block_num=block_num,
        signer_public_key=signer_public_key,
        header_signature=header_signature,
        timestamp=timestamp,
        previous_block_id=previous_block_id)


def create_config(latest_block,
                  oldest_block=None,
                  target_count=DEFAULT_TARGET_COUNT,
                  sync_tolerance=DEFAULT_SYNC_TOLERANCE):
    if oldest_block is None:
        oldest_block = latest_block - DEFAULT_TARGET_COUNT
    return BlockInfoConfig(
        latest_block=latest_block,
        oldest_block=oldest_block,
        target_count=target_count,
        sync_tolerance=sync_tolerance)


class TestBlockInfo(TransactionProcessorTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = MessageFactory(
            family_name=FAMILY_NAME,
            family_version=FAMILY_VERSION,
            namespace=NAMESPACE,
        )

    def _send_request(self, block, sync_tolerance=None, target_count=None):
        block_info_txn = BlockInfoTxn(
            block=block,
            sync_tolerance=sync_tolerance,
            target_count=target_count)

        self.validator.send(
            self.factory.create_tp_process_request(
                payload=block_info_txn.SerializeToString(),
                inputs=None,
                outputs=None,
                deps=None))

    def _expect_config_get(self, config=None):
        received = self.validator.expect(
            self.factory.create_get_request(addresses=[CONFIG_ADDRESS]))

        response = {} if config is None \
            else {CONFIG_ADDRESS: config.SerializeToString()}
        self.validator.respond(
            self.factory.create_get_response(response), received)

    def _expect_block_get(self, block):
        received = self.validator.expect(
            self.factory.create_get_request(
                addresses=[create_block_address(block.block_num)]))

        self.validator.respond(
            self.factory.create_get_response({
                create_block_address(block.block_num):
                block.SerializeToString()
            }), received)

    def _expect_set(self, sets):
        received = self.validator.expect(
            self.factory.create_set_request(
                {k: v.SerializeToString()
                 for k, v in sets.items()}))
        self.validator.respond(
            self.factory.create_set_response(addresses=sets.keys()), received)

    def _expect_delete(self, deletes):
        received = self.validator.expect(
            self.factory.create_delete_request(addresses=deletes))

        self.validator.respond(
            self.factory.create_delete_response(addresses=deletes), received)

    def _expect_response(self, status):
        self.validator.expect(self.factory.create_tp_response(status))

    def test_first_block_info(self):
        """Tests that the first block info is set correctly, without changing
        sync tolerance or target count."""

        block_info = create_block_info(block_num=1)
        self._send_request(block=block_info)
        self._expect_config_get()
        self._expect_set({
            create_block_address(1): block_info,
            CONFIG_ADDRESS: create_config(latest_block=1, oldest_block=1),
        })
        self._expect_response("OK")

    def test_new_block_info(self):
        """Tests that a new block info is set correctly, without changing
        sync tolerance or target count."""

        block_num = 8923521
        block_info = create_block_info(block_num=block_num)
        self._send_request(block=block_info)
        self._expect_config_get(create_config(latest_block=block_num - 1))

        prev_block_info = create_block_info(
            block_num=block_num - 1, header_signature="0" * 128,
            timestamp=int(time.time() - 3))
        self._expect_block_get(prev_block_info)

        self._expect_delete([
            create_block_address(block_num - 1 - DEFAULT_TARGET_COUNT),
        ])

        self._expect_set({
            create_block_address(block_num): block_info,
            CONFIG_ADDRESS: create_config(latest_block=block_num),
        })

        self._expect_response("OK")

    def test_new_sync_tolerance(self):
        """Tests that setting a new sync tolerance works correctly."""
        block_num = 163134613422
        block_info = create_block_info(block_num=block_num)
        self._send_request(block=block_info, sync_tolerance=450)
        self._expect_config_get(create_config(latest_block=block_num - 1))

        prev_block_info = create_block_info(
            block_num=block_num - 1, header_signature="0" * 128,
            timestamp=int(time.time() - 3))
        self._expect_block_get(prev_block_info)

        self._expect_delete([
            create_block_address(block_num - 1 - DEFAULT_TARGET_COUNT),
        ])

        self._expect_set({
            create_block_address(block_num): block_info,
            CONFIG_ADDRESS: create_config(
                latest_block=block_num, sync_tolerance=450),
        })

        self._expect_response("OK")

    def test_smaller_target_count(self):
        """Tests that setting a new, smaller target count works correctly."""
        block_num = 122351345
        block_info = create_block_info(block_num=block_num)
        self._send_request(block=block_info, target_count=128)
        config = create_config(latest_block=block_num - 1)
        self._expect_config_get(config)

        prev_block_info = create_block_info(
            block_num=block_num - 1, header_signature="0" * 128,
            timestamp=int(time.time() - 3))
        self._expect_block_get(prev_block_info)

        deletes = [
            create_block_address(i)
            for i in range(config.oldest_block, config.latest_block - 128 + 1)
        ]
        self._expect_delete(deletes)

        self._expect_set({
            create_block_address(block_num): block_info,
            CONFIG_ADDRESS: create_config(
                latest_block=block_num,
                oldest_block=block_num - 128,
                target_count=128),
        })

        self._expect_response("OK")

    def test_bigger_target_count(self):
        """Tests that setting a new, bigger target count works correctly."""
        block_num = 122351345
        block_info = create_block_info(block_num=block_num)
        self._send_request(block=block_info, target_count=512)
        config = create_config(latest_block=block_num - 1)
        self._expect_config_get(config)

        prev_block_info = create_block_info(
            block_num=block_num - 1, header_signature="0" * 128,
            timestamp=int(time.time() - 3))
        self._expect_block_get(prev_block_info)

        self._expect_set({
            create_block_address(block_num): block_info,
            CONFIG_ADDRESS: create_config(
                latest_block=block_num,
                oldest_block=config.oldest_block,
                target_count=512),
        })

        self._expect_response("OK")

    def test_missing_fields(self):
        """Tests that an invalid transaction is handled correctly."""
        block_info = BlockInfo()
        self._send_request(block=block_info)
        self._expect_response("INVALID_TRANSACTION")

    def test_invalid_block_num(self):
        """Tests that an invalid block number is caught."""
        block_num = 924689724697
        block_info = create_block_info(block_num=block_num)
        self._send_request(block=block_info)
        config = create_config(latest_block=block_num - 2)
        self._expect_config_get(config)
        self._expect_response("INVALID_TRANSACTION")

    def test_big_timestamp(self):
        """Tests that a timestamp that is too big is caught. Tests too old and
        too new."""
        block_num = 7133647461978
        block_info = create_block_info(
            block_num=block_num,
            timestamp=int(time.time() + DEFAULT_SYNC_TOLERANCE + 1))
        self._send_request(block=block_info)
        config = create_config(latest_block=block_num - 1)
        self._expect_config_get(config)
        self._expect_response("INVALID_TRANSACTION")

    def test_small_timestamp(self):
        """Tests that a timestamp that is too big is caught. Tests too old and
        too new."""
        block_num = 7133647461978
        block_info = create_block_info(
            block_num=block_num, timestamp=int(time.time() - 5))
        self._send_request(block=block_info)
        config = create_config(latest_block=block_num - 1)
        self._expect_config_get(config)

        self._expect_block_get(create_block_info(
            block_num=block_num - 1, header_signature="0" * 128,
            timestamp=int(time.time())))

        self._expect_response("INVALID_TRANSACTION")

    def test_invalid_block_id(self):
        """Tests that an invalid previous block id is caught."""
        block_num = 643651461
        block_info = create_block_info(block_num=block_num)
        self._send_request(block=block_info)
        self._expect_config_get(create_config(latest_block=block_num - 1))

        prev_block_info = create_block_info(
            block_num=block_num - 1, header_signature="4" * 128,
            timestamp=int(time.time() - 3))
        self._expect_block_get(prev_block_info)

        self._expect_response("INVALID_TRANSACTION")
