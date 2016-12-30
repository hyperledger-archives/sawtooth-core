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

from gossip.node import Node, TransmissionQueue, RoundTripEstimator
import gossip.signed_object as SigObj
from gossip.message import Message


class TestNode(unittest.TestCase):
    # Helper methods to create nodes
    def _create_node(self):
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 8800))
        return node

    def test_node_init(self):
        # Test normal Init for a single node
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 8800))
        self.assertEqual(node.NetHost, "localhost")
        self.assertEqual(node.NetPort, 8800)
        self.assertEqual(node.Identifier, ident)
        self.assertEqual(node.SigningKey, signingkey)
        self.assertEqual(node.Name, ident[:8])
        self.assertFalse(node.is_peer)
        self.assertIsInstance(node.Estimator, RoundTripEstimator)
        self.assertIsInstance(node.MessageQ, TransmissionQueue)
        self.assertEqual(node.Delay, node._fixeddelay)

    def test_node_netaddress(self):
        # Test NetAddress property
        node = self._create_node()
        self.assertEqual(node.NetAddress, ("localhost", 8800))

    def test_node_str(self):
        # Test overloaded string function
        node = self._create_node()
        # If not given a name, node.Name is first 8 letters of its Id
        self.assertEqual(node.Name, node.Identifier[:8])
        self.assertEqual(node.Name, str(node))

    def test_node_delay(self):
        # Test _randomdelay and _fixeddelay for node
        node = self._create_node()
        rdelay1 = node._randomdelay()
        rdelay2 = node._randomdelay()
        self.assertLess(rdelay1, 1)
        # The delays should change with _randomdelay
        self.assertNotEqual(rdelay1, rdelay2)
        fdelay3 = node._fixeddelay()
        fdelay4 = node._fixeddelay()
        # The delay _fixeddelay should not change after node is created
        self.assertEqual(fdelay3, fdelay4)

    def test_node_initialize_stats(self):
        # Test Stats are initialized as expected
        node = self._create_node()
        node2 = self._create_node()
        # before should be None
        before = node.Stats
        node.initialize_stats(node2)
        after = node.Stats.get_stats()
        self.assertNotEqual(before, after)

    def test_node_enqueue_message(self):
        # Test correct enqueue of a message to MessageQueue
        node = self._create_node()
        before = str(node.MessageQ)
        msg = Message()
        msg.sign_from_node(node)
        now = time.time()
        # Add message
        node.enqueue_message(msg, now)
        after = str(node.MessageQ)
        self.assertNotEqual(before, after)
        self.assertIn(msg.Identifier, node.MessageQ.Messages)

    def test_node_dequeue_message(self):
        # Test correct enqueue of a message from MessageQueue
        node = self._create_node()
        msg = Message()
        msg.sign_from_node(node)
        now = time.time()
        # must enqueue message before able to dequeue
        node.enqueue_message(msg, now)
        before = str(node.MessageQ)
        node.dequeue_message(msg)
        after = str(node.MessageQ)
        self.assertNotEqual(before, after)
        self.assertNotIn(msg.Identifier, node.MessageQ.Messages)

    def test_node_dequeue_message_no_message(self):
        # Test that trying to dequeue a message that is not enqueued does not
        # throw an error
        node = self._create_node()
        msg = Message()
        msg.sign_from_node(node)
        now = time.time()
        # Msg was never enqueued
        before = str(node.MessageQ)
        node.dequeue_message(msg)
        after = str(node.MessageQ)
        self.assertEqual(before, after)

    def test_node_get_next_message(self):
        # Test get_next_message
        now = time.time()
        node = self._create_node()
        node2 = self._create_node()
        # No Messages, return None
        self.assertIsNone(node.get_next_message(now))
        msg = Message()
        msg2 = Message()
        msg.sign_from_node(node)
        msg2.sign_from_node(node2)
        now = time.time()
        # Add only 1 message
        node.enqueue_message(msg, now)
        self.assertEqual(node.get_next_message(now + 5), msg)
        now = time.time()
        node.enqueue_message(msg, now)
        node.enqueue_message(msg2, now)
        # Should not return anything since the time is the same
        self.assertIsNone(node.get_next_message(now))
        # Take out 1 message
        self.assertNotIn(node.get_next_message(now + 5),
                         node.MessageQ.Messages)
        # Take out last message
        self.assertNotIn(node.get_next_message(now + 5),
                         node.MessageQ.Messages)
        # No messages left, should return None
        self.assertEqual(node.get_next_message(now + 5), None)

    def test_node_message_delivered(self):
        # Test behavior if message is "delivered"
        node = self._create_node()
        msg = Message()
        msg.sign_from_node(node)
        node.enqueue_message(msg, time.time())
        oldRTO = node.Estimator.RTO
        node.message_delivered(msg, 2.0)
        newRTO = node.Estimator.RTO
        # Should update RTO and add identifier to MessageQueue
        self.assertLess(oldRTO, newRTO)
        self.assertNotIn(msg.Identifier, node.MessageQ.Messages)

    def test_node_message_dropped(self):
        # Test behavior if message is believe to be "dropped"
        node = self._create_node()
        msg = Message()
        msg.sign_from_node(node)
        oldRTO = node.Estimator.RTO
        node.message_dropped(msg)
        newRTO = node.Estimator.RTO
        # Should increase RTO and "re-add" msg to the MessageQueue
        self.assertLess(oldRTO, newRTO)
        self.assertIn(msg.Identifier, node.MessageQ.Messages)

    def test_node_ticks(self):
        # Test bump_ticks and reset_ticks
        node = self._create_node()
        # Bump ticks 10 times
        for i in range(10):
            node.bump_ticks()
        self.assertEqual(node.MissedTicks, 10)
        # reset the MissedTicks to zero
        node.reset_ticks()
        self.assertEqual(node.MissedTicks, 0)

    def test_node_reset_peer_stats(self):
        # Test that reset_peers does not break
        now = time.time()
        node = self._create_node()
        node2 = self._create_node()
        node.initialize_stats(node2)
        msg = Message()
        msg.sign_from_node(node)
        stats1 = str(node.Stats.get_stats(["Address", "MessageQueue",
                                           "MessageQueueLength"]))
        # Nothing changes since all are the original defaults
        node.reset_peer_stats(["Address", "MessageQueue",
                               "MessageQueueLength"])
        stats2 = str(node.Stats.get_stats(["Address", "MessageQueue",
                                           "MessageQueueLength"]))
        self.assertEqual(stats1, stats2)
        node.enqueue_message(msg, now)
        stats3 = (node.Stats.get_stats(["Address", "MessageQueue",
                                        "MessageQueueLength"]))
        node.reset_peer_stats(["Address", "MessageQueue",
                               "MessageQueueLength"])
        stats4 = (node.Stats.get_stats(["Address", "MessageQueue",
                                        "MessageQueueLength"]))
        # All values are either sample or value metrics that are not changed
        # by the reset_peer_stats
        self.assertEqual(stats3, stats4)

    def test_node_clone(self):
        # Test making a clone of the node, it should have the same
        # Identifier and NetAddress, but will be different node objects
        node = self._create_node()
        twin = node._clone()
        self.assertEqual(node.Identifier, twin.Identifier)
        self.assertEqual(node.NetAddress, twin.NetAddress)
