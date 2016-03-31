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
"""
This module implements a Message-derived class for handling random walk
messages. Random walk messages support extending the connectivity of the
gossip network via the random walk topology.
"""

import logging
import random

from gossip.messages.connect_message import send_connection_request
from gossip import message, node

logger = logging.getLogger(__name__)

MaxNumberOfConnections = 11


def send_random_walk_message(gossiper):
    """Sends a random walk message to a random peer.

    Args:
        gossiper (Node): The local node.
    """
    msg = RandomWalkMessage()
    msg.NetHost = gossiper.LocalNode.NetHost
    msg.NetPort = gossiper.LocalNode.NetPort
    msg.NodeIdentifier = gossiper.LocalNode.Identifier
    msg.Name = gossiper.LocalNode.Name

    peers = gossiper.peer_id_list()
    if len(peers) > 0:
        peerid = random.choice(peers)
        gossiper.send_message(msg, peerid)


def register_message_handlers(gossiper):
    """Registers the random-walk related message handlers for a node.

    Args:
        gossiper (Node): The node to register message handlers on.
    """
    gossiper.register_message_handler(RandomWalkMessage, random_walk_handler)


class RandomWalkMessage(message.Message):
    """Random walk messages are sent to a random peer to extend the
    connectivity of the network.

    Attributes:
        MessageType (str): The class name of the message.
        NetHost (str): Hostname or IP address identifying the node.
        NetPort (int): The remote port number to connect to.
        NodeIdentifier (str): The identifier of the originating node.
        Name (str): The name of the connection.
        IsSystemMessage (bool): Whether or not this is a system message.
            System messages have special delivery priority rules.
        IsForward (bool): Whether the message should be automatically
            forwarded.
        IsReliable (bool): Whether reliable delivery is required.
        TimeToLive (int): How many 'steps' there are in the random walk.
            When a random walk message is received, the TimeToLive value
            is decremented and the message is retransmitted from the
            receving node. This continues until TimeToLive reaches zero.
    """
    MessageType = "/" + __name__ + "/Topology/RandomWalk"

    def __init__(self, minfo={}):
        """Constructor for the RandomWalkMessage class.

        Args:
            minfo (dict): Dictionary of values for message fields.
        """
        super(RandomWalkMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = False
        self.IsReliable = True

        self.NetHost = minfo.get('Host', "127.0.0.1")
        self.NetPort = minfo.get('Port', 0)
        self.NodeIdentifier = minfo.get('NodeIdentifier', '')
        self.Name = minfo.get('Name', self.NodeIdentifier[:8])

        self.TimeToLive = 8

    @property
    def NetAddress(self):
        """Returns the host and port of the connection request message.

        Returns:
            ordered pair: (host, port).
        """
        return (self.NetHost, self.NetPort)

    def dump(self):
        """Dumps a dict containing object attributes.

        Returns:
            dict: A mapping of object attribute names to values.
        """
        result = super(RandomWalkMessage, self).dump()

        result['Host'] = self.NetHost
        result['Port'] = self.NetPort
        result['NodeIdentifier'] = self.NodeIdentifier
        result['Name'] = self.Name

        return result


def random_connections():
    """Determines how many random connections the node should attempt
    to connect to.

    Returns:
        int: The number of random connections to attempt.
    """
    count = 0
    value = random.randint(1, pow(2, MaxNumberOfConnections))
    while value > 0:
        value >>= 1
        count += 1

    return count


def random_walk_handler(msg, gossiper):
    """Function called when the gossiper receives a RandomWalkMessage
    from one of its peers.

    Args:
        msg (Message): The received random walk message.
        gossiper (Node): The local node.
    """

    if msg.OriginatorID == gossiper.LocalNode.Identifier:
        logger.debug('node %s received its own random walk request, ignore',
                     gossiper.LocalNode)
        return

    logger.debug('random walk request %s from %s with ttl %d',
                 msg.Identifier[:8], msg.Name, msg.TimeToLive)

    peers = gossiper.peer_id_list()

    # if the source is not already one of our peers, then check to see if we
    # should add it to our list
    if msg.OriginatorID not in peers:
        if len(peers) < random_connections():
            logger.debug(
                'add connection to node %s based on random walk request %s',
                msg.Name, msg.Identifier[:8])
            onode = node.Node(address=msg.NetAddress,
                              identifier=msg.NodeIdentifier,
                              name=msg.Name)
            onode.Enabled = True

            send_connection_request(gossiper, onode)
            return

    # if there is still life in the message, then see if we should forward it
    # to another node

    if msg.TimeToLive > 0:
        # see if we can find a peer other than the peer who forwarded the
        # message to us, if not then we'll just drop the request

        try:
            peers.remove(msg.SenderID)
            peers.remove(msg.OriginatorID)
        except:
            pass

        if len(peers) > 0:
            peerid = random.choice(peers)
            gossiper.send_message(msg, peerid, initialize=False)
