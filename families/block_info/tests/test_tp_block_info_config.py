# Copyright 2018 Intel Corporation
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
import os

from sawtooth_block_info.processor.config.block_info \
import load_default_block_info_config,\
    load_toml_block_info_config, merge_block_info_config
from sawtooth_sdk.processor.exceptions import LocalConfigurationError

class TestBlockInfoConfig(unittest.TestCase):
    def test_load_default_block_info_config(self):
        """ Tests the default return value of config file """
        block_config_default = load_default_block_info_config()
        self.assertEqual(block_config_default.connect, "tcp://localhost:4004")

    def test_load_toml_block_info_config_ne(self):
        """ Tests toml load file if it is not present """
        filename = "test.toml"
        block_config_default = load_toml_block_info_config(filename)
        self.assertEqual(block_config_default.connect, None)

    def test_load_toml_block_info_config(self):
        """ Tests value inside toml load file """
        filename = "test_block_info.toml"
        try:
            with open(filename, 'w') as fd:
                fd.write('connect = "tcp://blarg:1234"')
            block_config_filename = load_toml_block_info_config(filename)
            self.assertEqual(block_config_filename.connect, "tcp://blarg:1234")
        finally:
            os.remove(filename)

    def test_merge_config(self):
        """ Tests the merge of all toml config files """
        l = []
        block_config_default_1 = load_default_block_info_config()
        block_config_default_2 = load_default_block_info_config()
        block_config_default_3 = load_default_block_info_config()
        l.append(block_config_default_1)
        l.append(block_config_default_2)
        l.append(block_config_default_3)
        mc = merge_block_info_config(l)
        self.assertEqual(mc.connect, "tcp://localhost:4004")

    def test_to_toml(self):
        block_config_default = load_default_block_info_config()
        self.assertEqual(block_config_default.to_toml_string(),
                        ['connect = "tcp://localhost:4004"'])

    def test_repr(self):
        block_config_default = load_default_block_info_config()
        self.assertEqual(block_config_default.__repr__(),
                         "BlockInfoConfig(connect='tcp://localhost:4004')")

    def test_load_toml_block_info_config_invalidkeys(self):
        filename = "a.toml"
        try:
            with open(filename, 'w') as fd:
                fd.write('ty = "tcp://test:4004"')
            with self.assertRaises(LocalConfigurationError):
                load_toml_block_info_config(filename)
        finally:
            os.remove(filename)

