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

import unittest
import logging
from unittest.mock import patch

from test_consensus.mock_validator_registry_view import MockValidatorRegistryView
from sawtooth_poet.poet_consensus import BlockVerifier
from tests.unit3.test_journal.mock import MockStateViewFactory
from tests.unit3.test_client_request_handlers.mocks import MockBlockStore
from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.state.config_view import ConfigView
from sawtooth_validator.protobuf.setting_pb2 import Setting
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.journal.block_wrapper import BlockStatus

LOGGER = logging.getLogger(__name__)

class TestPoetBlockVerifier(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_validators = None
        self._temp_val_info = None

    def create_block_wrapper(self):
        block = Block()
        return BlockWrapper(status=BlockStatus.Valid,
                block=block, weight=0,)

    def create_state_view_factory(self, values):
        state_db = {}
        if values is not None:
            for key, value in values.items():
                state_db[ConfigView.setting_address(key)] = \
                    TestPoetBlockVerifier._setting_entry(key, repr(value))
        return MockStateViewFactory(state_db)

    @patch('sawtooth_poet.poet_consensus.poet_block_verifier.ValidatorRegistryView')
    def test_verify_block(self, mock_validatorregistryview):
        mock_validatorregistryview.return_value = MockValidatorRegistryView({})

        factory = self.create_state_view_factory(values=None)
        block_wrapper = self.create_block_wrapper()

        poet_block_verifier = \
            BlockVerifier(
                block_cache=BlockCache(block_store=MockBlockStore()),
                state_view_factory=factory,
                data_dir=None)

        self.assertTrue(poet_block_verifier.verify_block(block_wrapper))


    @patch('sawtooth_poet.poet_consensus.poet_block_verifier.ValidatorRegistryView')
    def test_verify_block_no_signer_pubkey(self, mock_ValidatorRegistryView):
        mock_ValidatorRegistryView.return_value = MockValidatorRegistryView({})
        poet_block_verifier = BlockVerifier(block_cache=None, state_view_factory=None, data_dir=None)

    # def test_verify_block_wait_certificate (self, )

    @staticmethod
    def _setting_entry(key, value):
        return Setting(
            entries=[Setting.Entry(key=key, value=value)]
        ).SerializeToString()