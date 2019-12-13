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

# pylint: disable=invalid-name

import unittest

from sawtooth_validator.protobuf import network_pb2
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf import block_pb2
from sawtooth_validator.protobuf import batch_pb2
from sawtooth_validator.protobuf import transaction_pb2
from sawtooth_validator.journal.responder import Responder
from sawtooth_validator.journal.responder import BlockResponderHandler
from sawtooth_validator.journal.responder import BatchByBatchIdResponderHandler
from sawtooth_validator.journal.responder import \
    BatchByTransactionIdResponderHandler
from sawtooth_validator.journal.responder import ResponderBlockResponseHandler
from sawtooth_validator.journal.responder import ResponderBatchResponseHandler
from test_responder.mock import MockGossip
from test_responder.mock import MockCompleter


class TestResponder(unittest.TestCase):
    def setUp(self):
        self.gossip = MockGossip()
        self.completer = MockCompleter()
        self.responder = Responder(self.completer)
        self.block_request_handler = \
            BlockResponderHandler(self.responder, self.gossip)
        self.block_response_handler = \
            ResponderBlockResponseHandler(self.responder, self.gossip)
        self.batch_request_handler = \
            BatchByBatchIdResponderHandler(self.responder, self.gossip)
        self.batch_response_handler = \
            ResponderBatchResponseHandler(self.responder, self.gossip)
        self.batch_by_txn_request_handler = \
            BatchByTransactionIdResponderHandler(self.responder, self.gossip)

    # Tests
    def test_block_responder_handler(self):
        """
        Test that the BlockResponderHandler correctly broadcasts a received
        request that the Responder cannot respond to, or sends a
        GossipBlockResponse back to the connection_id the handler received
        the request from.
        """
        # The completer does not have the requested block
        before_message = network_pb2.GossipBlockRequest(
            block_id="ABC",
            nonce="1",
            time_to_live=1)

        after_message = network_pb2.GossipBlockRequest(
            block_id="ABC",
            nonce="1",
            time_to_live=0)

        self.block_request_handler.handle(
            "Connection_1", before_message.SerializeToString())
        # If we cannot respond to the request, broadcast the block request
        # and add to pending request
        self.assert_message_was_broadcasted(
            after_message, validator_pb2.Message.GOSSIP_BLOCK_REQUEST)

        self.assert_request_pending(
            requested_id="ABC", connection_id="Connection_1")
        self.assert_message_not_sent(connection_id="Connection_1")

        # Add the block to the completer and resend the Block Request
        block = block_pb2.Block(header_signature="ABC")
        self.completer.add_block(block)

        message = network_pb2.GossipBlockRequest(
            block_id="ABC",
            nonce="2",
            time_to_live=1)

        self.block_request_handler.handle(
            "Connection_1", message.SerializeToString())

        # Check that the a Block Response was sent back to "Connection_1"
        self.assert_message_sent(
            connection_id="Connection_1",
            message_type=validator_pb2.Message.GOSSIP_BLOCK_RESPONSE
        )

    def test_block_responder_handler_requested(self):
        """
        Test that the BlockResponderHandler correctly broadcasts a received
        request that the Responder cannot respond to, and does not rebroadcast
        the same request.  If we have already recieved the
        request, do nothing.
        """
        before_message = network_pb2.GossipBlockRequest(
            block_id="ABC",
            nonce="1",
            time_to_live=1)

        after_message = network_pb2.GossipBlockRequest(
            block_id="ABC",
            nonce="1",
            time_to_live=0)

        self.block_request_handler.handle(
            "Connection_1", before_message.SerializeToString())
        # If we cannot respond to the request, broadcast the block request
        # and add to pending request
        self.assert_message_was_broadcasted(
            after_message, validator_pb2.Message.GOSSIP_BLOCK_REQUEST)

        self.assert_request_pending(
            requested_id="ABC", connection_id="Connection_1")
        self.assert_message_not_sent(connection_id="Connection_1")

        self.gossip.clear()

        # Message should be dropped since the same message has already been
        # handled
        self.block_request_handler.handle(
            "Connection_2", before_message.SerializeToString())

        self.assert_message_was_not_broadcasted(
            before_message, validator_pb2.Message.GOSSIP_BLOCK_REQUEST)

        self.assert_request_not_pending(
            requested_id="ABC", connection_id="Connection_2")

        message = network_pb2.GossipBlockRequest(
            block_id="ABC",
            nonce="2",
            time_to_live=1)

        self.block_request_handler.handle(
            "Connection_2", message.SerializeToString())

        self.assert_message_was_not_broadcasted(
            message, validator_pb2.Message.GOSSIP_BLOCK_REQUEST)

        self.assert_request_pending(
            requested_id="ABC", connection_id="Connection_2")
        self.assert_message_not_sent(connection_id="Connection_2")

    def test_responder_block_response_handler(self):
        """
        Test that the ResponderBlockResponseHandler, after receiving a Block
        Response, checks to see if the responder has any pending request for
        that response and forwards the response on to the connection_id that
        had requested it.
        """
        # The Responder does not have any pending requests for block "ABC"
        block = block_pb2.Block(header_signature="ABC")
        response_message = network_pb2.GossipBlockResponse(
            content=block.SerializeToString())

        self.block_response_handler.handle(
            "Connection_1", (block, response_message.SerializeToString()))

        # ResponderBlockResponseHandler should not send any messages.
        self.assert_message_not_sent("Connection_1")
        self.assert_request_not_pending(requested_id="ABC")

        # Handle a request message for block "ABC". This adds it to the pending
        # request queue.
        request_message = \
            network_pb2.GossipBlockRequest(block_id="ABC", time_to_live=1)

        self.block_request_handler.handle(
            "Connection_2", request_message.SerializeToString())

        self.assert_request_pending(
            requested_id="ABC", connection_id="Connection_2")

        # Handle the the BlockResponse Message. Since Connection_2 had
        # requested the block but it could not be fulfilled at that time of the
        # request the received BlockResponse is forwarded to Connection_2
        self.block_response_handler.handle(
            "Connection_1", (block, response_message.SerializeToString()))

        self.assert_message_sent(
            connection_id="Connection_2",
            message_type=validator_pb2.Message.GOSSIP_BLOCK_RESPONSE
        )
        # The request for block "ABC" from "Connection_2" is no longer pending
        # it should be removed from the pending request cache.
        self.assert_request_not_pending(requested_id="ABC")

    def test_batch_by_id_responder_handler(self):
        """
        Test that the BatchByBatchIdResponderHandler correctly broadcasts a
        received request that the Responder cannot respond to, or sends a
        GossipBatchResponse back to the connection_id the handler received
        the request from.
        """
        # The completer does not have the requested batch
        before_message = network_pb2.GossipBatchByBatchIdRequest(
            id="abc",
            nonce="1",
            time_to_live=1)

        after_message = network_pb2.GossipBatchByBatchIdRequest(
            id="abc",
            nonce="1",
            time_to_live=0)

        self.batch_request_handler.handle(
            "Connection_1", before_message.SerializeToString())
        # If we cannot respond to the request broadcast batch request and add
        # to pending request
        self.assert_message_was_broadcasted(
            after_message,
            validator_pb2.Message.GOSSIP_BATCH_BY_BATCH_ID_REQUEST)
        self.assert_request_pending(
            requested_id="abc", connection_id="Connection_1")
        self.assert_message_not_sent(connection_id="Connection_1")

        # Add the batch to the completer and resend the BatchByBatchIdRequest
        message = network_pb2.GossipBatchByBatchIdRequest(
            id="abc",
            nonce="2",
            time_to_live=1)
        batch = batch_pb2.Batch(header_signature="abc")
        self.completer.add_batch(batch)
        self.batch_request_handler.handle(
            "Connection_1", message.SerializeToString())

        # Check that the a Batch Response was sent back to "Connection_1"
        self.assert_message_sent(
            connection_id="Connection_1",
            message_type=validator_pb2.Message.GOSSIP_BATCH_RESPONSE
        )

    def test_batch_by_id_responder_handler_requested(self):
        """
        Test that the BatchByBatchIdResponderHandler correctly broadcasts
        a received request that the Responder cannot respond to, and does not
        rebroadcast the same request again.  If we have already recieved the
        request, do nothing.
        """
        # The completer does not have the requested batch
        before_message = network_pb2.GossipBatchByBatchIdRequest(
            id="abc",
            nonce="1",
            time_to_live=1)

        after_message = network_pb2.GossipBatchByBatchIdRequest(
            id="abc",
            nonce="1",
            time_to_live=0)
        self.batch_request_handler.handle(
            "Connection_1", before_message.SerializeToString())
        # If we cannot respond to the request broadcast batch request and add
        # to pending request
        self.assert_message_was_broadcasted(
            after_message,
            validator_pb2.Message.GOSSIP_BATCH_BY_BATCH_ID_REQUEST)
        self.assert_request_pending(
            requested_id="abc", connection_id="Connection_1")
        self.assert_message_not_sent(connection_id="Connection_1")

        self.gossip.clear()

        # Message should be dropped since the same message has already been
        # handled
        self.batch_request_handler.handle(
            "Connection_2", before_message.SerializeToString())

        self.assert_message_was_not_broadcasted(
            before_message,
            validator_pb2.Message.GOSSIP_BATCH_BY_BATCH_ID_REQUEST)

        self.assert_request_not_pending(
            requested_id="abc", connection_id="Connection_2")

        message = network_pb2.GossipBatchByBatchIdRequest(
            id="abc",
            nonce="2",
            time_to_live=1)

        self.batch_request_handler.handle(
            "Connection_2", message.SerializeToString())

        self.assert_message_was_not_broadcasted(
            message, validator_pb2.Message.GOSSIP_BATCH_BY_BATCH_ID_REQUEST)

        self.assert_request_pending(
            requested_id="abc", connection_id="Connection_2")
        self.assert_message_not_sent(connection_id="Connection_2")

    def test_batch_by_transaction_id_response_handler(self):
        """
        Test that the BatchByTransactionIdResponderHandler correctly broadcasts
        a received request that the Responder cannot respond to, or sends a
        GossipBatchResponse back to the connection_id the handler received
        the request from.
        """
        # The completer does not have the requested batch with the transaction
        before_message = network_pb2.GossipBatchByTransactionIdRequest(
            ids=["123"],
            nonce="1",
            time_to_live=1)

        after_message = network_pb2.GossipBatchByTransactionIdRequest(
            ids=["123"],
            nonce="1",
            time_to_live=0)

        self.batch_by_txn_request_handler.handle(
            "Connection_1", before_message.SerializeToString())

        # If we cannot respond to the request, broadcast batch request and add
        # to pending request
        self.assert_message_was_broadcasted(
            after_message,
            validator_pb2.Message.GOSSIP_BATCH_BY_TRANSACTION_ID_REQUEST
        )
        self.assert_request_pending(
            requested_id="123", connection_id="Connection_1")
        self.assert_message_not_sent(connection_id="Connection_1")

        # Add the batch to the completer and resend the
        # BatchByTransactionIdRequest
        message = network_pb2.GossipBatchByTransactionIdRequest(
            ids=["123"],
            nonce="2",
            time_to_live=1)
        transaction = transaction_pb2.Transaction(header_signature="123")
        batch = batch_pb2.Batch(
            header_signature="abc", transactions=[transaction])
        self.completer.add_batch(batch)
        self.batch_request_handler.handle(
            "Connection_1", message.SerializeToString())

        # Check that the a Batch Response was sent back to "Connection_1"
        self.assert_message_sent(
            connection_id="Connection_1",
            message_type=validator_pb2.Message.GOSSIP_BATCH_RESPONSE
        )

    def test_batch_by_transaction_id_response_handler_requested(self):
        """
        Test that the BatchByTransactionIdResponderHandler correctly broadcasts
        a received request that the Responder cannot respond to, and does not
        rebroadcast the same request again. If we have already recieved the
        request, do nothing.
        """
        # The completer does not have the requested batch with the transaction
        before_message = network_pb2.GossipBatchByTransactionIdRequest(
            ids=["123"],
            time_to_live=1)

        after_message = network_pb2.GossipBatchByTransactionIdRequest(
            ids=["123"],
            time_to_live=0)

        self.batch_by_txn_request_handler.handle(
            "Connection_1", before_message.SerializeToString())

        # If we cannot respond to the request, broadcast batch request and add
        # to pending request
        self.assert_message_was_broadcasted(
            after_message,
            validator_pb2.Message.GOSSIP_BATCH_BY_TRANSACTION_ID_REQUEST
        )
        self.assert_request_pending(
            requested_id="123", connection_id="Connection_1")
        self.assert_message_not_sent(connection_id="Connection_1")

        self.gossip.clear()

        # Message should be dropped since the same message has already been
        # handled
        self.batch_by_txn_request_handler.handle(
            "Connection_2", before_message.SerializeToString())

        self.assert_message_was_not_broadcasted(
            after_message,
            validator_pb2.Message.GOSSIP_BATCH_BY_TRANSACTION_ID_REQUEST
        )

        self.assert_request_not_pending(
            requested_id="123", connection_id="Connection_2")

        message = network_pb2.GossipBatchByTransactionIdRequest(
            ids=["123"],
            nonce="2",
            time_to_live=1)
        self.batch_by_txn_request_handler.handle(
            "Connection_2", message.SerializeToString())

        self.assert_message_was_not_broadcasted(
            message,
            validator_pb2.Message.GOSSIP_BATCH_BY_TRANSACTION_ID_REQUEST
        )
        self.assert_request_pending(
            requested_id="123", connection_id="Connection_2")
        self.assert_message_not_sent(connection_id="Connection_2")

    def test_batch_by_transaction_id_multiple_txn_ids(self):
        """
        Test that the BatchByTransactionIdResponderHandler correctly broadcasts
        a new request with only the transaction_ids that the Responder cannot
        respond to, and sends a GossipBatchResponse for the transactions_id
        requests that can be satisfied.
        """
        # Add batch that has txn 123
        transaction = transaction_pb2.Transaction(header_signature="123")
        batch = batch_pb2.Batch(
            header_signature="abc", transactions=[transaction])
        self.completer.add_batch(batch)
        # Request transactions 123 and 456
        message = network_pb2.GossipBatchByTransactionIdRequest(
            ids=["123", "456"],
            time_to_live=1)
        self.batch_by_txn_request_handler.handle(
            "Connection_1", message.SerializeToString())
        self.batch_request_handler.handle(
            "Connection_1", message.SerializeToString())

        # Respond with a BatchResponse for transaction 123
        self.assert_message_sent(
            connection_id="Connection_1",
            message_type=validator_pb2.Message.GOSSIP_BATCH_RESPONSE
        )

        # Broadcast a BatchByTransactionIdRequest for just 456
        after_message = \
            network_pb2.GossipBatchByTransactionIdRequest(
                ids=["456"],
                time_to_live=0)

        self.assert_message_was_broadcasted(
            after_message,
            validator_pb2.Message.GOSSIP_BATCH_BY_TRANSACTION_ID_REQUEST)

        # And set a pending request for 456
        self.assert_request_pending(
            requested_id="456", connection_id="Connection_1")

    def test_responder_batch_response_handler(self):
        """
        Test that the ResponderBatchResponseHandler, after receiving a Batch
        Response, checks to see if the responder has any pending request for
        that batch and forwards the response on to the connection_id that
        had requested it.
        """
        # The Responder does not have any pending requests for block "ABC"
        batch = batch_pb2.Batch(header_signature="abc")

        response_message = network_pb2.GossipBatchResponse(
            content=batch.SerializeToString())

        self.batch_response_handler.handle(
            "Connection_1", (batch, response_message.SerializeToString()))

        # ResponderBlockResponseHandler should not send any messages.
        self.assert_message_not_sent("Connection_1")
        self.assert_request_not_pending(requested_id="abc")

        # Handle a request message for batch "abc". This adds it to the pending
        # request queue.
        request_message = \
            network_pb2.GossipBatchByBatchIdRequest(id="abc", time_to_live=1)

        self.batch_request_handler.handle(
            "Connection_2", request_message.SerializeToString())

        self.assert_request_pending(
            requested_id="abc", connection_id="Connection_2")

        # Handle the the BatchResponse Message. Since Connection_2 had
        # requested the batch but it could not be fulfilled at that time of the
        # request the received BatchResponse is forwarded to Connection_2
        self.batch_response_handler.handle(
            "Connection_1", (batch, response_message.SerializeToString()))

        self.assert_message_sent(
            connection_id="Connection_2",
            message_type=validator_pb2.Message.GOSSIP_BATCH_RESPONSE
        )
        # The request for batch "abc" from "Connection_2" is no longer pending
        # it should be removed from the pending request cache.
        self.assert_request_not_pending(requested_id="abc")

    def test_responder_batch_response_txn_handler(self):
        """
        Test that the ResponderBatchResponseHandler, after receiving a Batch
        Response, checks to see if the responder has any pending request for
        that transactions in the batch and forwards the response on to the
        connection_id that had them.
        """
        transaction = transaction_pb2.Transaction(header_signature="123")
        batch = batch_pb2.Batch(
            header_signature="abc", transactions=[transaction])

        response_message = network_pb2.GossipBatchResponse(
            content=batch.SerializeToString())

        request_message = \
            network_pb2.GossipBatchByTransactionIdRequest(
                ids=["123"],
                time_to_live=1)

        # Send BatchByTransaciontIdRequest for txn "123" and add it to the
        # pending request cache
        self.batch_request_handler.handle(
            "Connection_2", request_message.SerializeToString())

        self.assert_request_pending(
            requested_id="123", connection_id="Connection_2")

        # Send Batch Response that contains the batch that has txn "123"
        self.batch_response_handler.handle(
            "Connection_1", (batch, response_message.SerializeToString()))

        # Handle the the BatchResponse Message. Since Connection_2 had
        # requested the txn_id in the batch but it could not be fulfilled at
        # that time of the request the received BatchResponse is forwarded to
        # Connection_2
        self.assert_message_sent(
            connection_id="Connection_2",
            message_type=validator_pb2.Message.GOSSIP_BATCH_RESPONSE
        )
        # The request for transaction_id "123" from "Connection_2" is no
        # longer pending it should be removed from the pending request cache.
        self.assert_request_not_pending(requested_id="123")

    # assertions
    def assert_message_was_broadcasted(self, message, message_type):
        self.assertIn(message, self.gossip.broadcasted[message_type])

    def assert_message_was_not_broadcasted(self, message, message_type):
        if message_type in self.gossip.broadcasted:
            self.assertNotIn(message, self.gossip.broadcasted[message_type])
        else:
            self.assertIsNone(self.gossip.broadcasted.get(message_type))

    def assert_message_not_sent(self, connection_id):
        self.assertIsNone(self.gossip.sent.get(connection_id))

    def assert_message_sent(self, connection_id, message_type):
        self.assertIsNotNone(self.gossip.sent.get(connection_id))
        self.assertTrue(
            self.gossip.sent.get(connection_id)[0][0] == message_type)

    def assert_request_pending(self, requested_id, connection_id):
        self.assertIn(connection_id, self.responder.get_request(requested_id))

    def assert_request_not_pending(self, requested_id, connection_id=None):
        if self.responder.get_request(requested_id) is not None:
            self.assertFalse(
                connection_id in self.responder.get_request(requested_id))
        else:
            self.assertIsNone(self.responder.get_request(requested_id))
