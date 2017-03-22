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
from sawtooth_validator.journal.consensus.dev_mode.dev_mode_consensus\
    import BlockPublisher
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.state.config_view import ConfigView
from sawtooth_validator.protobuf.setting_pb2 import Setting

LOGGER = logging.getLogger(__name__)

class TestCheckPublishBlock(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)

    def create_block_header(self, signer_pubkey=None):
        return BlockHeader(signer_pubkey=signer_pubkey)

    def create_state_view(self, values):
        state_db = {}
        if values is not None:
            for key, value in values.items():
                state_db[ConfigView.setting_address(key)] = \
                    TestCheckPublishBlock._setting_entry(key, repr(value))

        state_view_factory = MockStateViewFactory(state_db)
        state_view = state_view_factory.create_view(None)
        return state_view

    def test_default_settings(self):
        state = self.create_state_view(values=None)

        dev_mode = BlockPublisher(None, state,
                                  data_dir=None, batch_publisher = None)

        block_header = self.create_block_header()

        self.assertTrue(dev_mode.check_publish_block(block_header))

    def test_min_wait_time(self):
        # non zero value of min wait time
        state = self.create_state_view(
            {"sawtooth.consensus.min_wait_time": 1
             })
        dev_mode = BlockPublisher(None, state, batch_publisher=None, data_dir=None)
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
        state = self.create_state_view({
            "sawtooth.consensus.valid_block_publisher": ["name"]

        })
        dev_mode = BlockPublisher(None, state, batch_publisher=None, data_dir=None)
        block_header = self.create_block_header("name")
        self.assertTrue(dev_mode.check_publish_block(block_header))

    def test_not_in_valid_block_publisher_list(self):
        state = self.create_state_view({})
        dev_mode = BlockPublisher(None, state, batch_publisher=None, data_dir=None)
        block_header = self.create_block_header("name")
        self.assertTrue(dev_mode.check_publish_block(block_header))

    @staticmethod
    def _setting_entry(key, value):
        return Setting(
            entries=[Setting.Entry(key=key, value=value)]
        ).SerializeToString()
