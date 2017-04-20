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

import argparse
import os
import tempfile
import shutil
import unittest

from sawtooth_cli.protobuf.batch_pb2 import BatchHeader
from sawtooth_cli.protobuf.batch_pb2 import BatchList

from sawtooth_cli import config


TEST_WIF = '5Jq6nhPbVjgi9vTUuK7e2W81VT5dpQR7qPweYJZPVJKNzSornyv'


class TestConfigBatchlist(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None
        self._parser = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

        # create a wif key for signing
        self._wif_file = os.path.join(self._temp_dir, 'test.priv')
        with open(self._wif_file, 'wb') as wif:
            wif.write(TEST_WIF.encode())

        self._parser = argparse.ArgumentParser()
        subparsers = self._parser.add_subparsers(title='subcommands',
                                                 dest='command')

        config.add_config_parser(subparsers, self._parser)

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    def _parse_set_command(self, *settings):
        cmd_args = ['config', 'proposal', 'create',
                    '-k', self._wif_file,
                    '-o', os.path.join(self._temp_dir, 'myconfig.batch')]
        cmd_args += settings

        return self._parser.parse_args(cmd_args)

    def _read_target_file_as(self, target_type):
        target_path = os.path.join(self._temp_dir, 'myconfig.batch')
        with open(target_path, 'r+b') as result:
            output = target_type()
            output.ParseFromString(result.read())

            return output

    def test_set_value_creates_batch_list(self):
        args = self._parse_set_command('x=1', 'y=1')
        config.do_config(args)

        batch_list = self._read_target_file_as(BatchList)

        self.assertEqual(1, len(batch_list.batches))

        batch_header = BatchHeader()
        batch_header.ParseFromString(batch_list.batches[0].header)
        self.assertEqual(2, len(batch_header.transaction_ids))
