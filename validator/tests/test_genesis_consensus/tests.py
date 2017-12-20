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
from unittest.mock import Mock

from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.consensus.genesis.genesis_consensus import \
    BlockPublisher
from sawtooth_validator.journal.consensus.genesis.genesis_consensus import \
    BlockVerifier

from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.protobuf.block_pb2 import BlockHeader


class TestGenesisBlockPublisher(unittest.TestCase):
    def test_initialize_block(self):
        """
        Create a block header and initialize it using the genesis consensus
        BlockPublisher.

        This test should verify that the appropriate header fields are set and
        the consensus module returns that the block should be built.
        """
        block_cache = Mock()
        state_view_factory = Mock()
        batch_publisher = Mock()
        data_dir = 'mock_dir'
        config_dir = 'mock_dir'
        validator_id = 'validator_001'
        block_publisher = BlockPublisher(block_cache,
                                         state_view_factory,
                                         batch_publisher,
                                         data_dir,
                                         config_dir,
                                         validator_id)

        block_header = BlockHeader(
            previous_block_id=NULL_BLOCK_IDENTIFIER)

        result = block_publisher.initialize_block(block_header)
        self.assertTrue(result)
        self.assertEqual(b'Genesis', block_header.consensus)

    def test_check_publish_valid(self):
        """
        Create a block header with the NULL_BLOCK_IDENTIFIER as previous id and
        check that it can be published.

        This test should verify that only blocks with the NULL_BLOCK_IDENTIFIER
        as previous should be allowed to be published with this consensus
        module.
        """
        block_cache = Mock()
        state_view_factory = Mock()
        batch_publisher = Mock()
        data_dir = 'mock_dir'
        config_dir = 'mock_dir'
        validator_id = 'validator_001'
        block_publisher = BlockPublisher(block_cache,
                                         state_view_factory,
                                         batch_publisher,
                                         data_dir,
                                         config_dir,
                                         validator_id)

        block_header = BlockHeader(
            consensus=b'Genesis',
            previous_block_id=NULL_BLOCK_IDENTIFIER)

        result = block_publisher.check_publish_block(block_header)
        self.assertTrue(result)

    def test_check_publish_invalid(self):
        """
        Create a block header with some other block id as the previous id and
        check that it can be published.

        This test should verify that only blocks with the NULL_BLOCK_IDENTIFIER
        as previous should be allowed to be published with this consensus
        module.
        """
        block_cache = Mock()
        state_view_factory = Mock()
        batch_publisher = Mock()
        data_dir = 'mock_dir'
        config_dir = 'mock_dir'
        validator_id = 'validator_001'
        block_publisher = BlockPublisher(block_cache,
                                         state_view_factory,
                                         batch_publisher,
                                         data_dir,
                                         config_dir,
                                         validator_id)

        block_header = BlockHeader(
            consensus=b'Genesis',
            previous_block_id='some_other_id')

        result = block_publisher.check_publish_block(block_header)
        self.assertFalse(result)

    def test_finalize_block_valid(self):
        """
        Create a block header with the NULL_BLOCK_IDENTIFIER as the previous id
        and check that it can be properly finalized.

        This test should verify that only blocks with the NULL_BLOCK_IDENTIFIER
        as previous should be allowed to be finalized with this consensus
        module.
        """
        block_cache = Mock()
        state_view_factory = Mock()
        batch_publisher = Mock()
        data_dir = 'mock_dir'
        config_dir = 'mock_dir'
        validator_id = 'validator_001'
        block_publisher = BlockPublisher(block_cache,
                                         state_view_factory,
                                         batch_publisher,
                                         data_dir,
                                         config_dir,
                                         validator_id)

        block_header = BlockHeader(
            consensus=b'Genesis',
            previous_block_id=NULL_BLOCK_IDENTIFIER)

        result = block_publisher.finalize_block(block_header)
        self.assertTrue(result)

    def test_finalize_block_invalid(self):
        """
        Create a block header with some other block id as the previous id
        and check that it can be properly finalized.

        This test should verify that only blocks with the NULL_BLOCK_IDENTIFIER
        as previous should be allowed to be finalized with this consensus
        module.
        """
        block_cache = Mock()
        state_view_factory = Mock()
        batch_publisher = Mock()
        data_dir = 'mock_dir'
        config_dir = 'mock_dir'
        validator_id = 'validator_001'
        block_publisher = BlockPublisher(block_cache,
                                         state_view_factory,
                                         batch_publisher,
                                         data_dir,
                                         config_dir,
                                         validator_id)

        block_header = BlockHeader(
            consensus=b'Genesis',
            previous_block_id='some_other_id')

        result = block_publisher.finalize_block(block_header)
        self.assertFalse(result)


class TestGenesisBlockVerifier(unittest.TestCase):
    def test_verify_genesis_block(self):
        """This test should verify that a block with the NULL_BLOCK_IDENTIFIER
        should be considered a valid block using this consensus module.
        """
        block_cache = Mock()
        state_view_factory = Mock()
        data_dir = 'mock_dir'
        config_dir = 'mock_dir'
        validator_id = 'validator_001'
        block_verifier = BlockVerifier(block_cache,
                                       state_view_factory,
                                       data_dir,
                                       config_dir,
                                       validator_id)

        block = Block(header=BlockHeader(
            previous_block_id=NULL_BLOCK_IDENTIFIER).SerializeToString())
        block_wrapper = BlockWrapper(block)

        result = block_verifier.verify_block(block_wrapper)
        self.assertTrue(result)

    def test_reject_non_genesis_block(self):
        """This test should show that a block with any previous blocks should
        fail verification.
        """
        block_cache = Mock()
        state_view_factory = Mock()
        data_dir = 'mock_dir'
        config_dir = 'mock_dir'
        validator_id = 'validator_001'
        block_verifier = BlockVerifier(block_cache,
                                       state_view_factory,
                                       data_dir,
                                       config_dir,
                                       validator_id)

        block = Block(header=BlockHeader(
            previous_block_id='some_prev_block_id').SerializeToString())
        block_wrapper = BlockWrapper(block)

        result = block_verifier.verify_block(block_wrapper)
        self.assertFalse(result)
