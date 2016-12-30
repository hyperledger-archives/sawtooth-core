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

import unittest
import time

import gossip.signed_object as SigObj

from sawtooth_signing import pbct_nativerecover as signing
from gossip.gossip_core import Gossip, GossipException
from gossip.message import Packet, Message
from gossip.node import Node
from gossip.messages import shutdown_message


# from utils.py in txintegration
def generate_private_key():
    return signing.encode_privkey(signing.generate_privkey(), 'wif')


class TestGossipCore(unittest.TestCase):
    # Helper functions for creating the test
    def _setup(self, port):
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        firstNode = Node(identifier=ident, signingkey=signingkey,
                         address=("localhost", port))
        core = Gossip(firstNode)
        return core

    def _create_node(self, port):
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", port))
        node.is_peer = True
        return node

    def _create_msg(self):
        msg = Message({'__SIGNATURE__': "test"})
        return msg

    def test_gossip_core_init(self):
        # Test correct init
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        firstNode = Node(identifier=ident, signingkey=signingkey,
                         address=("localhost", 8800))
        core = Gossip(firstNode)
        self.assertIsNotNone(core)

    def test_gossip_core_bad_node_address(self):
        # Make sure it fails if given a node without an address
        # Should always throw an error
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey)
        try:
            core = Gossip(node)
            self.fail("Should raise an error")
        except GossipException, e:
            self.assertIsInstance(e, GossipException)

    def test_gossip_core_stats(self):
        # Test that stats are set and change as different methods are used
        core = self._setup(8801)
        packetdic1 = core.PacketStats.get_stats()
        msgdic1 = str(core.MessageStats.get_stats())
        newNode = self._create_node(8859)
        core.add_node(newNode)
        msg = self._create_msg()
        pak = Packet()
        pak.add_message(msg, newNode, newNode, 0)

        # Following methods should update PacketStats
        core._do_write(pak.pack(), newNode)
        core._send_ack(pak, newNode)
        data = pak.pack()

        # Following method should update MessageStats
        packetdic2 = core.PacketStats.get_stats()
        core.datagramReceived(data, "localhost:8801")
        msgdic2 = str(core.MessageStats.get_stats())
        msgdic = core.MessageStats.get_stats(["MessageType"])["MessageType"]
        self.assertEqual(packetdic2["MessagesAcked"], 1)
        self.assertNotEqual(packetdic2["BytesSent"], [0, 0])
        self.assertNotEqual(packetdic1, packetdic2)
        self.assertNotEqual(msgdic1, msgdic2)
        self.assertEqual(msgdic['/gossip.Message/MessageBase'], 1)

    def test_gossip_peers(self):
        # Test retrieving peers and their ids
        core = self._setup(8802)
        peers = core.peer_list()
        self.assertEqual(peers, [])

        # Create more nodes
        newNode = self._create_node(8803)
        newNode.is_peer = True

        # Add nodes to NodeMape
        core.add_node(newNode)
        peers = core.peer_list()
        idDic = core.peer_id_list()
        self.assertIn(newNode, peers)
        self.assertIn(newNode.Identifier, idDic)

        # Test that exceptions are ignored
        peers = core.peer_list(exceptions=[newNode.Identifier])
        idDic = core.peer_id_list(exceptions=[newNode.Identifier])
        self.assertEqual(peers, [])
        self.assertNotIn(newNode.Identifier, idDic)


