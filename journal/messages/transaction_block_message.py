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
    """Registers the transaction block message handlers with the
    journal.

    Args:
        journal (Journal): The journal to register the message
            handlers against.
    """
    journal.register_message_handler(TransactionBlockMessage,
                                     transaction_block_message_handler)
    journal.register_message_handler(BlockRequestMessage, _blkrequesthandler)


class TransactionBlockMessage(message.Message):
    """Transaction block messages represent the message format
    for exchanging transaction blocks.

    Attributes:
        MessageType (str): The class name of the message.
        IsSystemMessage (bool): Whether or not this message is
            a system message.
        IsForward (bool): Whether or not this message is forwarded.
        IsReliable (bool): Whether or not this message should
            use reliable delivery.
        TransactionBlock (TransactionBlock): The block associated
            with the message.
    """
    MessageType = "/" + __name__ + "/TransactionBlock"

    def __init__(self, minfo={}):
        """Constructor for the TransactionBlockMessage class.

        Args:
            minfo (dict): A dict of initial values for the new
                TransactionBlockMessage.
        """
        super(TransactionBlockMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = False
        self.IsReliable = True
        self.TransactionBlock = None

    def dump(self):
        """Returns a dict containing information about the
        transaction block message.

        Returns:
            dict: A dict containing information about the
                transaction block message.
        """
        result = super(TransactionBlockMessage, self).dump()
        result['TransactionBlock'] = self.TransactionBlock.dump()

        return result


def transaction_block_message_handler(msg, journal):
    """The function called when the node receives a transaction
    block message.

    Args:
        msg (Message): The transaction block message.
        journal (Journal): The journal.
    """
    # if we already have this block, then there is no reason to
    # send it on, be conservative about forwarding messages
    if not msg.TransactionBlock:
        logger.warn('transaction block message missing transaction block; %s',
                    msg.MessageType)
        return

    if msg.TransactionBlock.Identifier in journal.BlockStore:
        return

    journal.commit_transaction_block(msg.TransactionBlock)
    journal.forward_message(msg, exceptions=[msg.SenderID], initialize=False)


class BlockRequestMessage(message.Message):
    """Represents the message format for block requests.

    Attributes:
        MessageType (str): The class name of the message.
        IsSystemMessage (bool): Whether or not this message is
            a system message.
        IsForward (bool): Whether or not this message is forwarded.
        IsReliable (bool): Whether or not this message should
            use reliable delivery.
        BlockID (str): The id of the requested block.
    """
    MessageType = "/" + __name__ + "/BlockRequest"

    def __init__(self, minfo={}):
        """Constructor for the BlockRequestMessage class.

        Args:
            minfo (dict): A dict of initial values for the
                new BlockRequestMessage.
        """
        super(BlockRequestMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = False
        self.IsReliable = True

        self.BlockID = minfo.get('BlockID')

    def dump(self):
        """Returns a dict containing information about the
        BlockRequestMessage.

        Returns:
            dict: A dict containing information about the
                BlockRequestMessage.
        """
        result = super(BlockRequestMessage, self).dump()
        result['BlockID'] = self.BlockID

        return result


def _blkrequesthandler(msg, journal):
    blk = journal.BlockStore.get(msg.BlockID)
    if blk:
        reply = blk.build_message()
        journal.forward_message(reply)
        return

    journal.request_missing_block(msg.BlockID,
                                  exceptions=[msg.SenderID],
                                  request=msg)
