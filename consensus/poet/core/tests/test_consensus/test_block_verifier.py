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
import json
from unittest.mock import patch

from test_consensus.mock_block_verifier import MockValidatorRegistryView
from test_consensus.mock_block_verifier import MockCreateWaitCertificate
from sawtooth_poet.poet_consensus import BlockVerifier
from tests.unit3.test_journal.mock import MockStateViewFactory
from tests.unit3.test_client_request_handlers.mocks import MockBlockStore
from sawtooth_validator.journal.block_cache import BlockCache
from sawtooth_validator.state.config_view import ConfigView
from sawtooth_validator.protobuf.setting_pb2 import Setting
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.journal.block_wrapper import BlockStatus
from sawtooth_poet.poet_consensus import utils
from sawtooth_poet.poet_consensus import poet_enclave_factory as factory
from test_validator_registry_view.mocks import MockStateView
from test_validator_registry_view.utils import to_address
from sawtooth_poet_common.protobuf.validator_registry_pb2 import ValidatorInfo
from sawtooth_poet_common.protobuf.validator_registry_pb2 import SignUpInfo
from sawtooth_poet.poet_consensus.wait_timer import WaitTimer
from sawtooth_poet.poet_consensus.wait_certificate import WaitCertificate
from sawtooth_validator.protobuf.block_pb2 import BlockHeader

LOGGER = logging.getLogger(__name__)

class TestPoetBlockVerifier(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_validators = None
        self._temp_val_info = None

    def create_block_wrapper(self):
        block = Block()
        block_wrapper = BlockWrapper(status=BlockStatus.Valid,
                block=block, weight=0)
        return block_wrapper


    def create_block_header(self, signer_pubkey=None):
        return BlockHeader(signer_pubkey=signer_pubkey)

    def create_state_view_factory(self, values):
        state_db = {}
        if values is not None:
            for key, value in values.items():
                state_db[ConfigView.setting_address(key)] = \
                    TestPoetBlockVerifier._setting_entry(key, repr(value))
        return MockStateViewFactory(state_db)


    @patch('sawtooth_poet.poet_consensus.poet_block_verifier.ValidatorRegistryView')
    def test_verify_block_empty_validator_registry_view(self, mock_validator_registry_view):
        mock_validator_registry_view.return_value = MockValidatorRegistryView({})

        factory = self.create_state_view_factory(values=None)
        block_wrapper = self.create_block_wrapper()

        poet_block_verifier = \
            BlockVerifier(
                block_cache=BlockCache(block_store=MockBlockStore()),
                state_view_factory=factory,
                data_dir=None)

        self.assertTrue(poet_block_verifier.verify_block(block_wrapper))


    @patch('sawtooth_poet.poet_consensus.poet_block_verifier.ValidatorRegistryView')
    def test_verify_block_wait_certificate_bad_consensus(self, mock_validator_registry_view):
        mock_validator_registry_view.return_value = MockValidatorRegistryView({})

        block_wrapper = self.create_block_wrapper()
        block_wrapper.header.consensus = b"bad data"

        LOGGER.info('block_wrapper.consensus: %s', block_wrapper.consensus)
        factory = self.create_state_view_factory(values=None)

        poet_block_verifier = \
            BlockVerifier(
                block_cache=BlockCache(block_store=MockBlockStore()),
                state_view_factory=factory,
                data_dir=None)

        self.assertFalse(poet_block_verifier.verify_block(block_wrapper))


    @patch('sawtooth_poet.poet_consensus.poet_block_verifier.ValidatorRegistryView')
    def test_verify_block_wait_certificate_is_none(self, mock_validator_registry_view):
        mock_validator_registry_view.return_value = MockValidatorRegistryView({})

        block_wrapper = self.create_block_wrapper()
        wait_certificate = MockCreateWaitCertificate().create_wait_certificate()

        factory = self.create_state_view_factory(values=None)

        poet_block_verifier = \
            BlockVerifier(
                block_cache=BlockCache(block_store=MockBlockStore()),
                state_view_factory=factory,
                data_dir=None)

        self.assertFalse(poet_block_verifier.verify_block(block_wrapper))


    @patch('sawtooth_poet.poet_consensus.poet_block_verifier.ValidatorRegistryView')
    def test_verify_block_wait_certificate_check_valid(self, mock_validator_registry_view):
        mock_validator_registry_view.return_value = MockValidatorRegistryView({})

        block_wrapper = self.create_block_wrapper()
        wait_certificate = MockCreateWaitCertificate().create_wait_certificate()
        LOGGER.info('wait_certificate: %s', wait_certificate)
        check_valid = MockCreateWaitCertificate().wait_certificate_check_valid()
        LOGGER.info('wait_certificate.check_valid: %s', check_valid)

        factory = self.create_state_view_factory(values=None)
        poet_block_verifier = \
            BlockVerifier(
                block_cache=BlockCache(block_store=MockBlockStore()),
                state_view_factory=factory,
                data_dir=None)

        self.assertFalse(poet_block_verifier.verify_block(block_wrapper))


    @staticmethod
    def _setting_entry(key, value):
        return Setting(
            entries=[Setting.Entry(key=key, value=value)]
        ).SerializeToString()
