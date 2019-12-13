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

import unittest

from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.block_pb2 import Block
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.validation_rule_enforcer import \
    enforce_validation_rules
from test_validation_rule_enforcer.mock import MockSettingsViewFactory


class ValidationRuleEnforcerTest(unittest.TestCase):
    def setUp(self):
        self._settings_view_factory = MockSettingsViewFactory()

    def _settings_view(self):
        return self._settings_view_factory.create_settings_view(
            "state_root")

    def _make_block(self, txns_family, signer_public_key,
                    same_public_key=True):
        transactions = []
        for family in txns_family:
            txn_header = TransactionHeader(
                family_name=family,
                signer_public_key=signer_public_key)
            txn = Transaction(header=txn_header.SerializeToString())
            transactions.append(txn)

        batch = Batch(transactions=transactions)
        if same_public_key:
            block_header = BlockHeader(signer_public_key=signer_public_key)
        else:
            block_header = BlockHeader(signer_public_key="other")
        block = Block(header=block_header.SerializeToString(), batches=[batch])
        return BlockWrapper(block)

    def test_no_setting(self):
        """
        Test that if no validation rules are set, the block is valid.
        """
        blkw = self._make_block(["intkey"], "pub_key")
        self.assertTrue(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))

    def test_n_of_x(self):
        """
        Test that if NofX Rule is set, the validation rule is checked
        correctly. Test:
            1. Valid Block, has one or less intkey transactions.
            2. Invalid Block, to many intkey transactions.
            3. Valid Block, ignore rule because it is formatted incorrectly.
        """
        blkw = self._make_block(["intkey"], "pub_key")
        self._settings_view_factory.add_setting(
            "sawtooth.validator.block_validation_rules",
            "NofX:1,intkey")

        self.assertTrue(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))

        self._settings_view_factory.add_setting(
            "sawtooth.validator.block_validation_rules",
            "NofX:0,intkey")

        self.assertFalse(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))

        self._settings_view_factory.add_setting(
            "sawtooth.validator.block_validation_rules",
            "NofX:0")

        self.assertTrue(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))

    def test_x_at_y(self):
        """
        Test that if XatY Rule is set, the validation rule is checked
        correctly. Test:
            1. Valid Block, has intkey at the 0th position.
            2. Invalid Block, does not have an blockinfo txn at the 0th postion
            3. Valid Block, ignore rule because it is formatted incorrectly.
        """
        blkw = self._make_block(["intkey"], "pub_key")
        self._settings_view_factory.add_setting(
            "sawtooth.validator.block_validation_rules",
            "XatY:intkey,0")

        self.assertTrue(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))

        self._settings_view_factory.add_setting(
            "sawtooth.validator.block_validation_rules",
            "XatY:blockinfo,0")

        self.assertFalse(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))

        self._settings_view_factory.add_setting(
            "sawtooth.validator.block_validation_rules",
            "XatY:0")

        self.assertTrue(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))

    def test_local(self):
        """
        Test that if local Rule is set, the validation rule is checked
        correctly. Test:
            1. Valid Block, first transaction is signed by the same signer as
               the block.
            2. Invalid Block, first transaction is not signed by the same
               signer as the block.
            3. Valid Block, ignore rule because it is formatted incorrectly.
        """
        blkw = self._make_block(["intkey"], "pub_key")
        self._settings_view_factory.add_setting(
            "sawtooth.validator.block_validation_rules",
            "local:0")

        self.assertTrue(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))

        blkw = self._make_block(["intkey"], "pub_key", False)
        self._settings_view_factory.add_setting(
            "sawtooth.validator.block_validation_rules",
            "local:0")

        self.assertFalse(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))

        self._settings_view_factory.add_setting(
            "sawtooth.validator.block_validation_rules",
            "local:test")

        self.assertTrue(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))

    def test_all_at_once(self):
        """
        Test that if multiple rules are set, they are all checked correctly.
        Block should be valid.
        """
        blkw = self._make_block(["intkey"], "pub_key")
        self._settings_view_factory.add_setting(
            "sawtooth.validator.block_validation_rules",
            "XatY:intkey,0;XatY:intkey,0;local:0")

        self.assertTrue(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))

    def test_all_at_once_bad_number_of_intkey(self):
        """
        Test that if multiple rules are set, they are all checked correctly.
        Block is invalid, because there are too many intkey transactions
        """
        blkw = self._make_block(["intkey"], "pub_key")
        self._settings_view_factory.add_setting(
            "sawtooth.validator.block_validation_rules",
            "NofX:0,intkey;XatY:intkey,0;local:0")

        self.assertFalse(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))

    def test_all_at_once_bad_family_at_index(self):
        """
        Test that if multiple rules are set, they are all checked correctly.
        Block is invalid, there is not a blockinfo transactions at the 0th
        position.
        """
        blkw = self._make_block(["intkey"], "pub_key")
        self._settings_view_factory.add_setting(
            "sawtooth.validator.block_validation_rules",
            "XatY:intkey,0;XatY:blockinfo,0;local:0")

        self.assertFalse(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))

    def test_all_at_once_signer_key(self):
        """
        Test that if multiple rules are set, they are all checked correctly.
        Block is invalid, transaction at the 0th postion is not signed by the
        same signer as the block.
        """
        blkw = self._make_block(["intkey"], "pub_key", False)
        self._settings_view_factory.add_setting(
            "sawtooth.validator.block_validation_rules",
            "XatY:intkey,0;XatY:intkey,0;local:0")

        self.assertFalse(
            enforce_validation_rules(
                self._settings_view(),
                blkw.header.signer_public_key,
                blkw.batches))
