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

import unittest

from sawtooth_sdk.consensus.zmq_service import ZmqService
from sawtooth_sdk.messaging.future import Future
from sawtooth_sdk.messaging.future import FutureResult
from sawtooth_sdk.protobuf import consensus_pb2
from sawtooth_sdk.protobuf.validator_pb2 import Message


class TestService(unittest.TestCase):
    def setUp(self):
        self.mock_stream = unittest.mock.Mock()
        self.service = ZmqService(
            stream=self.mock_stream,
            timeout=10)

    def _make_future(self, message_type, content):
        fut = Future('test')
        fut.set_result(FutureResult(
            message_type=message_type,
            content=content))
        return fut

    def test_send_to(self):
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_SEND_TO_RESPONSE,
            content=consensus_pb2.ConsensusSendToResponse(
                status=consensus_pb2.ConsensusSendToResponse.OK
            ).SerializeToString())

        self.service.send_to(
            receiver_id=b'receiver_id',
            message_type='message_type',
            payload=b'payload')

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_SEND_TO_REQUEST,
            content=consensus_pb2.ConsensusSendToRequest(
                message_type='message_type',
                content=b'payload',
                receiver_id=b'receiver_id').SerializeToString())

    def test_broadcast(self):
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_BROADCAST_RESPONSE,
            content=consensus_pb2.ConsensusBroadcastResponse(
                status=consensus_pb2.ConsensusBroadcastResponse.OK
            ).SerializeToString())

        self.service.broadcast(
            message_type='message_type',
            payload=b'payload')

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_BROADCAST_REQUEST,
            content=consensus_pb2.ConsensusBroadcastRequest(
                message_type='message_type',
                content=b'payload').SerializeToString())

    def test_initialize_block(self):
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_INITIALIZE_BLOCK_RESPONSE,
            content=consensus_pb2.ConsensusInitializeBlockResponse(
                status=consensus_pb2.ConsensusInitializeBlockResponse.OK
            ).SerializeToString())

        self.service.initialize_block(previous_id=b'test')

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_INITIALIZE_BLOCK_REQUEST,
            content=consensus_pb2.ConsensusInitializeBlockRequest(
                previous_id=b'test').SerializeToString())

    def test_summarize_block(self):
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_SUMMARIZE_BLOCK_RESPONSE,
            content=consensus_pb2.ConsensusSummarizeBlockResponse(
                status=consensus_pb2.ConsensusSummarizeBlockResponse.OK,
                summary=b'summary').SerializeToString())

        result = self.service.summarize_block()

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_SUMMARIZE_BLOCK_REQUEST,
            content=consensus_pb2.ConsensusSummarizeBlockRequest()
                                 .SerializeToString())

        self.assertEqual(result, b'summary')

    def test_finalize_block(self):
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_FINALIZE_BLOCK_RESPONSE,
            content=consensus_pb2.ConsensusFinalizeBlockResponse(
                status=consensus_pb2.ConsensusFinalizeBlockResponse.OK,
                block_id=b'block_id').SerializeToString())

        result = self.service.finalize_block(data=b'test')

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_FINALIZE_BLOCK_REQUEST,
            content=consensus_pb2.ConsensusFinalizeBlockRequest(
                data=b'test').SerializeToString())

        self.assertEqual(result, b'block_id')

    def test_cancel_block(self):
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_CANCEL_BLOCK_RESPONSE,
            content=consensus_pb2.ConsensusCancelBlockResponse(
                status=consensus_pb2.ConsensusCancelBlockResponse.OK
            ).SerializeToString())

        self.service.cancel_block()

        request = consensus_pb2.ConsensusCancelBlockRequest()

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_CANCEL_BLOCK_REQUEST,
            content=request.SerializeToString())

    def test_check_blocks(self):
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_CHECK_BLOCKS_RESPONSE,
            content=consensus_pb2.ConsensusCheckBlocksResponse(
                status=consensus_pb2.ConsensusCheckBlocksResponse.OK
            ).SerializeToString())

        self.service.check_blocks(priority=[b'test1', b'test2'])

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_CHECK_BLOCKS_REQUEST,
            content=consensus_pb2.ConsensusCheckBlocksRequest(
                block_ids=[b'test1', b'test2']).SerializeToString())

    def test_commit_block(self):
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_COMMIT_BLOCK_RESPONSE,
            content=consensus_pb2.ConsensusCommitBlockResponse(
                status=consensus_pb2.ConsensusCommitBlockResponse.OK
            ).SerializeToString())

        self.service.commit_block(block_id=b'test')

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_COMMIT_BLOCK_REQUEST,
            content=consensus_pb2.ConsensusCommitBlockRequest(
                block_id=b'test').SerializeToString())

    def test_ignore_block(self):
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_IGNORE_BLOCK_RESPONSE,
            content=consensus_pb2.ConsensusIgnoreBlockResponse(
                status=consensus_pb2.ConsensusIgnoreBlockResponse.OK
            ).SerializeToString())

        self.service.ignore_block(block_id=b'test')

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_IGNORE_BLOCK_REQUEST,
            content=consensus_pb2.ConsensusIgnoreBlockRequest(
                block_id=b'test').SerializeToString())

    def test_fail_block(self):
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_FAIL_BLOCK_RESPONSE,
            content=consensus_pb2.ConsensusFailBlockResponse(
                status=consensus_pb2.ConsensusFailBlockResponse.OK
            ).SerializeToString())

        self.service.fail_block(block_id=b'test')

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_FAIL_BLOCK_REQUEST,
            content=consensus_pb2.ConsensusFailBlockRequest(
                block_id=b'test').SerializeToString())

    def test_get_blocks(self):
        block_1 = consensus_pb2.ConsensusBlock(
            block_id=b'block1',
            previous_id=b'block0',
            signer_id=b'signer1',
            block_num=1,
            payload=b'test1')

        block_2 = consensus_pb2.ConsensusBlock(
            block_id=b'block2',
            previous_id=b'block1',
            signer_id=b'signer2',
            block_num=2,
            payload=b'test2')

        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_BLOCKS_GET_RESPONSE,
            content=consensus_pb2.ConsensusBlocksGetResponse(
                status=consensus_pb2.ConsensusBlocksGetResponse.OK,
                blocks=[block_1, block_2]).SerializeToString())

        blocks = self.service.get_blocks(block_ids=[b'id1', b'id2'])

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_BLOCKS_GET_REQUEST,
            content=consensus_pb2.ConsensusBlocksGetRequest(
                block_ids=[b'id1', b'id2']).SerializeToString())

        self.assertEqual({
            block_id: (
                block.previous_id,
                block.signer_id,
                block.block_num,
                block.payload)
            for block_id, block in blocks.items()
        }, {
            b'block1': (b'block0', b'signer1', 1, b'test1'),
            b'block2': (b'block1', b'signer2', 2, b'test2'),
        })

    def test_get_chain_head(self):
        block = consensus_pb2.ConsensusBlock(
            block_id=b'block',
            previous_id=b'block0',
            signer_id=b'signer',
            block_num=1,
            payload=b'test')

        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_CHAIN_HEAD_GET_RESPONSE,
            content=consensus_pb2.ConsensusChainHeadGetResponse(
                status=consensus_pb2.ConsensusChainHeadGetResponse.OK,
                block=block).SerializeToString())

        chain_head = self.service.get_chain_head()

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_CHAIN_HEAD_GET_REQUEST,
            content=consensus_pb2.ConsensusChainHeadGetRequest()
            .SerializeToString())

        self.assertEqual(chain_head.block_id, b'block')
        self.assertEqual(chain_head.previous_id, b'block0')
        self.assertEqual(chain_head.signer_id, b'signer')
        self.assertEqual(chain_head.block_num, 1)
        self.assertEqual(chain_head.payload, b'test')

    def test_get_settings(self):
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_SETTINGS_GET_RESPONSE,
            content=consensus_pb2.ConsensusSettingsGetResponse(
                status=consensus_pb2.ConsensusSettingsGetResponse.OK,
                entries=[
                    consensus_pb2.ConsensusSettingsEntry(
                        key='key1',
                        value='value1'),
                    consensus_pb2.ConsensusSettingsEntry(
                        key='key2',
                        value='value2')]).SerializeToString())

        entries = self.service.get_settings(
            block_id=b'test',
            settings=['test1', 'test2'])

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_SETTINGS_GET_REQUEST,
            content=consensus_pb2.ConsensusSettingsGetRequest(
                block_id=b'test',
                keys=['test1', 'test2']).SerializeToString())

        self.assertEqual(
            entries, {
                'key1': 'value1',
                'key2': 'value2',
            })

    def test_get_state(self):
        self.mock_stream.send.return_value = self._make_future(
            message_type=Message.CONSENSUS_STATE_GET_RESPONSE,
            content=consensus_pb2.ConsensusStateGetResponse(
                status=consensus_pb2.ConsensusStateGetResponse.OK,
                entries=[
                    consensus_pb2.ConsensusStateEntry(
                        address='address1',
                        data=b'data1'),
                    consensus_pb2.ConsensusStateEntry(
                        address='address2',
                        data=b'data2')]).SerializeToString())

        entries = self.service.get_state(
            block_id=b'test',
            addresses=['test1', 'test2'])

        self.mock_stream.send.assert_called_with(
            message_type=Message.CONSENSUS_STATE_GET_REQUEST,
            content=consensus_pb2.ConsensusStateGetRequest(
                block_id=b'test',
                addresses=['test1', 'test2']).SerializeToString())

        self.assertEqual(
            entries, {
                'address1': b'data1',
                'address2': b'data2',
            })
