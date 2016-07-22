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
import uuid

from twisted.internet import reactor

from gossip import message, node

logger = logging.getLogger(__name__)

TimeToWaitForTopologyProbe = 2.0
CurrentTopologyRequestID = None
CurrentTopologyResponseMap = {}


def initiate_topology_probe(gossiper, callback):
    """Broadcasts a topology message and establishes a callback timer
    to handle the responses.

    Args:
        gossiper (Node): The local node.
        callback (function): The callback argument to the
            update_peers_from_topology_probe method.
    """
    global CurrentTopologyRequestID, CurrentTopologyResponseMap

    # if there is a request being processed, then dont initiate another
    if CurrentTopologyRequestID:
        return

    request = TopologyRequestMessage()
    CurrentTopologyRequestID = request.Identifier

    gossiper.broadcast_message(request)
    reactor.callLater(TimeToWaitForTopologyProbe,
                      update_peers_from_topology_probe,
                      gossiper,
                      callback)


def update_peers_from_topology_probe(gossiper, callback):
    """Calls the passed in callback and resets global variables.

    Args:
        gossiper (Node): The local node.
        callback (function): The function which should be called.
    """
    global CurrentTopologyRequestID, CurrentTopologyResponseMap

    if callback:
        callback(gossiper, CurrentTopologyResponseMap)

    CurrentTopologyRequestID = None
    CurrentTopologyResponseMap = {}


def register_message_handlers(gossiper):
    """Registers the topology-related message handlers for a node.

    Args:
        gossiper (Node): The node to register message handlers on.
    """
    gossiper.register_message_handler(TopologyRequestMessage,
                                      topology_request_handler)
    gossiper.register_message_handler(TopologyReplyMessage,
                                      topology_reply_handler)


class TopologyRequestMessage(message.Message):
    """Topology request messages are sent to peer nodes to query the
    connectivity of the peer nodes.

    Attributes:
        TopologyRequestMessage.MessageType (str): The class name of the
            message.
        IsSystemMessage (bool): Whether or not this is a system message.
            System messages have special delivery priority rules.
        IsForward (bool): Whether the message should be automatically
            forwarded.
        IsReliable (bool): Whether reliable delivery is required.
    """
    MessageType = "/gossip.messages.TopologyMessage/ToplogyRequest"

    def __init__(self, minfo={}):
        """Constructor for the TopologyRequestMessage class.

        Args:
            minfo (dict): Dictionary of values for message fields.
        """
        super(TopologyRequestMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = True
        self.IsReliable = True

        self.TimeToLive = 2

    def dump(self):
        """Dumps a dict containing object attributes.

        Returns:
            dict: A mapping of object attribute names to values.
        """
        result = super(TopologyRequestMessage, self).dump()
        return result


def topology_request_handler(msg, gossiper):
    """Handles incoming topology request messages.

    Args:
        msg (message.Message): The incoming topology message.
        gossiper (Node): The local node.
    """
    logger.debug('responding to probe %s from node %s', msg.Identifier[:8],
                 msg.OriginatorID[:8])

    if msg.OriginatorID == gossiper.LocalNode.Identifier:
        logger.debug('node %s received its own topology request, ignore',
                     gossiper.LocalNode.Identifier[:8])
        return

    reply = TopologyReplyMessage()
    reply.NetHost = gossiper.LocalNode.endpoint_host
    reply.NetPort = gossiper.LocalNode.endpoint_port
    reply.NodeIdentifier = gossiper.LocalNode.Identifier
    reply.Name = gossiper.LocalNode.Name
    reply.InReplyTo = msg.Identifier

    for peer in gossiper.peer_list():
        if peer.Enabled:
            reply.Peers.append((peer.Identifier, peer.NetAddress))

    gossiper.broadcast_message(reply)


class TopologyReplyMessage(message.Message):
    """Topology reply messages are sent in response to topology
    request messages.

    Attributes:
        TopologyReplyMessage.MessageType (str): The class name of the message.
        IsSystemMessage (bool): Whether or not this is a system message.
            System messages have special delivery priority rules.
        IsForward (bool): Whether the message should be automatically
            forwarded.
        IsReliable (bool): Whether reliable delivery is required.
        NetHost (str): Hostname or IP address identifying the node.
        NetPort (int): The remote port number to connect to.
        NodeIdentifier (str): The identifier of the remote node.
        Name (str): The name of the originator.
        Peers (list): A list of peers in the topology response.
        InReplyTo (str): The identifier of the associated topology
            request message.
    """
    MessageType = "/gossip.messages.TopologyMessage/TopologyReply"

    def __init__(self, minfo={}):
        super(TopologyReplyMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = True
        self.IsReliable = True

        self.NetHost = minfo.get('Host', "127.0.0.1")
        self.NetPort = minfo.get('Port', 0)
        self.NodeIdentifier = minfo.get('NodeIdentifier', '')
        self.Name = minfo.get('Name', self.OriginatorID[:8])

        self.Peers = minfo.get('Peers', [])
        self.InReplyTo = minfo.get('InReplyTo', str(uuid.UUID(int=0)))

    @property
    def NetAddress(self):
        """Returns the host and port of the topology reply message.

        Returns:
            ordered pair: (host, port).
        """
        return (self.NetHost, self.NetPort)

    def dump(self):
        """Dumps a dict containing object attributes.

        Returns:
            A mapping of object attribute names to values.
        """
        result = super(TopologyReplyMessage, self).dump()

        result['Host'] = self.NetHost
        result['Port'] = self.NetPort
        result['NodeIdentifier'] = self.NodeIdentifier
        result['Name'] = self.Name

        result['Peers'] = self.Peers
        result['InReplyTo'] = self.InReplyTo

        return result


def topology_reply_handler(msg, gossiper):
    """Handles incoming topology reply messages.

    Args:
        msg (message.Message): The incoming topology message.
        gossiper (Node): The local node.
    """
    logger.debug('received reply to probe %s from node %s', msg.InReplyTo[:8],
                 msg.Name)

    global CurrentTopologyRequestID, CurrentTopologyResponseMap

    # Because of the multiple paths through the overlay network, the topology
    # request can arrive after replies have started to arrive so we initialize
    # the current set of requests with the replies that come in
    if not CurrentTopologyRequestID:
        CurrentTopologyRequestID = msg.InReplyTo
        reactor.callLater(TimeToWaitForTopologyProbe,
                          update_peers_from_topology_probe, gossiper, None)

    if msg.InReplyTo != CurrentTopologyRequestID:
        logger.debug('reply for a different probe, %s instead of %s',
                     msg.InReplyTo[:8], CurrentTopologyRequestID[:8])
        return

    peer = node.Node(address=msg.NetAddress,
                     identifier=msg.NodeIdentifier,
                     name=msg.Name)
    CurrentTopologyResponseMap[peer] = msg.Peers
