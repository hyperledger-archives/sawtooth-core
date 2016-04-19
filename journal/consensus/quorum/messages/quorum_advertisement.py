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
import random

from gossip import message, node

logger = logging.getLogger(__name__)


def send_quorum_advertisement_message(journal):
    """Sends a quorum advertisement message to peers.

    Args:
        journal (QuorumJournal): The journal on which the quorum will
            take place.
    """
    logger.info('sending quorum advertisement')

    msg = QuorumAdvertisementMessage.create_from_node(journal.LocalNode)

    peers = journal.peer_id_list()
    if len(peers) > 0:
        peerid = random.choice(peers)
        journal.send_message(msg, peerid)


def register_message_handlers(journal):
    """Registers the message handlers which are triggered when
    quorum advertisement messages arrive.

    Args:
        journal (QuorumJournal): The journal to register the message
            handlers against.
    """
    journal.register_message_handler(QuorumAdvertisementMessage,
                                     quorum_advertisement_handler)


class QuorumAdvertisementMessage(message.Message):
    """Quorum advertisement messages represent the message format
    for exchanging quorum advertisements.

    Attributes:
        QuorumAdvertisementMessage.MessageType (str): The class name of the
            message.
        IsSystemMessage (bool): Whether or not this message is
            a system message.
        IsForward (bool): Whether or not this message is forwarded.
        IsReliable (bool): Whether or not this message should
            use reliable delivery.
        Identifier (str): The identifier of the node.
        NetHost (str): Hostname or IP address identifying the node.
        NetPort (int): The remote port number to connect to.
        Name (str): The name of the originator.
        TimeToLive (int): The number of hops for the message to
            live.
    """
    MessageType = "/journal.consensus.quorum.messages.QuorumAdvertisement" \
        "/Quorum/Advertisement"

    @staticmethod
    def create_from_node(nd):
        """Creates a QuorumAdvertisementMessage from a node.

        Args:
            nd (Node): The node to create the message from.

        Returns:
            QuorumAdvertisementMessage: The new message.
        """
        msg = QuorumAdvertisementMessage()
        msg.Identifier = nd.Identifier
        msg.NetHost = nd.NetHost
        msg.NetPort = nd.NetPort
        msg.Name = nd.Name
        return msg

    def __init__(self, minfo={}):
        """Constructor for the QuorumAdvertisementMessage class.

        Args:
            minfo (dict): A dict containing initialization values
                for the new QuorumAdvertisementMessage.
        """
        super(QuorumAdvertisementMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = False
        self.IsReliable = True

        self.Identifier = minfo.get('Identifier', '')
        self.NetHost = minfo.get('Host', "127.0.0.1")
        self.NetPort = minfo.get('Port', 0)
        self.Name = minfo.get('Name', self.OriginatorID[:8])

        self.TimeToLive = 8

    @property
    def NetAddress(self):
        """Returns the host and port of the quorum advertisement
        message.

        Returns:
            ordered pair: (host, port).
        """
        return (self.NetHost, self.NetPort)

    def dump(self):
        """Dumps a dict containing object attributes.

        Returns:
            dict: A mapping of object attribute names to values.
        """
        result = super(QuorumAdvertisementMessage, self).dump()

        result['Host'] = self.NetHost
        result['Port'] = self.NetPort
        result['Name'] = self.Name
        result['Identifier'] = self.Identifier

        return result


def quorum_advertisement_handler(msg, journal):
    """Function called when the journal receives a
    QuorumAdvertisementMessage from one of its peers.

    Args:
        msg (QuorumAdvertisementMessage): The received quorum
            advertisement message.
        journal (QuorumJournal): The journal which received the
            message.
    """
    logger.info("quorum advertisement received from %s", msg.OriginatorID[:8])

    if msg.OriginatorID == journal.LocalNode.Identifier:
        logger.debug(
            'node %s received its own quorum advertisement request, ignore',
            journal.LocalNode)
        return

    onode = node.Node(address=msg.NetAddress,
                      identifier=msg.Identifier,
                      name=msg.Name)
    journal.add_quorum_node(onode)

    # if there is still life in the message, then see if we should forward it
    # to another node

    if msg.TimeToLive > 0:
        # see if we can find a peer other than the peer who forwarded the
        # message to us, if not then we'll just drop the request

        try:
            peers = journal.peer_id_list()
            peers.remove(msg.SenderID)
            peers.remove(msg.OriginatorID)
        except:
            pass

        if len(peers) > 0:
            peerid = random.choice(peers)
            journal.send_message(msg, peerid, initialize=False)
