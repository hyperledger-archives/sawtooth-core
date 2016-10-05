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
This module defines the core gossip class for communication between nodes.
"""

import errno
import logging
import socket
import time

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

from gossip import event_handler
from gossip import message
from gossip.message_dispatcher import MessageDispatcher
from gossip import stats
from gossip.messages import connect_message
from gossip.messages import gossip_debug
from gossip.messages import random_walk_message
from gossip.messages import shutdown_message
from gossip.messages import topology_message
from gossip.message_queue import MessageQueue

logger = logging.getLogger(__name__)


class GossipException(Exception):
    """An exception thrown when an error is encountered during
    Gossip initialization."""

    def __init__(self, msg):
        super(GossipException, self).__init__(msg)


class Gossip(object, DatagramProtocol):
    """Defines the protocol for gossip communication between nodes.

    Attributes:
        ExpireMessageTime (int): Time in seconds to hold message to test
            for duplicates.
        MaximumPacketSize (int): The maximum size of a packet.
        CleanupInterval (float): The number of seconds between cleanups.
        KeepAliveInterval (float): The number of seconds between keep
            alive messages.
        MinimumRetries (int): The minimum number of retries on message
            retransmission.
        RetryInterval (float): The time between retries, in seconds.
        LocalNode (Node): The local node sending and receiving messages.
        NodeMap (dict): A map of peer nodes the local node is communicating
            with.
        PendingAckMap (dict): A map of incoming messages that require
            acknowledgement.
        MessageHandledMap (dict): A map of handled messages where keys are
            message identifiers and values are message expiration times.
        SequenceNumber (int): The next sequence number to be used for
            messages from the local node.
        NextCleanup (float): The time of the next cleanup event.
        NextKeepAlive (float): The time of the next keep alive event.
        onNodeDisconnect (EventHandler): An EventHandler for functions
            to call when a node becomes disconnected.
        IncomingMessageQueue (MessageQueue): The queue of incoming messages.
        ProcessIncomingMessages (bool): Whether or not to process incoming
            messages.
        Listener (Reactor.listenUDP): The UDP listener.
    """

    # time in seconds to hold message to test for duplicates
    ExpireMessageTime = 300
    MaximumPacketSize = 8192 * 6 - 128
    CleanupInterval = 1.00
    KeepAliveInterval = 10.0

    def __init__(self,
                 node,
                 minimum_retries=None,
                 retry_interval=None,
                 stat_domains=None):
        """Constructor for the Gossip class.

        Args:
            node (Node): The local node.
            MinimumRetries (int): The minimum number of retries on message
                transmission.
            RetryInterval (float): The time between retries, in seconds.
        """
        super(Gossip, self).__init__()

        self.blacklist = []

        if minimum_retries is not None:
            self.MinimumRetries = minimum_retries

        if retry_interval is not None:
            self.RetryInterval = retry_interval

        self.LocalNode = node
        self.NodeMap = {}

        self.PendingAckMap = {}
        self.MessageHandledMap = {}

        self.SequenceNumber = 0
        self.NextCleanup = time.time() + self.CleanupInterval
        self.NextKeepAlive = time.time() + self.KeepAliveInterval

        self._init_gossip_stats(stat_domains)

        self.dispatcher = MessageDispatcher(self)

        connect_message.register_message_handlers(self)
        gossip_debug.register_message_handlers(self)
        random_walk_message.register_message_handlers(self)
        shutdown_message.register_message_handlers(self)
        topology_message.register_message_handlers(self)

        # setup connectivity events
        self.onNodeDisconnect = event_handler.EventHandler('onNodeDisconnect')

        # setup the timer events
        self.dispatcher.on_heartbeat += self._timer_transmit
        self.dispatcher.on_heartbeat += self._timer_cleanup
        self.dispatcher.on_heartbeat += self._keep_alive

        self.IncomingMessageQueue = MessageQueue()
        try:
            self.ProcessIncomingMessages = True
            self.Listener = reactor.listenUDP(self.LocalNode.NetPort,
                                              self)
            reactor.callInThread(self._dispatcher)
        except Exception as e:
            logger.critical(
                "failed to connect local socket, server shutting down",
                exc_info=True)
            raise GossipException(
                "Failed to connect local "
                "socket, server shutting down")

    def _init_gossip_stats(self, stat_domains):
        self.PacketStats = stats.Stats(self.LocalNode.Name, 'packet')
        self.PacketStats.add_metric(stats.Average('BytesSent'))
        self.PacketStats.add_metric(stats.Average('BytesReceived'))
        self.PacketStats.add_metric(stats.Counter('MessagesAcked'))
        self.PacketStats.add_metric(stats.Counter('DuplicatePackets'))
        self.PacketStats.add_metric(stats.Counter('DroppedPackets'))
        self.PacketStats.add_metric(stats.Counter('AcksReceived'))
        self.PacketStats.add_metric(stats.Counter('MessagesHandled'))
        self.PacketStats.add_metric(stats.Sample(
            'UnackedPacketCount', lambda: len(self.PendingAckMap)))

        self.MessageStats = stats.Stats(self.LocalNode.Name, 'message')
        self.MessageStats.add_metric(stats.MapCounter('MessageType'))
        if stat_domains is not None:
            stat_domains['packet'] = self.PacketStats
            stat_domains['message'] = self.MessageStats

    def peer_list(self, allflag=False, exceptions=None):
        """Returns a list of peer nodes.

        Args:
            allflag (bool): Whether to include all peers.
            exceptions (list): A list of node identifiers to exclude
                from the peer list.

        Returns:
            list: A list of Nodes considered peers.
        """
        if exceptions is None:
            exceptions = []
        peers = []
        for peer in self.NodeMap.itervalues():
            if peer.is_peer or allflag:
                if peer.Identifier not in exceptions:
                    peers.append(peer)
        return peers

    def peer_id_list(self, allflag=False, exceptions=None):
        """Returns a list of peer node identifiers.

        Args:
            allflag (bool): Whether to include all peers.
            exceptions (list): A list of node identifiers to exclude
                from the peer list.

        Returns:
            list: A list of Node identifiers considered peers.

        """

        if exceptions is None:
            exceptions = []
        return [p.Identifier for p in self.peer_list(allflag, exceptions)]

    def next_sequence_number(self):
        """Increments the sequence number and returns it.

        Returns:
            int: The current sequence number for messages.
        """
        self.SequenceNumber += 1
        return self.SequenceNumber

    # --------------------------------- ###
    # DatagramProtocol Overrides        ###
    # --------------------------------- ###

    def startProtocol(self):
        """Starts the gossip protocol."""
        endpoint = self.transport.getHost()
        logger.info('listening on %s', endpoint)
        self.LocalNode.NetPort = endpoint.port
        self.transport.maxPacketSize = self.MaximumPacketSize

    def stopProtocol(self):
        """Stops the gossip protocol."""
        pass

    def datagramReceived(self, data, address):
        """Handles a received datagram.

        Find a handler for the message if one exists, and call it if
        the message has not already been handled. Also forward to peers
        as appropriate.

        Args:
            data (str): the text of the message
            address (str): host:port network address of the peer
        """

        if not self.ProcessIncomingMessages:
            return

        self.PacketStats.BytesReceived.add_value(len(data))

        # unpack the header
        try:
            packet = message.Packet()
            packet.unpack(data)
        except:
            logger.exception('failed to unpack message')
            return

        # Grab peer information if it is available, unless this is a system
        # message we don't process any further without a known peer
        srcpeer = self.NodeMap.get(packet.SenderID)
        if srcpeer:
            srcpeer.reset_ticks()

        # Handle incoming acknowledgements first, there is no data associated
        # with an ack
        if packet.IsAcknowledgement:
            if srcpeer:
                self._handle_ack(packet)
            return

        # first thing to do with the message is to send an ACK, all
        # retransmissions will be handled by the sending node, if the
        # IsReliable flag is set then this is not a system message & we know
        # that the peer exists
        if packet.IsReliable:
            if srcpeer:
                self._send_ack(packet, srcpeer)

        # now unpack the rest of the message
        try:
            minfo = message.unpack_message_data(packet.Data)
        except:
            logger.exception('unable to decode message with length %d',
                             len(data))
            return

        # if we don't have a handler, thats ok we just dont do anything
        # with the message, note the missing handler in the logs however
        typename = minfo['__TYPE__']
        self.MessageStats.MessageType.increment(typename)

        if not self.dispatcher.has_message_handler(typename):
            logger.info('no handler found for message type %s from %s',
                        minfo['__TYPE__'], srcpeer or packet.SenderID[:8])
            return

        try:
            msg = self.dispatcher.unpack_message(typename, minfo)
            msg.TimeToLive = packet.TimeToLive - 1
            msg.SenderID = packet.SenderID
        except:
            logger.exception(
                'unable to deserialize message of type %s from %s',
                typename,
                packet.SenderID[:8])
            return

        # if we have seen this message before then just ignore it
        if msg.Identifier in self.MessageHandledMap:
            logger.debug('duplicate message %s received from %s', msg,
                         packet.SenderID[:8])
            self.PacketStats.DuplicatePackets.increment()

            # if we have received a particular message from a node then we dont
            # need to send another copy back to the node, just remove it from
            # the queue
            try:
                if srcpeer:
                    srcpeer.dequeue_message(msg)
            except:
                pass

            return

        # verify the signature, this is a no-op for the gossiper, but
        # subclasses might override the function, system messages need not have
        # verified signatures
        if not msg.IsSystemMessage and not msg.verify_signature():
            logger.warn('unable to verify message %s received from %s',
                        msg.Identifier[:8], msg.OriginatorID[:8])
            return

        # Handle system messages,these do not require the existence of
        # a peer. If the packet is marked as a system message but the message
        # type does not, then something bad is happening.
        self.PacketStats.MessagesHandled.increment()

        if (srcpeer and srcpeer.is_peer) or msg.IsSystemMessage:
            self._handle_message(msg)
            return

        logger.warn('received message %s from an unknown peer %s', msg,
                    packet.SenderID[:8])

    def _do_write(self, msg, peer):
        """Put a message on the wire.

        Args:
            message (bytes): The contents of the message to send.
            peer (Node): The node to send the message to.

        Returns:
            bool: Whether or not the attempt to send the message succeeded.
        """

        if len(msg) > self.MaximumPacketSize:
            logger.error(
                'attempt to send a message beyond maximum packet size, %d',
                len(msg))
            return False

        try:
            host, port = peer.NetAddress
            ip = socket.gethostbyname(host)
            sentbytes = self.transport.write(msg, (ip, port))
        except socket.error as serr:
            if serr.errno == errno.EWOULDBLOCK:
                logger.error('outbound queue is full, dropping message to %s',
                             peer)
                return False
            else:
                logger.critical(
                    'unknown socket error occurred while sending message '
                    'to %s; %s',
                    peer, serr)
                return False
        except:
            logger.exception('error occurred while writing to %s', peer)
            return False

        if sentbytes < len(msg):
            logger.error('message transmission truncated at %d, expecting %d',
                         sentbytes, len(msg))

        self.PacketStats.BytesSent.add_value(sentbytes)
        return True

    def _send_msg(self, msg, destids):
        """Handle a request to send a message.

        Rather than send immediately we'll queue it up in the destination
        node to allow for flow control.

        Args:
            msg (Message): Initialized message of type Message.Message()
                or a subclass.
            destids (list): List of peer identifiers (UUIDs).
        """

        now = time.time()

        for dstnodeid in destids:
            dstnode = self.NodeMap.get(dstnodeid)
            if not dstnode:
                logger.info(
                    'attempt to send message to unknown node %s',
                    dstnodeid[:8])
                continue

            dstnode.enqueue_message(msg, now)

    def _send_ack(self, packet, peer):
        """Send an acknowledgement for a reliable packet.

        Args:
            packet (Packet): Incoming packet.
            peer (Node): Initialized peer object.
        """

        logger.debug("sending ack for %s to %s", packet, peer)

        self._do_write(packet.create_ack(self.LocalNode.Identifier).pack(),
                       peer)
        self.PacketStats.MessagesAcked.increment()

    def _handle_ack(self, incomingpkt):
        """Handle an incoming acknowledgement.

        Args:
            incomingpkt (Packet): Incoming packet.
        """

        incomingnode = self.NodeMap.get(incomingpkt.SenderID,
                                        incomingpkt.SenderID[:8])
        originalpkt = self.PendingAckMap.get(incomingpkt.SequenceNumber)

        # First thing to do is make sure that we have a record of this packet,
        # its not necessarily broken if the sequence number doesn't exist
        # because we may have expired the original packet if the ack took too
        # long to get here
        if not originalpkt:
            logger.info('received unexpected ack for packet %s from %s',
                        incomingpkt, incomingnode)
            return

        # The source for the ack better be the one we sent the original packet
        # to
        # This could be a real problem so mark it as a warning
        origdstnode = self.NodeMap[originalpkt.DestinationID]
        if incomingpkt.SenderID != origdstnode.Identifier:
            logger.warn('received ack for packet %s from %s instead of %s',
                        incomingpkt, incomingnode, origdstnode)
            logger.warn('%s, %s', incomingpkt.SenderID, origdstnode.Identifier)
            return

        # Normal situation... update the RTT estimator to help with future
        # retranmission times and remove the message from the retranmission
        # queue
        origdstnode.message_delivered(originalpkt.Message,
                                      time.time() - originalpkt.TransmitTime)

        self.PacketStats.AcksReceived.increment()
        del self.PendingAckMap[incomingpkt.SequenceNumber]

    def _timer_transmit(self, now):
        """A periodic handler that iterates through the nodes and sends
        any packets that are queued for delivery.

        Args:
            now (float): Current time.
        """
        srcnode = self.LocalNode

        dstnodes = self.peer_list(True)
        while len(dstnodes) > 0:
            newnodes = []
            for dstnode in dstnodes:
                msg = dstnode.get_next_message(now)
                if msg:
                    if dstnode.is_peer or msg.IsSystemMessage:
                        # basically we are looping through the nodes & as long
                        # as there are messages pending then come back around &
                        # try again
                        newnodes.append(dstnode)

                        packet = message.Packet()
                        packet.add_message(msg, srcnode, dstnode,
                                           self.next_sequence_number())
                        packet.TransmitTime = now

                        if packet.IsReliable:
                            self.PendingAckMap[packet.SequenceNumber] = packet

                        self._do_write(packet.pack(), dstnode)

            dstnodes = newnodes

    def _timer_cleanup(self, now):
        """A periodic handler that performs a variety of cleanup operations
        including checks for dropped packets.

        Args:
            now (float): Current time.
        """
        if now < self.NextCleanup:
            return

        if len(self.PendingAckMap):
            logger.debug("clean up processing %d unacked packets",
                         len(self.PendingAckMap))

        self.NextCleanup = now + self.CleanupInterval

        # Process packet retransmission
        deleteq = []
        for seqno, packet in self.PendingAckMap.iteritems():
            if (packet.TransmitTime + packet.RoundTripEstimate) < now:
                deleteq.append((seqno, packet))

        for (seqno, packet) in deleteq:
            logger.debug('packet %d has been marked as dropped', seqno)

            self.PacketStats.DroppedPackets.increment()

            # inform the node that we are treating the packet as though
            # it has been dropped, the node may have already closed the
            # connection so check that here
            if packet.DestinationID in self.NodeMap:
                dstnode = self.NodeMap[packet.DestinationID]
                dstnode.message_dropped(packet.Message, now)

            # and remove it from our saved queue
            del self.PendingAckMap[seqno]

        # Clean up information about old messages handled, this is a hack to
        # reduce memory utilization and does create an opportunity for spurious
        # duplicate messages to be processed. Should be fixed for production
        # use
        deleteq = []
        for msgid in self.MessageHandledMap.keys():
            exptime = self.MessageHandledMap[msgid]
            if exptime < now:
                deleteq.append(msgid)

        for msgid in deleteq:
            del self.MessageHandledMap[msgid]

    def _keep_alive(self, now):
        """A periodic handler that sends a keep alive message to all peers.

        Args:
            now (float): Current time.
        """
        if now < self.NextKeepAlive:
            return

        self.NextKeepAlive = now + self.KeepAliveInterval
        self.forward_message(connect_message.KeepAliveMessage())

        # Check for nodes with excessive RTTs, for now just report.
        for node in self.peer_list(True):
            node.bump_ticks()
            if node.MissedTicks > 10:
                logger.info('no messages from node %s in %d ticks, dropping',
                            node, node.MissedTicks)
                self.drop_node(node.Identifier)

    def _dispatcher(self):
        while self.ProcessIncomingMessages:
            msg = self.IncomingMessageQueue.pop()
            self.dispatcher.dispatch(msg)

    def shutdown(self):
        """Handle any shutdown processing.

        Note:
            Subclasses should override this method.
        """
        logger.info(
            'send disconnection message to peers in preparation for shutdown')

        self.forward_message(connect_message.DisconnectRequestMessage())

        # We could turn off packet processing at this point but we really need
        # to leave the socket open long enough to send the disconnect messages
        # that we just queued up
        self.ProcessIncomingMessages = False
        self.IncomingMessageQueue.appendleft(None)

    def add_node(self, peer):
        """Adds an endpoint to the list of peers known to this node.

        Args:
            peer (Node): The peer node to add to the node map.
        """
        self.NodeMap[peer.Identifier] = peer
        peer.initialize_stats(self.LocalNode)

    def drop_node(self, peerid):
        """Drops an endpoint from the list of connected peers

        Args
            peer (Node): The peer node to remove from the node map.
        """
        try:
            del self.NodeMap[peerid]
            self.onNodeDisconnect.fire(peerid)
        except:
            pass

    def forward_message(self, msg, exceptions=None, initialize=True):
        """Forward a previously received message on to our peers.

        This is useful for request messages that only need to be
        forwarded if they cannot be handled locally, but where
        we do not want to re-process the request.

        Args:
            msg (message.Message): The message to forward.
            exceptions (list): A list of Nodes to exclude from the peer_list.
            initialize (bool): Whether to initialize the origin fields, used
                for initial send of the message.
        """

        if exceptions is None:
            exceptions = []
        self._multicast_message(
            msg,
            self.peer_id_list(exceptions=exceptions),
            initialize)

    def _multicast_message(self, msg, nodeids, initialize=True):
        """
        Send an encoded message to a list of participants

        Args:
            message (message.Message): Object of type Message
            nodeids (list): List of node identifiers where the message should
                be sent.
            initialize (bool): Flag to indicate that the message should be
                signed.
        """

        if msg.IsForward:
            logger.warn('Attempt to unicast a broadcast message with id %s',
                        msg.Identifier[:8])
            msg.IsForward = False

        if initialize:
            msg.SenderID = self.LocalNode.Identifier
            msg.sign_from_node(self.LocalNode)

        self._send_msg(msg, nodeids)

    def send_message(self, msg, nodeid, initialize=True):
        """Send an encoded message through the peers to the entire
        network of participants.

        Args:
            msg (message.Message): The message to send.
            peerid (str): Identifer of the peer node.
            initialize (bool): Whether to initialize the origin fields, used
                for initial send of the message.
        """

        self._multicast_message(msg, [nodeid], initialize)

    def _handle_message(self, msg):
        logger.debug('calling handler for message %s from %s of type %s',
                     msg.Identifier[:8], msg.SenderID[:8], msg.MessageType)

        self.MessageHandledMap[msg.Identifier] = \
            time.time() + self.ExpireMessageTime
        self.IncomingMessageQueue.appendleft(msg)

        # and now forward it on to the peers if it is marked for forwarding
        if msg.IsForward and msg.TimeToLive > 0:
            self._send_msg(msg, self.peer_id_list(exceptions=[msg.SenderID]))

    def broadcast_message(self, msg, initialize=True):
        """
        Send an encoded message through the peers to the entire network
        of participants, including this node

        Args:
            msg (message.Message): The message to handle.
        """
        # mark the message as handled

        if initialize:
            msg.SenderID = self.LocalNode.Identifier
            msg.sign_from_node(self.LocalNode)

        self._handle_message(msg)

    def node_id_to_name(self, node_id):
        if node_id in self.NodeMap:
            return str(self.NodeMap[node_id])

        if node_id == self.LocalNode.Identifier:
            return str(self.LocalNode)

        return node_id[:8]
