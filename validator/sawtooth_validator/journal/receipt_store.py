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
from sawtooth_validator.protobuf.transaction_receipt_pb2 import \
    TransactionReceipt
from sawtooth_validator.protobuf.client_receipt_pb2 import \
    ClientReceiptGetRequest
from sawtooth_validator.protobuf.client_receipt_pb2 import \
    ClientReceiptGetResponse

from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.protobuf import validator_pb2

from sawtooth_validator.journal.chain import ChainObserver


class TransactionReceiptStore(ChainObserver):
    """A TransactionReceiptStore persists TransactionReceipt records to a
    provided database implementation.
    """

    def __init__(self, receipt_db):
        """Constructs a TransactionReceiptStore, backed by a given database
        implementation.

        Args:
            receipt_db (:obj:sawtooth_validator.database.database.Database): A
                database implementation that backs this store.
        """
        self._receipt_db = receipt_db

    def put(self, txn_id, txn_receipt):
        """Add the given transaction receipt to the store. Does not guarantee
           it has been written to the backing store.

        Args:
            txn_id (str): the id of the transaction being stored.
            receipt (TransactionReceipt): the receipt object to store.
        """
        self._receipt_db[txn_id] = txn_receipt.SerializeToString()

    def get(self, txn_id):
        """Returns the TransactionReceipt

        Args:
            txn_id (str): the id of the transaction for which the receipt
                should be retrieved.

        Returns:
            TransactionReceipt: The receipt for the given transaction id.

        Raises:
            KeyError: if the transaction id is unknown.
        """
        if txn_id not in self._receipt_db:
            raise KeyError('Unknown transaction id {}'.format(txn_id))

        txn_receipt_bytes = self._receipt_db[txn_id]
        txn_receipt = TransactionReceipt()
        txn_receipt.ParseFromString(txn_receipt_bytes)
        return txn_receipt

    def chain_update(self, block, receipts):
        for receipt in receipts:
            self.put(receipt.transaction_id, receipt)


class ClientReceiptGetRequestHandler(Handler):
    """Handles receiving messages for getting transactionreceipts."""
    _msg_type = validator_pb2.Message.CLIENT_RECEIPT_GET_RESPONSE

    def __init__(self, txn_receipt_store):
        self._txn_receipt_store = txn_receipt_store

    def handle(self, connection_id, message_content):
        request = ClientReceiptGetRequest()
        request.ParseFromString(message_content)

        try:
            response = ClientReceiptGetResponse(
                receipts=[
                    self._txn_receipt_store.get(txn_id)
                    for txn_id in request.transaction_ids
                ],
                status=ClientReceiptGetResponse.OK)

        except KeyError:
            response = ClientReceiptGetResponse(
                status=ClientReceiptGetResponse.NO_RESOURCE)

        return HandlerResult(
            HandlerStatus.RETURN,
            message_out=response,
            message_type=self._msg_type)
