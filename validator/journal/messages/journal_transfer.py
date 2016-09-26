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
    """
    Register the message handlers that every journal should support.
    """
    journal.dispatcher.register_message_handler(
        BlockListRequestMessage,
        _blocklistrequesthandler)
    journal.dispatcher.register_message_handler(
        UncommittedListRequestMessage,
        _uncommittedlistrequesthandler)
    journal.dispatcher.register_message_handler(
        BlockRequestMessage,
        _blockrequesthandler)
    journal.dispatcher.register_message_handler(
        TransactionRequestMessage,
        _txnrequesthandler)


class BlockListRequestMessage(message.Message):
    MessageType = "/journal.messages.JournalTransfer/BlockListRequest"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(BlockListRequestMessage, self).__init__(minfo)
        self.BlockListIndex = minfo.get('BlockListIndex', 0)

        self.IsSystemMessage = True
        self.IsForward = False
        self.IsReliable = True

    def dump(self):
        result = super(BlockListRequestMessage, self).dump()
        result['BlockListIndex'] = self.BlockListIndex
        return result


def _blocklistrequesthandler(msg, journal):
    gossip = journal.gossip
    source = gossip.NodeMap.get(msg.OriginatorID, msg.OriginatorID[:8])
    logger.debug(
        'processing incoming blocklist request for journal transfer from %s',
        source)

    if msg.OriginatorID == gossip.LocalNode.Identifier:
        logger.info('node %s received its own request, ignore',
                    gossip.LocalNode.Identifier[:8])
        return

    if journal.Initializing:
        src = gossip.NodeMap.get(msg.OriginatorID, msg.OriginatorID[:8])
        logger.warn(
            'received blocklist transfer request from %s prior to completing '
            'initialization',
            src)
        gossip.send_message(TransferFailedMessage(), msg.OriginatorID)
        return

    reply = BlockListReplyMessage()
    reply.InReplyTo = msg.Identifier
    reply.BlockListIndex = msg.BlockListIndex

    blockids = journal.committed_block_ids()
    blockids.reverse()

    index = msg.BlockListIndex
    if index < len(blockids):
        reply.BlockIDs = blockids[index:index + 100]

    logger.debug('sending %d committed blocks to %s for request %s',
                 len(reply.BlockIDs), source, msg.Identifier[:8])
    gossip.send_message(reply, msg.OriginatorID)


class BlockListReplyMessage(message.Message):
    MessageType = "/journal.messages.JournalTransfer/BlockListReply"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(BlockListReplyMessage, self).__init__(minfo)

        self.InReplyTo = minfo.get('InReplyTo')
        self.BlockListIndex = minfo.get('BlockListIndex', 0)
        self.BlockIDs = minfo.get('BlockIDs', [])
        self.UncommittedTxnIDs = minfo.get('UncommittedTxnIDs', [])

        self.IsSystemMessage = True
        self.IsForward = False
        self.IsReliable = True

    def dump(self):
        result = super(BlockListReplyMessage, self).dump()
        result['BlockListIndex'] = self.BlockListIndex

        result['BlockIDs'] = []
        for blkid in self.BlockIDs:
            result['BlockIDs'].append(blkid)

        result['UncommittedTxnIDs'] = []
        for txnid in self.UncommittedTxnIDs:
            result['UncommittedTxnIDs'].append(txnid)

        result['InReplyTo'] = self.InReplyTo
        return result


class UncommittedListRequestMessage(message.Message):
    MessageType = "/journal.messages.JournalTransfer/UncommittedListRequest"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(UncommittedListRequestMessage, self).__init__(minfo)
        self.TransactionListIndex = minfo.get('TransactionListIndex', 0)

        self.IsSystemMessage = True
        self.IsForward = False
        self.IsReliable = True

    def dump(self):
        result = super(UncommittedListRequestMessage, self).dump()
        result['TransactionListIndex'] = self.TransactionListIndex
        return result


def _uncommittedlistrequesthandler(msg, journal):
    gossip = journal.gossip
    source = gossip.NodeMap.get(msg.OriginatorID, msg.OriginatorID[:8])
    logger.debug(
        'processing incoming uncommitted list request for journal transfer '
        'from %s',
        source)

    if msg.OriginatorID == gossip.LocalNode.Identifier:
        logger.info('node %s received its own request, ignore',
                    gossip.LocalNode.Identifier[:8])
        return

    if journal.Initializing:
        src = gossip.NodeMap.get(msg.OriginatorID, msg.OriginatorID[:8])
        logger.warn(
            'received uncommitted list transfer request from %s prior to '
            'completing initialization',
            src)
        journal.send_message(TransferFailedMessage(), msg.OriginatorID)
        return

    reply = UncommittedListReplyMessage()
    reply.InReplyTo = msg.Identifier
    reply.TransactionListIndex = msg.TransactionListIndex

    index = msg.TransactionListIndex
    txns = journal.PendingTransactions.keys()
    if index < len(txns):
        reply.TransactionIDs = txns[index:index + 100]

    logger.debug('sending %d uncommitted txns to %s for request %s',
                 len(reply.TransactionIDs), source, msg.Identifier[:8])
    gossip.send_message(reply, msg.OriginatorID)


