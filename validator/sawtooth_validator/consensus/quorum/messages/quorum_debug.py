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

LOGGER = logging.getLogger(__name__)


def register_message_handlers(journal):
    """Register the message handlers that every journal should support.

    Args:
        journal (QuorumJournal): The journal to register the handlers
            against.
    """
    journal.dispatcher.register_message_handler(
        DumpQuorumMessage, _dumpquorumhandler)


def _dumpquorumhandler(msg, journal):
    LOGGER.info('dumping quorum for %s', journal.LocalNode)

    identifier = "{0}, {1:0.2f}, {2}".format(journal.LocalNode, time.time(),
                                             msg.Identifier[:8])

    for node in journal.VotingQuorum.itervalues():
        LOGGER.info('quorum, %s, %s', identifier, node)


class DumpQuorumMessage(message.Message):
    """Represents the structure of a message to dump quorum information.

    Attributes:
        DumpQuorumMessage.MessageType (str): The class name of the message.
        IsSystemMessage (bool): Whether or not this message is
            a system message.
        IsForward (bool): Whether or not this message is forwarded.
        IsReliable (bool): Whether or not this message should
            use reliable delivery.
    """
    MessageType = \
        "/sawtooth_validator.consensus.quorum.messages.QuorumDebug/" \
        "Quorum/DumpQuorum"

    def __init__(self, minfo=None):
        """Constructor for DumpQuorumMessage class.

        Args:
            minfo (dict): A dict containing initial values for the
                new DumpQuorumMessage.
        """
        if minfo is None:
            minfo = {}
        super(DumpQuorumMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = True
        self.IsReliable = True

    def dump(self):
        """Returns a dict with information about the dump quorum message.

        Returns:
            dict: A dict with information about the dump quorum
                message.
        """
        result = super(DumpQuorumMessage, self).dump()
        return result
