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

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import sawtooth_signing as signing

from sawtooth_poet_cli.main import main
import sawtooth_validator.protobuf.batch_pb2 as batch_pb
import sawtooth_validator.protobuf.transaction_pb2 as txn_pb


class TestValidatorRegistryGenesisTransaction(unittest.TestCase):

    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    @patch('sawtooth_poet_cli.config.get_data_dir')
    @patch('sawtooth_poet_cli.config.get_key_dir')
    def test_run_simulator_genesis(self, get_data_dir_fn, get_key_dir_fn):
        """Test generating a Validator Registry transaction, which is written
        to a file.

        This test executes the `poet genesis` command. The expected output is:

        - a BatchList written to a file at <temp_dir>/poet_genesis.batch
        - the serialized sealed signup data is written to
          `<data_dir>/poet_signup_data`
        """
        get_data_dir_fn.return_value = self._temp_dir
        get_key_dir_fn.return_value = self._temp_dir

        pubkey = self._create_key()

        main('poet',
             args=['genesis',
                   '-o', os.path.join(self._temp_dir, 'poet-genesis.batch')])

        self._assert_validator_transaction(pubkey, 'poet-genesis.batch')
        self._assert_sealed_signup_data()

    def _assert_validator_transaction(self, pubkey, target_file):
        filename = os.path.join(self._temp_dir, target_file)
        batch_list = batch_pb.BatchList()
        with open(filename, 'rb') as batch_file:
            batch_list.ParseFromString(batch_file.read())

        self.assertEqual(1, len(batch_list.batches))

        batch = batch_list.batches[0]
        self.assertEqual(1, len(batch.transactions))
        batch_header = batch_pb.BatchHeader()
        batch_header.ParseFromString(batch.header)

        self.assertEqual(pubkey, batch_header.signer_pubkey)

        txn = batch.transactions[0]
        txn_header = txn_pb.TransactionHeader()
        txn_header.ParseFromString(txn.header)

        self.assertEqual(pubkey, txn_header.signer_pubkey)
        self.assertEqual('sawtooth_validator_registry', txn_header.family_name)

    def _assert_sealed_signup_data(self):
        filename = os.path.join(self._temp_dir, 'poet_signup_data')
        with open(filename, 'rb') as data_file:
            self.assertTrue(len(data_file.read()) > 0)

    def _create_key(self, key_name='validator.wif'):
        privkey = signing.generate_privkey()
        wif_file = os.path.join(self._temp_dir, key_name)
        with open(wif_file, 'w') as wif_fd:
            wif_fd.write(privkey)

        return signing.generate_pubkey(privkey)
