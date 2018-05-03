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

def read_file(flag):
        if flag == 1:
            filename = "/tmp/test_block_info1.toml"
            
            with open(filename, 'w') as fd:
                    fd.write('connect = "tcp://blarg:1234"')
                    fd.write(os.linesep)
                    return filename
           
        elif flag == 2:
            filename = "/tmp/test_block_info2.toml"
           
            with open(filename, 'w') as fd:
                    fd.write('connect = "tcp://test:1234"')
                    fd.write(os.linesep)
                    return filename
        
class TestBlockInfoConfig(unittest.TestCase):
    def test_load_default_block_info_config(self):
        """ Tests the default value is returned properly from BlockInfoConfig Object """
        block_config_default = load_default_block_info_config()
        self.assertEqual(block_config_default.connect, "tcp://localhost:4004")

    def test_load_toml_block_info_config_ne(self):
        """ Tests to create BlockInfoConfig object through toml file, if toml file does not exists """
        filename = "test.toml"
        block_config_default = load_toml_block_info_config(filename)
        self.assertEqual(block_config_default.connect, None)

    def test_load_toml_block_info_config(self):
        """ Tests the value BlockInfoConfig object created through toml file """
        filename = "test_block_info.toml"
        try:
            with open(filename, 'w') as fd:
                fd.write('connect = "tcp://blarg:1234"')
            block_config_filename = load_toml_block_info_config(filename)
            self.assertEqual(block_config_filename.connect, "tcp://blarg:1234")
        finally:
            os.remove(filename)

    def test_merge_default_config(self):
        """ Tests the merge of BlockInfoConfig object created through toml config files - Scenario 1"""
        configs_list = []
        try:
            filename_1=read_file(flag=1)
            block_toml_config_default_1 = load_toml_block_info_config(filename_1)
            block_config_default_3 = load_default_block_info_config()
            filename_2=read_file(flag=2)
            block_toml_config_default_2 = load_toml_block_info_config(filename_2)
            configs_list.append(block_config_default_3)
            configs_list.append(block_toml_config_default_2)
            configs_list.append(block_toml_config_default_1)
            merge_configs = merge_block_info_config(configs_list)
            self.assertEqual(merge_configs.connect, "tcp://localhost:4004")
        finally:
            os.remove(filename_1)
            os.remove(filename_2)
        
    def test_merge_toml_config(self):
        """ Tests the merge of BlockInfoConfig object created through toml config files - Scenario 2"""
        configs_list = []
        try:
            filename_1=read_file(flag=1)
            block_toml_config_default_1 = load_toml_block_info_config(filename_1)
            block_config_default_3 = load_default_block_info_config()
            filename_2=read_file(flag=2)
            block_toml_config_default_2 = load_toml_block_info_config(filename_2)
            configs_list.append(block_toml_config_default_2)
            configs_list.append(block_config_default_3)
            configs_list.append(block_toml_config_default_1)
            merge_configs = merge_block_info_config(configs_list)
            self.assertEqual(merge_configs.connect, "tcp://test:1234")
        finally:
            os.remove(filename_1)
            os.remove(filename_2)
       
    def test_to_toml(self):
        """ Tests the string representation of BlockInfoConfig object connect key """
        filename = "/tmp/test_block_info.toml"
        try:
            with open(filename, 'w') as fd:
                fd.write('connect = "tcp://blarg:1234"')
                fd.write(os.linesep)
            block_config_filename = load_toml_block_info_config(filename)
            self.assertIn('connect = "tcp://blarg:1234"', block_config_filename.to_toml_string())
        finally:
            os.remove(filename)
            
    def test_to_dict(self):
        """ Tests the key, value from OrderedDict representation of BlockInfoConfig object created by toml file """
        filename = "/tmp/test_block_info.toml"
        try:
            with open(filename, 'w') as fd:
                fd.write('connect = "tcp://blarg:1234"')
                fd.write(os.linesep)
            block_config_filename = load_toml_block_info_config(filename)
            block_info_dict=block_config_filename.to_dict()           
            for k, v in block_info_dict.items():
                self.assertEqual(k, 'connect')
                self.assertEqual(v, 'tcp://blarg:1234')
        finally:
            os.remove(filename)
            
    def test_repr(self):
        """ Tests the oject representation of BlockInfoConfig object connect key """
        block_config_default = load_default_block_info_config()
        self.assertEqual(block_config_default.__repr__(),
                         "BlockInfoConfig(connect='tcp://localhost:4004')")

    def test_load_toml_block_info_config_invalidkeys(self):
        """ Tests exception raised, when trying to create BlockInfoConfig object through toml file with invalid keys """
        filename = "/tmp/test_block_info.toml"
        try:
            with open(filename, 'w') as fd:
                fd.write('connection = "tcp://test:4004"')
            with self.assertRaises(LocalConfigurationError):
                load_toml_block_info_config(filename)
        finally:
            os.remove(filename)

