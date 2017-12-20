# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributepd on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

from sawtooth_validator.server.events.extractor import EventExtractor
from sawtooth_validator.protobuf.events_pb2 import Event
from sawtooth_validator.protobuf.transaction_receipt_pb2 import StateChangeList


class BlockEventExtractor(EventExtractor):
    def __init__(self, block):
        self._block = block

    def _make_event(self):
        block = self._block
        attributes = [
            Event.Attribute(key="block_id", value=block.identifier),
            Event.Attribute(key="block_num", value=str(block.block_num)),
            Event.Attribute(
                key="state_root_hash", value=block.state_root_hash),
            Event.Attribute(
                key="previous_block_id", value=block.previous_block_id)]
        return Event(event_type="sawtooth/block-commit", attributes=attributes)

    def extract(self, subscriptions):
        if subscriptions:
            for sub in subscriptions:
                if sub.event_type == "sawtooth/block-commit":
                    return [self._make_event()]

        return None


class ReceiptEventExtractor(EventExtractor):
    def __init__(self, receipts):
        self._receipts = receipts

    def extract(self, subscriptions):
        if not subscriptions:
            return []
        events = []
        events.extend(self._make_receipt_events(subscriptions))
        events.extend(self._make_state_delta_events(subscriptions))
        return events

    def _make_receipt_events(self, subscriptions):
        events = []
        for receipt in self._receipts:
            for event in receipt.events:
                for subscription in subscriptions:
                    if event in subscription:
                        events.append(event)
        return events

    def _make_state_delta_events(self, subscriptions):
        gen = False
        for subscription in subscriptions:
            if subscription.event_type == "sawtooth/state-delta":
                gen = True

        if not gen:
            return []

        addresses = set()
        attributes = []
        squashed_changes = []
        for receipt in reversed(self._receipts):
            for state_change in reversed(receipt.state_changes):
                address = state_change.address
                if address not in addresses:
                    addresses.add(address)
                    attributes.append(
                        Event.Attribute(key="address", value=address))
                    squashed_changes.append(state_change)

        state_change_list = StateChangeList()
        state_change_list.state_changes.extend(squashed_changes)

        event = Event(
            event_type="sawtooth/state-delta",
            attributes=attributes,
            data=state_change_list.SerializeToString())

        for subscription in subscriptions:
            if event in subscription:
                return [event]

        # Event not in subscriptions
        return []
