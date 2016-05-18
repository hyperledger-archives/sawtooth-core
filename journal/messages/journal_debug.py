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
import time

from gossip import message

logger = logging.getLogger(__name__)


def register_message_handlers(journal):
    """Registers the message handlers that every journal should
    support.

    Args:
        journal (journal_core.Journal): The journal to register the message
            handlers against.
    """
    journal.register_message_handler(DumpJournalBlocksMessage,
                                     _dumpjournalblockshandler)
    journal.register_message_handler(DumpJournalValueMessage,
                                     _dumpjournalvaluehandler)


def _dumpjournalblockshandler(msg, journal):
    logger.info('dumping block list for %s', journal.LocalNode)

    identifier = "{0}, {1:0.2f}, {2}".format(journal.LocalNode, time.time(),
                                             msg.Identifier[:8])

    blockids = journal.committed_block_ids(msg.Count)
    for blkid in blockids:
        block = journal.BlockStore[blkid]
        logger.info('block, %s, %s', identifier, str(block))


class DumpJournalBlocksMessage(message.Message):
    """Dump journal blocks messages represent the message format
    for exchanging dump journal blocks messages.

    Attributes:
        DumpJournalBlocksMessage.MessageType (str): The class name of the
            message.
        IsSystemMessage (bool): Whether or not this message is
            a system message.
        IsForward (bool): Whether or not this message is forwarded.
        IsReliable (bool): Whether or not this message should
            use reliable delivery.
        Count (int): The number of journal blocks to dump.
    """
    MessageType = "/journal.messages.JournalDebug/DumpJournalBlocks"

    def __init__(self, minfo={}):
        """Constructor for DumpJournalBlocksMessage class.

        Args:
            minfo (dict): A dict containing intialization values
                for a DumpJournalBlocksMessage.
        """
        super(DumpJournalBlocksMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = True
        self.IsReliable = True

        self.Count = minfo.get("Count", 0)

    def dump(self):
        """Returns a dict containing information about the
        DumpJournalBlocksMessage.

        Returns:
            dict: A dict containing information about the dump
                journal blocks message.
        """
        result = super(DumpJournalBlocksMessage, self).dump()
        result['Count'] = self.Count

        return result


def _dumpjournalvaluehandler(msg, journal):
    key = msg.Name
    tname = msg.TransactionType

    msgid = msg.Identifier[:8]
    localnode = journal.LocalNode
    remotenode = journal.NodeMap.get(msg.OriginatorID, msg.OriginatorID[:8])

    logger.debug("received journal lookup for key <%s> from %s", key,
                 remotenode)

    cmn = "{0}, {1}, {2}, {3}".format(localnode, msgid, key, tname)

    # if the current journal contains incomplete blocks then we won't have any
    # global store
    if not journal.GlobalStore:
        logger.info("keylookup, %s, incomplete, 0", cmn)
    elif tname not in journal.GlobalStore.TransactionStores:
        logger.info("keylookup, %s, unknown type", cmn)
    elif key not in journal.GlobalStore.TransactionStores[tname]:
        logger.info("keylookup, %s, no value, 0", cmn)
    else:
        logger.info("keylookup, %s, known, %s", cmn,
                    str(journal.GlobalStore.TransactionStores[tname][key]))


class DumpJournalValueMessage(message.Message):
    """Represents the message format for exchanging dump journal
    value messages.

    Attributes:
        DumpJournalValueMessage.MessageType (str): The class name of the
            message.
        IsSystemMessage (bool): Whether or not this message is
            a system message.
        IsForward (bool): Whether or not this message is forwarded.
        IsReliable (bool): Whether or not this message should
            use reliable delivery.
        TransactionType (type): The type of transaction.
        Name (str): The name of the transaction.
    """
    MessageType = "/journal.messages.JournalDebug/DumpJournalValue"

    def __init__(self, minfo={}):
        """Constructor for the DumpJournalValueMessage class.

        Args:
            minfo (dict): A dict containing initial values for
                the new DumpJournalValueMessage.
        """
        super(DumpJournalValueMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = True
        self.IsReliable = True

        self.TransactionType = minfo.get('TransactionType')
        self.Name = minfo.get('Name')

    def dump(self):
        """Returns a dict containing information about the
        DumpJournalValueMessage.

        Returns:
            dict: A dict containing information about the dump
                journal value message.
        """
        result = super(DumpJournalValueMessage, self).dump()

        result['TransactionType'] = self.TransactionType
        result['Name'] = self.Name

        return result
