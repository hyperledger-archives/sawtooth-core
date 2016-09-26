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

import logging

from gossip import message

logger = logging.getLogger(__name__)


def register_message_handlers(journal):
    journal.dispatcher.register_message_handler(TransactionMessage,
                                                transaction_message_handler)
    journal.dispatcher.register_message_handler(TransactionRequestMessage,
                                                _txn_request_handler)


class TransactionMessage(message.Message):
    MessageType = "/journal.messages.TransactionMessage/Transaction"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(TransactionMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = False
        self.IsReliable = True
        self.Transaction = None

    def dump(self):
        result = super(TransactionMessage, self).dump()
        result['Transaction'] = self.Transaction.dump()

        return result


def transaction_message_handler(msg, journal):
    # if we already have this transaction, then there is no reason to
    # send it on, be conservative about forwarding messages
    if not msg.Transaction:
        logger.warn('transaction message missing transaction; %s',
                    msg.MessageType)
        return

    logger.debug('handle transaction message with identifier %s',
                 msg.Transaction.Identifier)

    with journal._txn_lock:
        if journal.TransactionStore.get(msg.Transaction.Identifier):
            return

        if journal.PendingTransactions.get(msg.Transaction.Identifier):
            return

        journal.add_pending_transaction(msg.Transaction)
        journal.forward_message(msg,
                                exceptions=[msg.SenderID],
                                initialize=False)


class TransactionRequestMessage(message.Message):
    MessageType = "/journal.messages.TransactionMessage/TransactionRequest"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(TransactionRequestMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = False
        self.IsReliable = True

        self.TransactionID = minfo.get('TransactionID')

    def dump(self):
        result = super(TransactionRequestMessage, self).dump()
        result['TransactionID'] = self.TransactionID

        return result


def _txn_request_handler(msg, journal):
    # a transaction might be in the committed transaction list only as a
    # placeholder, so we have to make sure that it is there and that it is not
    # None
    with journal._txn_lock:
        txn = journal.TransactionStore.get(msg.TransactionID)
        if txn:
            reply = txn.build_message()
            journal.forward_message(reply)
            return

        journal.request_missing_txn(msg.TransactionID,
                                    exceptions=[msg.SenderID],
                                    request=msg)
