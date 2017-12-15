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
# ------------------------------------------------------------------------------

import time
import unittest
import logging

from test_journal.mock import MockStateViewFactory
from test_client_request_handlers.mocks import MockBlockStore
from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.journal.consensus.dev_mode.dev_mode_consensus \
    import BlockPublisher
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.state.settings_view import SettingsView
from sawtooth_validator.protobuf.setting_pb2 import Setting

LOGGER = logging.getLogger(__name__)


class TestCheckPublishBlock(unittest.TestCase):
    def create_block_header(self, signer_public_key=None):
        return BlockHeader(signer_public_key=signer_public_key)

    def create_state_view_factory(self, values):
        state_db = {}
        if values is not None:
            for key, value in values.items():
                state_db[SettingsView.setting_address(key)] = \
                    TestCheckPublishBlock._setting_entry(key, repr(value))

        return MockStateViewFactory(state_db)

    def test_default_settings(self):
        factory = self.create_state_view_factory(values=None)

        dev_mode = \
            BlockPublisher(
                block_cache=BlockCache(block_store=MockBlockStore()),
                state_view_factory=factory,
                batch_publisher=None,
                data_dir=None,
                config_dir=None,
                validator_id='Validator_001')

        block_header = self.create_block_header()

        self.assertTrue(dev_mode.check_publish_block(block_header))

    def test_min_wait_time(self):
        # non zero value of min wait time
        factory = self.create_state_view_factory(
            {"sawtooth.consensus.min_wait_time": 1
             })
        dev_mode = \
            BlockPublisher(
                block_cache=BlockCache(block_store=MockBlockStore()),
                state_view_factory=factory,
                batch_publisher=None,
                data_dir=None,
                config_dir=None,
                validator_id='Validator_001')
        block_header = self.create_block_header()

        dev_mode.initialize_block(block_header)

        self.assertFalse(dev_mode.check_publish_block(block_header))
        time.sleep(1)
        self.assertTrue(dev_mode.check_publish_block(block_header))

    def test_max_wait_time(self):
        pass

    def test_min_and_max_wait_time(self):
        pass

    def test_in_valid_block_publisher_list(self):
        factory = self.create_state_view_factory({
            "sawtooth.consensus.valid_block_publisher": ["name"]

        })
        dev_mode = \
            BlockPublisher(
                block_cache=BlockCache(block_store=MockBlockStore()),
                state_view_factory=factory,
                batch_publisher=None,
                data_dir=None,
                config_dir=None,
                validator_id='Validator_001')
        block_header = self.create_block_header("name")
        self.assertTrue(dev_mode.check_publish_block(block_header))

    def test_not_in_valid_block_publisher_list(self):
        factory = self.create_state_view_factory({})
        dev_mode = \
            BlockPublisher(
                block_cache=BlockCache(block_store=MockBlockStore()),
                state_view_factory=factory,
                batch_publisher=None,
                data_dir=None,
                config_dir=None,
                validator_id='Validator_001')
        block_header = self.create_block_header("name")
        self.assertTrue(dev_mode.check_publish_block(block_header))

    @staticmethod
    def _setting_entry(key, value):
        return Setting(
            entries=[Setting.Entry(key=key, value=value)]
        ).SerializeToString()
