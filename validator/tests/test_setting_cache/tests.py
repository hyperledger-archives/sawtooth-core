# Copyright 2017 Intel Corporation
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
# ----------------------------------------------------------------------------
import unittest

from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.events_pb2 import Event
from sawtooth_validator.protobuf.transaction_receipt_pb2 import \
    TransactionReceipt
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.state.settings_cache import SettingsCache
from sawtooth_validator.state.settings_cache import SettingsObserver
from test_setting_cache.mocks import MockSettingsViewFactory


class TestSettingsObserver(unittest.TestCase):
    def setUp(self):
        self._settings_view_factory = MockSettingsViewFactory()
        self._settings_cache = SettingsCache(
            self._settings_view_factory,
        )
        self._settings_obsever = SettingsObserver(
            to_update=self._settings_cache.invalidate,
            forked=self._settings_cache.forked
        )
        self._state_root_func = lambda: "state_root"

        # Make sure SettingsCache has populated settings
        self._settings_view_factory.add_setting("setting1", "test")

    def create_block(self, previous_block_id="0000000000000000"):
        block_header = BlockHeader(
            block_num=85,
            state_root_hash="0987654321fedcba",
            previous_block_id=previous_block_id)
        block = BlockWrapper(
            Block(
                header_signature="abcdef1234567890",
                header=block_header.SerializeToString()))
        return block

    def test_chain_update(self):
        """
        Test that if there is no fork and only one value is updated, only
        that value is in validated in the catch.
        """
        # Set up cache so it does not fork
        block1 = self.create_block()
        self._settings_obsever.chain_update(block1, [])
        self._settings_cache.get_setting("setting1", self._state_root_func)
        self.assertNotEqual(self._settings_cache["setting1"], None)

        # Add next block and event that says network was updated.
        block2 = self.create_block("abcdef1234567890")
        event = Event(
            event_type="settings/update",
            attributes=[Event.Attribute(key="updated", value="setting1")])
        receipts = TransactionReceipt(events=[event])
        self._settings_obsever.chain_update(block2, [receipts])
        # Check that only "network" was invalidated
        self.assertEqual(self._settings_cache["setting"], None)

        # check that the correct values can be fetched from state.
        settings_view = \
            self._settings_view_factory.create_settings_view("state_root")

        self.assertEqual(
            self._settings_cache.get_setting(
                "setting1", self._state_root_func),
            settings_view.get_setting("setting1"))

    def test_fork(self):
        """
        Test that if there is a fork, all values in the cache will be
        invalidated and fetched from state.
        """
        block = self.create_block()
        self._settings_obsever.chain_update(block, [])
        # Check that all items are invalid
        for key in self._settings_cache:
            self.assertEqual(self._settings_cache[key], None)

        # Check that the items can be fetched from state.
        settings_view = \
            self._settings_view_factory.create_settings_view("state_root")

        self.assertEqual(
            self._settings_cache.get_setting(
                "setting1", self._state_root_func),
            settings_view.get_setting("setting1"))


class TestSettingsCache(unittest.TestCase):
    def setUp(self):
        self._settings_view_factory = MockSettingsViewFactory()
        self._settings_cache = SettingsCache(
            self._settings_view_factory,
        )
        self._state_root_func = lambda: "state_root"

    def test_get_settings(self):
        """
        Test that a setting can be fetched from the state.
        """
        self._settings_view_factory.add_setting("setting1", "test")
        self.assertIsNone(self._settings_cache["setting1"])

        settings_view = \
            self._settings_view_factory.create_settings_view("state_root")
        self.assertEqual(
            self._settings_cache.get_setting(
                "setting1", self._state_root_func),
            settings_view.get_setting("setting1"))

    def test_setting_invalidate(self):
        """
        Test that a setting can be invalidated.
        """
        self._settings_view_factory.add_setting("setting1", "test")
        self._settings_cache.invalidate("setting1")

        self.assertEqual(self._settings_cache["setting2"], None)

        settings_view = \
            self._settings_view_factory.create_settings_view("state_root")
        self.assertEqual(
            self._settings_cache.get_setting(
                "setting1", self._state_root_func),
            settings_view.get_setting("setting1"))

    def test_forked(self):
        """
        Test that forked() invalidates all items in the cache, and they can
        be fetched from state.
        """
        self._settings_view_factory.add_setting("setting1", "test1")
        self._settings_view_factory.add_setting("setting2", "test2")

        settings_view = \
            self._settings_view_factory.create_settings_view("state_root")

        self._settings_cache.get_setting("setting1", lambda: "test1")
        self._settings_cache.get_setting("setting2", lambda: "test2")

        self.assertEqual(len(self._settings_cache), 2)
        self._settings_cache.forked()

        self.assertEqual(self._settings_cache["setting1"], None)
        self.assertEqual(self._settings_cache["setting2"], None)

        self.assertEqual(
            self._settings_cache.get_setting(
                "setting1", self._state_root_func),
            settings_view.get_setting("setting1"))

        self.assertEqual(
            self._settings_cache.get_setting(
                "setting2", self._state_root_func),
            settings_view.get_setting("setting2"))
