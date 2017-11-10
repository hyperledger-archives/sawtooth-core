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
import shlex
import shutil
import subprocess
import tempfile
import unittest

from sawtooth_cli.protobuf.batch_pb2 import BatchHeader
from sawtooth_cli.protobuf.batch_pb2 import BatchList


TEST_WIF = '5Jq6nhPbVjgi9vTUuK7e2W81VT5dpQR7qPweYJZPVJKNzSornyv'


class TestConfigBatchlist(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

        # create a wif key for signing
        self._wif_file = os.path.join(self._temp_dir, 'test.priv')
        with open(self._wif_file, 'wb') as wif:
            wif.write(TEST_WIF.encode())

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    def _read_target_file_as(self, target_type):
        target_path = os.path.join(self._temp_dir, 'myconfig.batch')
        with open(target_path, 'r+b') as result:
            output = target_type()
            output.ParseFromString(result.read())

            return output

    def test_set_value_creates_batch_list(self):
        subprocess.run(shlex.split(
            'sawset proposal create -k {} -o {} x=1 y=1'.format(
                self._wif_file,
                os.path.join(self._temp_dir, 'myconfig.batch'))))

        batch_list = self._read_target_file_as(BatchList)

        self.assertEqual(1, len(batch_list.batches))

        batch_header = BatchHeader()
        batch_header.ParseFromString(batch_list.batches[0].header)
        self.assertEqual(2, len(batch_header.transaction_ids))