class TestGossipCoreDatagram(unittest.TestCase):

    # Helper functions for creating the Test
    def _setup(self, port):
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        firstNode = Node(identifier=ident, signingkey=signingkey,
                         address=("localhost", port))
        core = Gossip(firstNode)
        return core

    def _create_node(self, port):
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", port))
        node.is_peer = True
        return node

    def _create_msg(self):
        msg = Message({'__SIGNATURE__': "test"})
        return msg

    def test_gossip_start_protocol(self):
        # Test that the start protocol sets the Netport and maxpacket size
        core = self._setup(9050)
        core.LocalNode.NetPort = 100
        core.LocalNode.maxPacketSize = 10
        core.startProtocol()
        self.assertEqual(core.LocalNode.NetPort, 9050)
        self.assertEqual(core.transport.maxPacketSize, 49024)

    def test_gossip_stop_protocol(self):
        # Stop protocol does nothing at this point
        core = self._setup(9051)
        core.stopProtocol()

    def test_gossip_datagram_received(self):
        # Test that datagramReceived behaves as expected
        core = self._setup(9500)
        peer = self._create_node(9501)
        peer2 = self._create_node(9502)
        core.add_node(peer)
        core.add_node(peer2)
        msg = self._create_msg()
        pak = Packet()
        pak.add_message(msg, peer, peer2, 0)
        data = pak.pack()
        # Test correct use of datagramReceived
        core.datagramReceived(data, "localhost:9001")
        msgType = core.MessageStats.get_stats(["MessageType"])
        self.assertIn('/gossip.Message/MessageBase',
                      msgType["MessageType"])
        pakStats = core.PacketStats.get_stats(["MessagesAcked"])
        self.assertEqual(pakStats["MessagesAcked"], 1)
        # Test handling of duplicate packets
        msg2 = shutdown_message.ShutdownMessage({'__SIGNATURE__': "test"})
        core.MessageHandledMap[msg2.Identifier] = time.time()
        pak.add_message(msg2, peer, peer2, 1)
        data2 = pak.pack()
        core.datagramReceived(data2, "localhost:9001")
        pakStats = core.PacketStats.get_stats(["DuplicatePackets"])
        self.assertEqual(pakStats["DuplicatePackets"], 1)

    def test_gossip_datagram_unknown_peer(self):
        # Test that nothing is done if the nodes are not known
        core = self._setup(9007)
        peer = self._create_node(9008)
        peer2 = self._create_node(9009)
        msg = self._create_msg()
        pak = Packet()
        pak.add_message(msg, peer, peer2, 0)
        data = pak.pack()
        status = core.datagramReceived(data, "localhost:9001")
        self.assertIsNone(status)

    def test_gossip_datagram_recieved_ack(self):
        # Test that datagramReceived handles acknowledgements correctly
        core = self._setup(9004)
        peer = self._create_node(9005)
        peer2 = self._create_node(9006)
        core.add_node(peer)
        core.add_node(peer2)
        msg = self._create_msg()
        pak = Packet()
        pak.add_message(msg, peer, peer2, 0)
        newPak = pak.create_ack(peer2.Identifier)
        data = newPak.pack()
        core.PendingAckMap[0] = pak
        # send ack
        core.datagramReceived(data, "localhost:9001")
        stats = core.PacketStats.get_stats(["AcksReceived"])
        self.assertEqual(stats["AcksReceived"], 1)