class UncommittedListReplyMessage(message.Message):
    MessageType = "/journal.messages.JournalTransfer/UncommittedListReply"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(UncommittedListReplyMessage, self).__init__(minfo)

        self.InReplyTo = minfo.get('InReplyTo')
        self.TransactionListIndex = minfo.get('TransactionListIndex', 0)
        self.TransactionIDs = minfo.get('TransactionIDs', [])

        self.IsSystemMessage = True
        self.IsForward = False
        self.IsReliable = True

    def dump(self):
        result = super(UncommittedListReplyMessage, self).dump()
        result['TransactionListIndex'] = self.TransactionListIndex

        result['TransactionIDs'] = []
        for blkid in self.TransactionIDs:
            result['TransactionIDs'].append(blkid)

        result['InReplyTo'] = self.InReplyTo
        return result


class BlockRequestMessage(message.Message):
    MessageType = "/journal.messages.JournalTransfer/BlockRequest"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(BlockRequestMessage, self).__init__(minfo)
        self.BlockID = minfo.get('BlockID')

        self.IsSystemMessage = True
        self.IsForward = False
        self.IsReliable = True

    def dump(self):
        result = super(BlockRequestMessage, self).dump()
        result['BlockID'] = self.BlockID

        return result


def _blockrequesthandler(msg, journal):
    logger.debug('processing incoming block request for journal transfer')
    gossip = journal.gossip
    if journal.Initializing:
        src = gossip.NodeMap.get(msg.OriginatorID, msg.OriginatorID[:8])
        logger.warn(
            'received block transfer request from %s prior to completing '
            'initialization',
            src)
        gossip.send_message(TransferFailedMessage(), msg.OriginatorID)
        return

    reply = BlockReplyMessage()
    reply.InReplyTo = msg.Identifier
    if msg.BlockID in journal.BlockStore:
        blk = journal.BlockStore[msg.BlockID]
        bmsg = blk.build_message()
        reply.TransactionBlockMessage = bmsg.dump()
    else:
        logger.warn('request for unknown block, %s', msg.BlockID[:8])
        gossip.send_message(TransferFailedMessage(), msg.OriginatorID)
        return

    gossip.send_message(reply, msg.OriginatorID)


class BlockReplyMessage(message.Message):
    MessageType = "/journal.messages.JournalTransfer/BlockReply"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(BlockReplyMessage, self).__init__(minfo)

        # TransactionBlockMessage is the encapsulated, transaction block
        # type specific message that lets us handle multiple transaction
        # block types
        self.TransactionBlockMessage = minfo.get('TransactionBlockMessage', {})
        self.InReplyTo = minfo.get('InReplyTo')

        self.IsSystemMessage = True
        self.IsForward = False
        self.IsReliable = True

    def dump(self):
        result = super(BlockReplyMessage, self).dump()
        result['TransactionBlockMessage'] = self.TransactionBlockMessage
        result['InReplyTo'] = self.InReplyTo

        return result


class TransactionRequestMessage(message.Message):
    MessageType = "/journal.messages.JournalTransfer/TransactionRequest"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(TransactionRequestMessage, self).__init__(minfo)
        self.TransactionID = minfo[
            'TransactionID'] if 'TransactionID' in minfo else []

        self.IsSystemMessage = True
        self.IsForward = False
        self.IsReliable = True

    def dump(self):
        result = super(TransactionRequestMessage, self).dump()
        result['TransactionID'] = self.TransactionID

        return result


def _txnrequesthandler(msg, journal):
    logger.debug(
        'processing incoming transaction request for journal transfer')
    gossip = journal.gossip
    if journal.Initializing:
        src = gossip.NodeMap.get(msg.OriginatorID, msg.OriginatorID[:8])
        logger.warn(
            'received transaction transfer request from %s prior to '
            'completing initialization',
            src)
        gossip.send_message(TransferFailedMessage(), msg.OriginatorID)
        return

    reply = TransactionReplyMessage()
    reply.InReplyTo = msg.Identifier
    if msg.TransactionID in journal.TransactionStore:
        txn = journal.TransactionStore[msg.TransactionID]
        tmsg = txn.build_message()
        reply.TransactionMessage = tmsg.dump()
    else:
        logger.warn('request for unknown transaction, %s',
                    msg.TransactionID[:8])
        gossip.send_message(TransferFailedMessage(), msg.OriginatorID)
        return

    gossip.send_message(reply, msg.OriginatorID)


class TransactionReplyMessage(message.Message):
    MessageType = "/journal.messages.JournalTransfer/TransactionReply"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(TransactionReplyMessage, self).__init__(minfo)

        # TransactionMessage is the encapsulated, transaction-type specific
        # message that lets us handle multiple transaction types
        self.TransactionMessage = minfo.get('TransactionMessage', {})
        self.InReplyTo = minfo.get('InReplyTo')

        self.IsSystemMessage = True
        self.IsForward = False
        self.IsReliable = True

    def dump(self):
        result = super(TransactionReplyMessage, self).dump()
        result['TransactionMessage'] = self.TransactionMessage
        result['InReplyTo'] = self.InReplyTo

        return result


class TransferFailedMessage(message.Message):
    MessageType = "/journal.messages.JournalTransfer/TransferFailed"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(TransferFailedMessage, self).__init__(minfo)

        self.IsSystemMessage = True
        self.IsForward = False
        self.IsReliable = True

    def dump(self):
        result = super(TransferFailedMessage, self).dump()
        return result
