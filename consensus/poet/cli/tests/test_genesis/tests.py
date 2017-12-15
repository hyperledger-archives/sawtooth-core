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

# pylint: disable=invalid-name

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from sawtooth_signing import create_context

from sawtooth_poet_cli.main import main
import sawtooth_validator.protobuf.batch_pb2 as batch_pb
import sawtooth_validator.protobuf.transaction_pb2 as txn_pb
import sawtooth_poet_common.protobuf.validator_registry_pb2 as vr_pb


class TestValidatorRegistryGenesisTransaction(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()
        self._store = {}

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    @patch('sawtooth_poet_cli.registration.PoetKeyStateStore')
    @patch('sawtooth_poet_cli.registration.config.get_data_dir')
    @patch('sawtooth_poet_cli.registration.config.get_key_dir')
    def test_run_simulator_genesis(self,
                                   get_key_dir_fn,
                                   get_data_dir_fn,
                                   mock_store):
        """Test generating a Validator Registry transaction, which is written
        to a file.

        This test executes the `poet registration create` command. The
        expected output is:

        - a BatchList written to a file at <temp_dir>/poet_genesis.batch
        - the serialized sealed signup data is written to the key state store
        """
        mock_store.return_value = self._store
        get_data_dir_fn.return_value = self._temp_dir
        get_key_dir_fn.return_value = self._temp_dir

        public_key = self._create_key()

        main('poet',
             args=['registration', 'create',
                   '-o', os.path.join(self._temp_dir, 'poet-genesis.batch')])

        self._assert_validator_transaction(public_key, 'poet-genesis.batch')

    def _assert_validator_transaction(self, public_key, target_file):
        filename = os.path.join(self._temp_dir, target_file)
        batch_list = batch_pb.BatchList()
        with open(filename, 'rb') as batch_file:
            batch_list.ParseFromString(batch_file.read())

        self.assertEqual(1, len(batch_list.batches))

        batch = batch_list.batches[0]
        self.assertEqual(1, len(batch.transactions))
        batch_header = batch_pb.BatchHeader()
        batch_header.ParseFromString(batch.header)

        self.assertEqual(public_key, batch_header.signer_public_key)

        txn = batch.transactions[0]
        txn_header = txn_pb.TransactionHeader()
        txn_header.ParseFromString(txn.header)

        self.assertEqual(public_key, txn_header.signer_public_key)
        self.assertEqual('sawtooth_validator_registry', txn_header.family_name)

        payload = vr_pb.ValidatorRegistryPayload()
        payload.ParseFromString(txn.payload)
        self._assert_key_state(payload.signup_info.poet_public_key)

    def _assert_key_state(self, poet_public_key):
        # Assert that the proper entry was created in the consensus state store
        # and that the sealed signup data contains something
        self.assertEqual(len(self._store), 1)
        self.assertTrue(poet_public_key in self._store)

    def _create_key(self, key_name='validator.priv'):
        context = create_context('secp256k1')
        private_key = context.new_random_private_key()
        priv_file = os.path.join(self._temp_dir, key_name)
        with open(priv_file, 'w') as priv_fd:
            priv_fd.write(private_key.as_hex())

        return context.get_public_key(private_key).as_hex()
