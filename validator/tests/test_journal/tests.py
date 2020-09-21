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

# pylint: disable=too-many-lines
# pylint: disable=pointless-statement
# pylint: disable=protected-access
# pylint: disable=unbalanced-tuple-unpacking
# pylint: disable=arguments-differ

import logging
import unittest.mock

from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.timed_cache import TimedCache
from sawtooth_validator.journal.event_extractors \
    import BlockEventExtractor
from sawtooth_validator.journal.event_extractors \
    import ReceiptEventExtractor

from sawtooth_validator.server.events.subscription import EventSubscription
from sawtooth_validator.server.events.subscription import EventFilterFactory

from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.transaction_receipt_pb2 import \
    TransactionReceipt
from sawtooth_validator.protobuf.transaction_receipt_pb2 import StateChange
from sawtooth_validator.protobuf.transaction_receipt_pb2 import StateChangeList
from sawtooth_validator.protobuf.events_pb2 import Event
from sawtooth_validator.protobuf.events_pb2 import EventFilter


LOGGER = logging.getLogger(__name__)


class TestTimedCache(unittest.TestCase):
    def test_cache(self):
        bc = TimedCache(keep_time=1, purge_frequency=0)

        with self.assertRaises(KeyError):
            bc["test"]

        bc["test"] = "value"

        self.assertEqual(len(bc), 1)

        del bc["test"]
        self.assertFalse("test" in bc)

    def test_evict_expired(self):
        """ Test that values will be evicted from the
        cache as they time out.
        """

        # use an invasive technique so that we don't have to sleep for
        # the item to expire

        bc = TimedCache(keep_time=1, purge_frequency=0)

        bc["test"] = "value"
        bc["test2"] = "value2"
        self.assertEqual(len(bc), 2)

        # test that expired item i
        bc.cache["test"].timestamp = bc.cache["test"].timestamp - 2
        bc["test2"] = "value2"  # set value to activate purge
        self.assertEqual(len(bc), 1)
        self.assertFalse("test" in bc)
        self.assertTrue("test2" in bc)

    def test_access_update(self):

        bc = TimedCache(keep_time=1, purge_frequency=0)

        bc["test"] = "value"
        bc["test2"] = "value2"
        self.assertEqual(len(bc), 2)

        bc["test"] = "value"
        bc.cache["test"].timestamp = bc.cache["test"].timestamp - 2
        bc["test"]  # access to update timestamp
        bc["test2"] = "value2"  # set value to activate purge
        self.assertEqual(len(bc), 2)
        self.assertTrue("test" in bc)
        self.assertTrue("test2" in bc)


class TestBlockEventExtractor(unittest.TestCase):
    def test_block_event_extractor(self):
        """Test that a sawtooth/block-commit event is generated correctly."""
        block_header = BlockHeader(
            block_num=85,
            state_root_hash="0987654321fedcba",
            previous_block_id="0000000000000000")
        block = BlockWrapper(Block(
            header_signature="abcdef1234567890",
            header=block_header.SerializeToString()))
        extractor = BlockEventExtractor(block)
        events = extractor.extract([EventSubscription(
            event_type="sawtooth/block-commit")])
        self.assertEqual(events, [
            Event(
                event_type="sawtooth/block-commit",
                attributes=[
                    Event.Attribute(key="block_id", value="abcdef1234567890"),
                    Event.Attribute(key="block_num", value="85"),
                    Event.Attribute(
                        key="state_root_hash", value="0987654321fedcba"),
                    Event.Attribute(
                        key="previous_block_id",
                        value="0000000000000000")])])


class TestReceiptEventExtractor(unittest.TestCase):
    def test_tf_events(self):
        """Test that tf events are generated correctly."""
        gen_data = [
            ["test1", "test2"],
            ["test3"],
            ["test4", "test5", "test6"],
        ]
        event_sets = [
            [
                Event(event_type=event_type)
                for event_type in events
            ] for events in gen_data
        ]
        receipts = [
            TransactionReceipt(events=events)
            for events in event_sets
        ]
        extractor = ReceiptEventExtractor(receipts)

        events = extractor.extract([])
        self.assertEqual([], events)

        events = extractor.extract([
            EventSubscription(event_type="test1"),
            EventSubscription(event_type="test5"),
        ])
        self.assertEqual(events, [event_sets[0][0], event_sets[2][1]])

    def test_state_delta_events(self):
        """Test that sawtooth/state-delta events are generated correctly."""
        gen_data = [
            [("a", b"a", StateChange.SET), ("b", b"b", StateChange.DELETE)],
            [("a", b"a", StateChange.DELETE), ("d", b"d", StateChange.SET)],
            [("e", b"e", StateChange.SET)],
        ]
        change_sets = [
            [
                StateChange(address=address, value=value, type=change_type)
                for address, value, change_type in state_changes
            ] for state_changes in gen_data
        ]
        receipts = [
            TransactionReceipt(state_changes=state_changes)
            for state_changes in change_sets
        ]
        extractor = ReceiptEventExtractor(receipts)

        factory = EventFilterFactory()
        events = extractor.extract([
            EventSubscription(
                event_type="sawtooth/state-delta",
                filters=[factory.create("address", "a")]),
            EventSubscription(
                event_type="sawtooth/state-delta",
                filters=[factory.create(
                    "address", "[ce]", EventFilter.REGEX_ANY)],
            )
        ])
        self.assertEqual(events, [Event(
            event_type="sawtooth/state-delta",
            attributes=[
                Event.Attribute(key="address", value=address)
                for address in ["e", "d", "a", "b"]
            ],
            data=StateChangeList(state_changes=[
                change_sets[2][0], change_sets[1][1],
                change_sets[1][0], change_sets[0][1],
            ]).SerializeToString(),
        )])