class TestGossipCoreUtilityAndInterface(unittest.TestCase):

    # Helper functions for creating the Test
    def _setup(self, port):
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        firstNode = Node(identifier=ident, signingkey=signingkey,
                         address=("localhost", port))
        core = Gossip(firstNode)
        return core

    def _create_node(self, port):
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", port))
        node.is_peer = True
        return node

    def _create_msg(self):
        msg = Message({'__SIGNATURE__': "test"})
        return msg

    def test_gossip_heartbeat(self):
        # test HeartBeat handler does not throw any errors
        core = self._setup(9052)
        try:
            core.dispatcher._heartbeat()
        except:
            self.fail("Heartbeat Timer error")

    def test_gossip_dowrite(self):
        # Test _dowrite puts a message on the wire
        core = self._setup(8804)
        newNode = self._create_node(8805)
        newNode.is_peer = True
        core.add_node(newNode)
        core2 = Gossip
        pak = Packet()
        data = "test the pack"
        pak.Data = data
        # Test correct sending of bytes
        status = core._do_write(pak.pack(), newNode)
        self.assertTrue(status)
        stats = core.PacketStats.get_stats(["BytesSent"])
        self.assertNotEqual(stats["BytesSent"], [0, 0])
        # Test failure of message that is too big
        # This will print out an error
        core.MaximumPacketSize = 0
        status = core._do_write(pak.pack(), newNode)
        self.assertFalse(status)

    def test_gossip_sendmsg(self):
        # Test sending msg to their destinations
        core = self._setup(8806)
        # Send message to unknown node, will not add to queue
        newNode = self._create_node(8807)
        msg = self._create_msg()
        core._send_msg(msg, [newNode.Identifier])
        self.assertEqual(str(newNode.MessageQ), "[]")

        # Make node known, should add to the queue
        core.add_node(newNode)
        core._send_msg(msg, [newNode.Identifier])
        self.assertNotEqual(str(newNode.MessageQ), "[]")

    def test_gossip_ack_good(self):
        # Test sending acknowledgements
        core = self._setup(8808)
        pak = Packet()
        newNode = self._create_node(8809)
        core.add_node(newNode)
        newNode.is_peer = True
        core._send_ack(pak, newNode)

        # Add pak to PendingAckMap
        msg = self._create_msg()
        pak.add_message(msg, newNode, newNode, 0)
        core.PendingAckMap[pak.SequenceNumber] = pak
        ack = pak.create_ack(newNode.Identifier)
        core._handle_ack(ack)
        stats = core.PacketStats.get_stats(["AcksReceived"])
        self.assertEqual(stats["AcksReceived"], 1)

    def test_gossip_ack_unknown_packet(self):
        # Test behavior of sending a packet incorrectly
        core = self._setup(8810)
        pak = Packet()
        newNode = self._create_node(8811)
        core.add_node(newNode)
        # Ignore acks from unexpected packets not in PendingAckMap
        core._handle_ack(pak)
        stats = core.PacketStats.get_stats(["AcksReceived"])
        self.assertEqual(stats["AcksReceived"], 0)

        badNode = self._create_node(8812)
        core.add_node(badNode)
        # Test behavior of receiving an ack with bad Identifier
        # Will print out two warnings
        msg = self._create_msg()
        pak.add_message(msg, newNode, newNode, 0)
        core.PendingAckMap[pak.SequenceNumber] = pak
        ack = pak.create_ack(newNode.Identifier)
        pak.DestinationID = badNode.Identifier
        core._handle_ack(pak)
        stats = core.PacketStats.get_stats(["AcksReceived"])
        self.assertEqual(stats["AcksReceived"], 0)

    def test_gossip_timer(self):
        # Test timertransmit
        now = time.time()
        core = self._setup(8816)
        node1 = self._create_node(8813)
        node2 = self._create_node(8814)
        node3 = self._create_node(8815)
        # Add nodes to NodeMap
        core.add_node(node1)
        core.add_node(node2)
        core.add_node(node3)

        msg1 = self._create_msg()
        msg2 = self._create_msg()
        msg3 = self._create_msg()
        # Add messages to nodes
        node1.enqueue_message(msg1, now)
        node2.enqueue_message(msg2, now)
        node3.enqueue_message(msg3, now)
        time.sleep(1)
        now = time.time()
        # Adds messages to PendingAckMap
        self.assertEqual(core.PendingAckMap, {})
        core._timer_transmit(now)
        self.assertNotEqual(core.PendingAckMap, {})
        self.assertEqual(len(core.PendingAckMap), 3)
        # Test _timercleanup
        now = time.time() + 10000
        # Clean up "dropped" packets
        core._timer_cleanup(now)
        self.assertEqual(core.PendingAckMap, {})

    def test_gossip_dispatcher(self):
        # Test _dispatch will not loop if not processing messages
        core = self._setup(8883)
        msg = shutdown_message.ShutdownMessage({'__SIGNATURE__': "test"})
        core.IncomingMessageQueue.appendleft(msg)
        # Should not run if ProcessIncomingMessages is False
        # Otherwise it will loop
        core.ProcessIncomingMessages = False
        core._dispatcher()

    def test_keep_alive(self):
        # Test keep_alive, should only remove nodes with too many missed ticks
        core = self._setup(8880)
        msg = self._create_msg()
        msg.IsForward = False
        node1 = self._create_node(8881)
        node2 = self._create_node(8882)
        core.add_node(node1)
        core.add_node(node2)
        before = str(core.NodeMap)
        now = time.time() + 100
        core._keep_alive(now)
        after = str(core.NodeMap)
        self.assertEqual(before, after)

        # Test that a node with too many missed ticks is dropped
        node3 = self._create_node(8883)
        node3.MissedTicks = 110
        core.add_node(node3)
        now = now + 100
        core._keep_alive(now)
        after2 = str(core.NodeMap)
        self.assertEqual(before, after2)

    # Locally defined interface methods
    def test_gossip_shutdown(self):
        # Test that shutdown will empty the queue
        # And turns of ProcessIncomingMessages
        core = self._setup(8888)
        core.shutdown()
        self.assertFalse(core.ProcessIncomingMessages)
        self.assertFalse(len(core.IncomingMessageQueue) == 0)

    def test_gossip_register_message_handlers(self):
        # Test that a message handler and type can be added and removed
        core = self._setup(8840)
        msg = shutdown_message.ShutdownMessage({'__SIGNATURE__': "test"})
        # Remove ShutdownMessage handler
        core.dispatcher.clear_message_handler(msg)
        self.assertFalse(
            core.dispatcher.has_message_handler(
                "/gossip.messages.ShutdownMessage/ShutdownMessage"))
        # Add ShutdownMessage handler
        core.dispatcher.register_message_handler(
            msg, shutdown_message.shutdown_handler)
        self.assertTrue(
            core.dispatcher.has_message_handler(
                "/gossip.messages.ShutdownMessage/ShutdownMessage"))

    def test_gossip_get_message_handler(self):
        # Get message handler from MessageHandlerMap
        # Will throw error if not in HandlerMap
        core = self._setup(8841)
        msg = shutdown_message.ShutdownMessage({'__SIGNATURE__': "test"})
        handler = core.dispatcher.get_message_handler(msg)
        self.assertEqual(handler,
                          shutdown_message.shutdown_handler)

    def test_gossip_unpack_message(self):
        # Test unpacking message using its handler
        core = self._setup(8842)
        msg = shutdown_message.ShutdownMessage({'__SIGNATURE__': "test"})
        info = msg.dump()
        m = core.dispatcher.unpack_message(
            '/gossip.messages.ShutdownMessage/ShutdownMessage', info)
        self.assertEqual(msg.Identifier, m.Identifier)

    def test_gossip_add_and_drop_node(self):
        # Test adding and dropping nodes from NodeMap
        core = self._setup(8817)
        node = self._create_node(8818)
        # Add node
        core.add_node(node)
        self.assertIn(node, list(core.NodeMap.values()))
        # Drop node
        core.drop_node(node.Identifier)
        self.assertNotIn(node, list(core.NodeMap.values()))

    def test_gossip_multicast_msg(self):
        # Test multicast message, send same message to both nodes
        core = self._setup(8819)
        msg = self._create_msg()
        msg.IsForward = False
        node1 = self._create_node(8820)
        node2 = self._create_node(8821)
        core.add_node(node1)
        core.add_node(node2)
        core._multicast_message(msg, [node1.Identifier, node2.Identifier])
        self.assertEqual(str(node1.MessageQ), str(node2.MessageQ))

    def test_gossip_send_message(self):
        # Test send_message, send a message to 1 node, calls multicast
        core = self._setup(8822)
        msg = self._create_msg()
        msg.IsForward = False
        node1 = self._create_node(8823)
        node2 = self._create_node(8824)
        core.add_node(node1)
        core.add_node(node2)
        core.send_message(msg, node2.Identifier)
        self.assertEqual(str(node1.MessageQ), "[]")
        self.assertNotEqual(str(node2.MessageQ), "[]")

    def test_gossip_forward_msg(self):
        # Test fwd message with an exception to not send to, calls multicast
        core = self._setup(8831)
        msg = self._create_msg()
        msg.IsForward = False
        node1 = self._create_node(8832)
        node2 = self._create_node(8833)
        core.add_node(node1)
        core.add_node(node2)
        core.forward_message(msg, [node2.Identifier])
        self.assertNotEqual(str(node1.MessageQ), str(node2.MessageQ))

    def test_gossip_handle_msg(self):
        # Test handle_msg, uses sendmsg if
        core = self._setup(8825)
        msg = self._create_msg()
        node1 = self._create_node(8826)
        node2 = self._create_node(8827)
        core.add_node(node1)
        core.add_node(node2)
        core._handle_message(msg)
        self.assertEqual(str(node1.MessageQ), str(node2.MessageQ))
        self.assertIn(msg.Identifier, core.MessageHandledMap)
        self.assertNotEqual(str(node1.MessageQ), "[]")
        self.assertNotEqual(str(node2.MessageQ), "[]")

    def test_gossip_handle_broadcast_msg(self):
        # Test broadcast_message, uses handle_msg
        core = self._setup(8828)
        msg = self._create_msg()
        node1 = self._create_node(8829)
        node2 = self._create_node(8830)
        core.add_node(node1)
        core.add_node(node2)
        core.broadcast_message(msg)
        self.assertEqual(str(node1.MessageQ), str(node2.MessageQ))
        self.assertIn(msg.Identifier, core.MessageHandledMap)
