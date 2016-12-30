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

from gossip.node import TransmissionQueue, Node
from gossip.message import Message


class TestRoundTripEstimator(unittest.TestCase):

    # Helper functions for creating the test
    def _create_node(self):
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", 8800))
        node.is_peer = True
        return node

    def _create_msg(self):
        node = self._create_node()
        msg = Message()
        msg.sign_from_node(node)
        return msg

    def test_tranmission_queue_init(self):
        # Test init of TransmissionQueue
        tQ = TransmissionQueue()
        self.assertEqual(tQ._messages, {})
        self.assertEqual(tQ._times, {})
        self.assertEqual(tQ._heap, [])

    def test_tranmission_queue_str(self):
        # Test overridden string function
        tQ = TransmissionQueue()
        now = time.time()
        node = self._create_node()
        for i in range(3):
            msg = self._create_msg()
            tQ.enqueue_message(msg, now)
        idlist = tQ._times.keys()
        # Should return a string with all 3 msgs
        self.assertEqual(str(tQ), '[' + ', '
                         .join([ident[:8] for ident in idlist]) + ']')
        for i in range(4):
            msg = self._create_msg()
            tQ.enqueue_message(msg, now)
        idlist = tQ._times.keys()
        idlist = idlist[:4]
        idlist.append('...')
        # Should return a string with the first 4 msgs and ... at the end
        self.assertEqual(str(tQ), '[' + ', '
                         .join([ident[:8] for ident in idlist]) + ']')

    def test_tranmission_queue_enqueue_message(self):
        # Test Enqueuing a message
        tQ = TransmissionQueue()
        now = time.time()
        node = self._create_node()
        msg = self._create_msg()
        # Enqueue 1 message
        tQ.enqueue_message(msg, now)
        self.assertIn(msg.Identifier, tQ._messages)
        self.assertIn(msg.Identifier, tQ._times)
        self.assertIn((now, msg.Identifier), tQ._heap)
        # Enqueue 10 messages
        for i in range(10):
            msg = self._create_msg()
            tQ.enqueue_message(msg, now)
        self.assertEqual(len(tQ._messages), 11)

    def test_tranmission_queue_enqueue_message_duplicates(self):
        # Test Enqueuing a message, try to enqueue twice
        tQ = TransmissionQueue()
        now = time.time()
        node = self._create_node()
        msg = self._create_msg()
        tQ.enqueue_message(msg, now)
        self.assertIn(msg.Identifier, tQ._messages)
        self.assertIn(msg.Identifier, tQ._times)
        self.assertIn((now, msg.Identifier), tQ._heap)
        # Trying to enqueue the same message twice should throw an
        # AssertionError
        try:
            tQ.enqueue_message(msg, now)
            self.fail("This should throw an assertionError")
        except AssertionError, e:
            self.assertFalse(msg.Identifier not in tQ._messages)
            self.assertFalse(msg.Identifier not in tQ._times)

    def test_tranmission_queue_dequeue_message(self):
        # Test that a message can be dequeued correctly
        tQ = TransmissionQueue()
        now = time.time()
        node = self._create_node()
        msg = self._create_msg()
        # Add a message to the queue
        tQ.enqueue_message(msg, now)
        self.assertIn(msg.Identifier, tQ._messages)
        self.assertIn(msg.Identifier, tQ._times)
        self.assertIn((now, msg.Identifier), tQ._heap)
        # Dequeue message we just added
        tQ.dequeue_message(msg)
        self.assertNotIn(msg.Identifier, tQ._messages)
        self.assertNotIn(msg.Identifier, tQ._times)
        self.assertNotIn((now, msg.Identifier), tQ._heap)
        # Test that if we try to dequeue a message that is not in the queue
        # That is does not break the test
        tQ.dequeue_message(msg)
        self.assertNotIn(msg.Identifier, tQ._messages)
        self.assertNotIn(msg.Identifier, tQ._times)
        self.assertNotIn((now, msg.Identifier), tQ._heap)

    def test_tranmission_queue_head(self):
        # Test head property of transmission Queue
        tQ = TransmissionQueue()
        now = time.time()
        node = self._create_node()
        msg = self._create_msg()
        # Should return none, since no messages in queue
        head = tQ.Head
        self.assertIsNone(head)
        # Add a message to the queue
        tQ.enqueue_message(msg, now)
        # Return the time and message at the head
        head = tQ.Head
        self.assertEqual(head[0], now)
        self.assertEqual(head[1], msg)

    def test_tranmission_queue_count(self):
        # Test property count of TransmissionQueue
        tQ = TransmissionQueue()
        now = time.time()
        node = self._create_node()
        msg = self._create_msg()
        # 0 messages in queue
        self.assertEqual(tQ.Count, 0)
        tQ.enqueue_message(msg, now)
        # 1 message in queue
        self.assertEqual(tQ.Count, 1)
        msg2 = self._create_msg()
        tQ.enqueue_message(msg2, now)
        # 2 messages in queue
        self.assertEqual(tQ.Count, 2)
        tQ.dequeue_message(msg)
        # Dequeue message from queue, leaving 1 message
        self.assertEqual(tQ.Count, 1)

    def test_tranmission_queue_messages(self):
        # Test the Message property of TransmissionQueue
        tQ = TransmissionQueue()
        now = time.time()
        node = self._create_node()
        msg = self._create_msg()
        # No messages
        self.assertEqual(tQ.Messages, [])
        tQ.enqueue_message(msg, now)
        # 1 message
        self.assertEqual(tQ.Messages, [msg.Identifier])
        msg2 = self._create_msg()
        # 2 messages, check if messages id are in Messages
        tQ.enqueue_message(msg2, now)
        self.assertIn(msg2.Identifier, tQ.Messages)
        self.assertIn(msg.Identifier, tQ.Messages)

    def test_tranmission_queue_trimheap(self):
        # Test _trimheap, remove messages that are no longer valid
        tQ = TransmissionQueue()
        now = time.time()
        node = self._create_node()
        msg = self._create_msg()
        # Test the _trimheap doesn't break on empty heap
        tQ._trimheap()
        self.assertEqual(tQ._heap, [])
        tQ.enqueue_message(msg, now)
        tQ._trimheap()
        # Should not have changed anything
        self.assertEqual(tQ._heap, [(now, msg.Identifier)])
        # Change time to send in times, but not in heap, this makes it invalid
        tQ._times[msg.Identifier] = 0.0
        tQ._trimheap()
        self.assertEqual(tQ._heap, [])

    def test_tranmission_queue_buildheap(self):
        # Test buildheap, cleans up the heap when a large number of
        # messages have been dequeued
        tQ = TransmissionQueue()
        now = time.time()
        node = self._create_node()
        # Add 10 messages to the queue
        for i in range(10):
            msg = self._create_msg()
            tQ.enqueue_message(msg, now)
        before = str(tQ._heap)
        # Should not change the heap, no messages have been dequeued
        tQ._buildheap()
        after = str(tQ._heap)
        self.assertEqual(before, after)

        before = str(tQ._heap)
        for i in range(7):
            # Remove 7 messages from queue
            # not using dequeue_message so that buildheap() won't be called
            msgId = tQ._messages.keys().pop()
            tQ._messages.pop(msgId, None)
            tQ._times.pop(msgId, None)
        # The heap has not changed, even though 7 messages have been "dequeued"
        after = str(tQ._heap)
        self.assertEqual(before, after)
        # The heap is cleaned up and left with only the 3 messages.
        tQ._buildheap()
        after = str(tQ._heap)
        self.assertNotEqual(before, after)
        self.assertEqual(len(tQ._heap), 3)
