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

import Queue
import errno
import logging
import socket
import sys
import time

from twisted.internet import reactor, task
from twisted.internet.protocol import DatagramProtocol

from gossip import event_handler
from gossip import message
from gossip import stats
from gossip.messages import connect_message
from gossip.messages import gossip_debug
from gossip.messages import random_walk_message
from gossip.messages import shutdown_message
from gossip.messages import topology_message

logger = logging.getLogger(__name__)


class Gossip(object, DatagramProtocol):
    """Defines the protocol for gossip communcation between nodes.

    Attributes:
        ExpireMessageTime (int): Time in seconds to hold message to test
            for duplicates.
        MaximumPacketSize (int): The maximum size of a packet.
        CleanupInterval (float): The number of seconds between cleanups.
        KeepAliveInterval (float): The number of seconds between keep
            alives.
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
        MessageHandlerMap (dict): A map of message types to handler
            functions.
        SequenceNumber (int): The next sequence number to be used for
            messages from the local node.
        NextCleanup (float): The time of the next cleanup event.
        NextKeepAlive (float): The time of the next keepalive event.
        onNodeDisconnect (EventHandler): An EventHandler for functions
            to call when a node becomes disconnected.
        onHeartbeatTimer (EventHandler): An EventHandler for functions
            to call when the heartbeat timer fires.
        MessageQueue (Queue): The queue of incoming messages.
        ProcessIncomingMessages (bool): Whether or not to process incoming
            messages.
        Listener (Reactor.listenUDP): The UDP listener.
    """

    # time in seconds to hold message to test for duplicates
    ExpireMessageTime = 300
    MaximumPacketSize = 8192 * 6 - 128
    CleanupInterval = 1.00
    KeepAliveInterval = 10.0

    def __init__(self, node, **kwargs):
        """Constructor for the Gossip class.

        Args:
            node (Node): The local node.
            MinimumRetries (int): The minimum number of retries on message
                transmission.
            RetryInterval (float): The time between retries, in seconds.
        """
        if 'MinimumRetries' in kwargs:
            self.MinimumRetries = kwargs['MinimumRetries']
        if 'RetryInterval' in kwargs:
            self.RetryInterval = kwargs['RetryInterval']

        self.LocalNode = node
        self.NodeMap = {}

        self.PendingAckMap = {}
        self.MessageHandledMap = {}
        self.MessageHandlerMap = {}

        self.SequenceNumber = 0
        self.NextCleanup = time.time() + self.CleanupInterval
        self.NextKeepAlive = time.time() + self.KeepAliveInterval

        self._initgossipstats()

        connect_message.register_message_handlers(self)

        gossip_debug.register_message_handlers(self)
        shutdown_message.register_message_handlers(self)
        topology_message.register_message_handlers(self)
        random_walk_message.register_message_handlers(self)

        # setup connectivity events
        self.onNodeDisconnect = event_handler.EventHandler('onNodeDisconnect')

        # setup the timer events
        self.onHeartbeatTimer = event_handler.EventHandler('onHeartbeatTimer')
        self.onHeartbeatTimer += self._timertransmit
        self.onHeartbeatTimer += self._timercleanup
        self.onHeartbeatTimer += self._keepalive

        self._HeartbeatTimer = task.LoopingCall(self._heartbeat)
        self._HeartbeatTimer.start(0.05)

        self.MessageQueue = Queue.Queue()

        try:
            self.ProcessIncomingMessages = True
            self.Listener = reactor.listenUDP(self.LocalNode.NetPort,
                                              self,
                                              interface=self.LocalNode.NetHost)
            reactor.callInThread(self._dispatcher)

        except:
            logger.critical(
                "failed to connect local socket, server shutting down",
                exc_info=True)
            sys.exit(0)

    def _initgossipstats(self):
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

        self.StatDomains = {
            'packet': self.PacketStats,
            'message': self.MessageStats
        }

    def peer_list(self, allflag=False, exceptions=[]):
        """Returns a list of peer nodes.

        Args:
            allflag (bool): Whether to include all peers.
            exceptions (list): A list of node identifiers to exclude
                from the peer list.

        Returns:
            list: A list of Nodes considered peers.
        """
        peers = []
        for peer in self.NodeMap.itervalues():
            if allflag or peer.Enabled:
                if peer.Identifier not in exceptions:
                    peers.append(peer)
        return peers

    def peer_id_list(self, allflag=False, exceptions=[]):
        """Returns a list of peer node identifiers.

        Args:
            allflag (bool): Whether to include all peers.
            exceptions (list): A list of node identifiers to exclude
                from the peer list.

        Returns:
            list: A list of Node identifiers considered peers.

        """
        return map(lambda p: p.Identifier, self.peer_list(allflag, exceptions))

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
                self._handleack(packet)
            return

        # first thing to do with the message is to send an ACK, all
        # retransmissions will be handled by the sending node, if the
        # IsReliable flag is set then this is not a system message & we know
        # that the peer exists
        if packet.IsReliable:
            if srcpeer:
                self._sendack(packet, srcpeer)

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

        if typename not in self.MessageHandlerMap:
            logger.info('no handler found for message type %s from %s',
                        minfo['__TYPE__'], srcpeer or packet.SenderID[:8])
            return

        try:
            msg = self.unpack_message(typename, minfo)
            msg.TimeToLive = packet.TimeToLive - 1
            msg.SenderID = packet.SenderID
        except:
            logger.exception(
                'unable to deserialize message of type %s from %s', typename,
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

        if srcpeer or msg.IsSystemMessage:
            self.handle_message(msg)
            return

        logger.warn('received message %s from an unknown peer %s', msg,
                    packet.SenderID[:8])

    # --------------------------------- ###
    # Utility functions                 ###
    # --------------------------------- ###

    def _heartbeat(self):
        """Invoke functions that are connected to the heartbeat timer.
        """
        try:
            now = time.time()
            self.onHeartbeatTimer.fire(now)
        except:
            logger.exception('unhandled error occured during timer processing')

    def _dowrite(self, msg, peer):
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
            sentbytes = self.transport.write(msg, peer.NetAddress)
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

    def _sendmsg(self, msg, destids):
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
                logger.debug('attempt to send message to unknown node %s',
                             dstnodeid[:8])
                continue

            if dstnode.Enabled or msg.IsSystemMessage:
                dstnode.enqueue_message(msg, now)

    def _sendack(self, packet, peer):
        """Send an acknowledgement for a reliable packet.

        Args:
            packet (Packet): Incoming packet.
            peer (Node): Initialized peer object.
        """

        logger.debug("sending ack for %s to %s", packet, peer)

        self._dowrite(packet.create_ack(self.LocalNode.Identifier).pack(),
                      peer)
        self.PacketStats.MessagesAcked.increment()

    def _handleack(self, incomingpkt):
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

    def _timertransmit(self, now):
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
                    if dstnode.Enabled or msg.IsSystemMessage:
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

                        self._dowrite(packet.pack(), dstnode)

            dstnodes = newnodes

    def _timercleanup(self, now):
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

    def _keepalive(self, now):
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
            msg = self.MessageQueue.get()
            try:
                if msg and msg.MessageType in self.MessageHandlerMap:
                    self.MessageHandlerMap[msg.MessageType][1](msg, self)

            # handle the attribute error specifically so that the message type
            # can be used in the next exception
            except:
                logger.exception(
                    'unexpected error handling message of type %s',
                    msg.MessageType)

            self.MessageQueue.task_done()

    # --------------------------------- ###
    # Locally defined interface methods ###
    # --------------------------------- ###

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
        self.MessageQueue.put(None)

    def register_message_handler(self, msg, handler):
        """Register a function to handle incoming messages for the
        specified message type.

        Args:
            msg (type): A type object derived from MessageType.
            handler (function): Function to be called when messages of
                that type arrive.
        """
        self.MessageHandlerMap[msg.MessageType] = (msg, handler)

    def clear_message_handler(self, msg):
        """Remove any handlers associated with incoming messages for the
        specified message type.

        Args:
            msg (type): A type object derived from MessageType.
        """
        try:
            del self.MessageHandlerMap[msg.MessageType]
        except:
            pass

    def get_message_handler(self, msg):
        """Returns the function registered to handle incoming messages
        for the specified message type.

        Args:
            msg (type): A type object derived from MessageType.
            handler (function): Function to be called when messages of
                that type arrive.

        Returns:
            function: The registered handler function for this message
                type.
        """
        return self.MessageHandlerMap[msg.MessageType][1]

    def unpack_message(self, mtype, minfo):
        """Unpack a dictionary into a message object using the
        registered handlers.

        Args:
            mtype (str): Name of the message type.
            minfo (dict): Dictionary with message data.

        Returns:
            The result of the handler called with minfo.
        """
        return self.MessageHandlerMap[mtype][0](minfo)

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

    def forward_message(self, msg, exceptions=[], initialize=True):
        """Forward a previously received message on to our peers.

        This is useful for request messages that only need to be
        forwarded if they cannot be handled locally, but where
        we do not want to re-process the request.

        Args:
            msg (Message): The message to forward.
            exceptions (list): A list of Nodes to exclude from the peer_list.
            initialize (bool): Whether to initialize the origin fields, used
                for initial send of the message.
        """

        if msg.IsForward:
            logger.warn('Attempt to forward a broadcast message with id %s',
                        msg.Identifier[:8])
            msg.IsForward = False

        if initialize:
            msg.sign_from_node(self.LocalNode)

        self._sendmsg(msg, self.peer_id_list(exceptions=exceptions))

    def send_message(self, msg, peerid, initialize=True):
        """Send an encoded message through the peers to the entire
        network of participants.

        Args:
            msg (Message): The message to send.
            peerid (str): Identifer of the peer node.
            initialize (bool): Whether to initialize the origin fields, used
                for initial send of the message.
        """

        if msg.IsForward:
            logger.warn('Attempt to unicast a broadcast message with id %s',
                        msg.Identifier[:8])
            msg.IsForward = False

        if initialize:
            msg.sign_from_node(self.LocalNode)

        self._sendmsg(msg, [peerid])

    def broadcast_message(self, msg, initialize=True):
        """Send an encoded message through the peers to the entire network
        of participants.

        Args:
            msg (Message): The message to broadcast.
            initialize (bool): Whether to initialize the origin fields, used
                for initial send of the message.
        """

        if not msg.IsForward:
            logger.warn('Attempt to broadcast a unicast message with id %s',
                        msg.Identifier[:8])
            msg.IsForward = True

        if initialize:
            msg.sign_from_node(self.LocalNode)

        self.handle_message(msg)

    def handle_message(self, msg):
        """Handle a message.

        Args:
            msg (Message): The message to handle.
        """
        # mark the message as handled
        logger.debug('calling handler for message %s from %s of type %s',
                     msg.Identifier[:8], msg.SenderID[:8], msg.MessageType)

        self.MessageHandledMap[msg.Identifier] = time.time(
        ) + self.ExpireMessageTime
        self.MessageQueue.put(msg)

        # and now forward it on to the peers if it is marked for forwarding
        if msg.IsForward and msg.TimeToLive > 0:
            self._sendmsg(msg, self.peer_id_list(exceptions=[msg.SenderID]))
