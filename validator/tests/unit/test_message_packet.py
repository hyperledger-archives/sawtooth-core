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

from gossip.message import Packet, Message, unpack_message_data
from gossip.node import Node
from gossip.common import dict2cbor


class TestPacket(unittest.TestCase):

    def test_packet_init(self):
        # Test trival intialization of a packet
        # Check each value defualts correctly
        pak = Packet()
        self.assertEqual(pak.TimeToLive, 255)
        self.assertEqual(pak.SequenceNumber, 0)
        self.assertEqual(pak.IsAcknowledgement, False)
        self.assertEqual(pak.IsReliable, True)
        self.assertEqual(pak.SenderID, '========================')
        self.assertEqual(pak.Message, None)
        self.assertEqual(pak.Data, b'')
        self.assertEqual(pak.TransmitTime, 0.0)
        self.assertEqual(pak.RoundTripEstimate, 0.0)
        self.assertEqual(pak.DestinationID, '========================')
        self.assertEqual(pak.Identifier, None)

    def test_packet_str(self):
        # Test string method
        pak = Packet()
        string = pak.__str__()
        self.assertEqual(string, "PKT:{0}:{1}".format(pak.SenderID[:8],
                                                      pak.SequenceNumber))

    def test_create_ack(self):
        # Test creating an acknowledgement packet for a packet
        pak = Packet()
        # Fake nodeid for acknowledgement
        nodeID = "testNodeId"
        newAck = pak.create_ack(nodeID)
        self.assertIsNotNone(newAck)
        self.assertTrue(newAck.IsAcknowledgement)
        # Should have the same SequenceNumber
        self.assertEqual(newAck.SequenceNumber, pak.SequenceNumber)
        self.assertEqual(newAck.SenderID, nodeID)

    def test_add_message(self):
        # Add a message to a packet, along with source node and destination
        # Resets the packet attributes with that of the message
        pak = Packet()
        # Need signingkey, otherwise throws errors
        srcNode = Node(identifier="source", signingkey="source")
        desNode = Node(identifier="destination", signingkey="destination")
        msg = Message({'__SIGNATURE__': "MsgTestS"})
        pak.add_message(msg, srcNode, desNode, 1)
        # Check that msg and pak have the same attributes
        self.assertEqual([msg.Identifier, msg.TimeToLive, msg.IsReliable],
                         [pak.Identifier, pak.TimeToLive, pak.IsReliable])
        # Check correct SenderID
        self.assertEqual(srcNode.Identifier, pak.SenderID)
        # Check correct destinationID and destination RTE
        self.assertEqual(desNode.Identifier, pak.DestinationID)
        self.assertEqual(desNode.Estimator.RTO, pak.RoundTripEstimate)

        # Check correct data and msg
        self.assertEqual(pak.Message, msg)
        self.assertEqual(pak.Data, repr(msg))

    def test_pack_unpack(self):
        # Test packing a paket and a packed packet can be unpacked correctly
        pak = Packet()
        data = "test the pack"
        pak.Data = data
        # Store original attributes
        original = [pak.PackedFormat, pak.TimeToLive,
                    pak.SequenceNumber, pak.IsAcknowledgement,
                    pak.IsReliable, str(pak.SenderID)]
        packed = pak.pack()
        # Change the packet to see if it will be returned to original
        pak.SequenceNumber = 1234
        pak.unpack(packed)
        # Store the attrubites of the unpacked pack
        new = [pak.PackedFormat, pak.TimeToLive,
               pak.SequenceNumber, pak.IsAcknowledgement,
               pak.IsReliable, str(pak.SenderID)]

        self.assertEqual(original, new)
        self.assertEqual("test the pack", pak.Data.decode())


class TestMessage(unittest.TestCase):

    def test_message_init(self):
        # Test default Message intialization
        # This is a bad for actual use because it does not have a Signature
        msg = Message()
        time.sleep(.05)
        self.assertLess(msg.Nonce, time.time())
        self.assertEqual(msg.TimeToLive, (2**31))
        self.assertTrue(msg.IsForward)
        self.assertTrue(msg.IsReliable)
        self.assertFalse(msg.IsSystemMessage)
        self.assertIsNone(msg._data)
        # Add signature and nounce to minfo
        msg2 = Message({'__SIGNATURE__': "Test", "__NONCE__": 10.02})
        self.assertEqual(msg2.Nonce, 10.02)

    def test_message_str(self):
        # Test overridden string method
        # Will cause warning from SignedObject identifier
        msg = Message({'__SIGNATURE__': "Test"})
        string = str(msg)
        self.assertEqual(string, "MSG:{0}:{1}".format(msg.OriginatorID[:8],
                                                      msg._identifier[:8]))

    def test_str_assertion(self):
        # Test if the assert is called within SignedObject, An assert error
        # Should be called if message does not have a signature
        msg1 = Message()
        try:
            string = str(msg1)
            self.fail("This should cause an Assert Error")
        except AssertionError, e:
            self.assertIsInstance(e, AssertionError)

    def test_message_repr(self):
        # Test the overridden repr function
        # First case to test is when the msg has no data, creates data
        msg = Message({'__SIGNATURE__': "Test"})
        serMsg = msg.serialize()
        self.assertIsNone(msg._data)
        self.assertEqual(repr(msg), serMsg)
        self.assertEqual(msg._data, serMsg)
        # Second case is when the msg contains data
        msg2 = Message({'__SIGNATURE__': "Test"})
        msg2._data = "test data"
        self.assertEqual(repr(msg2), "test data")
        self.assertEqual(msg2._data, "test data")

    def test_message_len(self):
        # Test the overriden len function
        # First case is when the msg has no data, creates data
        msg = Message({'__SIGNATURE__': "Test"})
        length = len(dict2cbor(msg.dump()))
        self.assertIsNone(msg._data)
        self.assertEqual(len(msg), length)
        # The second case is when the msg does have data
        msg2 = Message({"__SIGNATURE__": "Test"})
        msg2._data = "test data"
        self.assertEqual(len(msg2), len("test data"))

    def test_message_dump(self):
        # Test dump for message
        msg = Message({'__SIGNATURE__': "Test", "__NONCE__": 1000.3})
        expectedDump = {'__SIGNATURE__': "Test", "__NONCE__": 1000.3,
                        "__TYPE__": "/gossip.Message/MessageBase",
                        "PublicKey": None}
        self.assertEqual(msg.dump(), expectedDump)

    def test_unpack_message(self):
        # Make sure that the message can be unpacked after serliazation
        msg = Message({'__SIGNATURE__': "Test"})
        cbor = dict2cbor(msg.dump())
        msgdict = unpack_message_data(cbor)
        self.assertEqual(msg.dump(), msgdict)
