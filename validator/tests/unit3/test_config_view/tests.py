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

import hashlib
import unittest

from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.protobuf.setting_pb2 import Setting
from sawtooth_validator.protobuf.state_context_pb2 import Entry

from sawtooth_validator.state.config_view import ConfigViewFactory
from sawtooth_validator.state.state_view import StateViewFactory

from sawtooth_validator.state.merkle import MerkleDatabase


class TestConfigView(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._config_view_factory = None
        self._current_root_hash = None

    def setUp(self):
        database = DictDatabase()
        state_view_factory = StateViewFactory(database)
        self._config_view_factory = ConfigViewFactory(state_view_factory)

        merkle_db = MerkleDatabase(database)
        self._current_root_hash = merkle_db.update({
            TestConfigView._address('my.setting'):
                TestConfigView._setting_entry('my.setting', '10'),
            TestConfigView._address('my.setting.list'):
                TestConfigView._setting_entry('my.setting.list', '10,11,12'),
            TestConfigView._address('my.other.list'):
                TestConfigView._setting_entry('my.other.list', '13;14;15')
        }, virtual=False)

    def test_get_setting(self):
        config_view = self._config_view_factory.create_config_view(
            self._current_root_hash)

        self.assertEqual('10', config_view.get_setting('my.setting'))

    def test_get_setting_with_type_coercion(self):
        config_view = self._config_view_factory.create_config_view(
            self._current_root_hash)
        self.assertEqual(10, config_view.get_setting('my.setting',
                                                     value_type=int))

    def test_get_setting_not_found(self):
        config_view = self._config_view_factory.create_config_view(
            self._current_root_hash)

        self.assertIsNone(config_view.get_setting('non-existant.setting'))

    def test_get_setting_not_found_with_default(self):
        config_view = self._config_view_factory.create_config_view(
            self._current_root_hash)

        self.assertEqual('default',
                         config_view.get_setting('non-existant.setting',
                                                 default_value='default'))

    def test_get_setting_list(self):
        config_view = self._config_view_factory.create_config_view(
            self._current_root_hash)

        # Verify we can still get the "raw" setting
        self.assertEqual('10,11,12',
                         config_view.get_setting('my.setting.list'))
        # And now the split setting
        self.assertEqual(
            ['10', '11', '12'],
            config_view.get_setting_list('my.setting.list'))

    def test_get_setting_list_not_found(self):
        config_view = self._config_view_factory.create_config_view(
            self._current_root_hash)
        self.assertIsNone(
            config_view.get_setting_list('non-existant.setting.list'))

    def test_get_setting_list_not_found_with_default(self):
        config_view = self._config_view_factory.create_config_view(
            self._current_root_hash)
        self.assertEqual(
            [],
            config_view.get_setting_list('non-existant.list',
                                         default_value=[]))

    def test_get_setting_list_alternate_delimiter(self):
        config_view = self._config_view_factory.create_config_view(
            self._current_root_hash)
        self.assertEqual(
            ['13', '14', '15'],
            config_view.get_setting_list('my.other.list', delimiter=';'))

    def test_get_setting_list_with_type_coercion(self):
        config_view = self._config_view_factory.create_config_view(
            self._current_root_hash)
        self.assertEqual(
            [10, 11, 12],
            config_view.get_setting_list('my.setting.list', value_type=int))

    @staticmethod
    def _address(key):
        return '000000' + hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def _setting_entry(key, value):
        setting = Setting(entries=[Setting.Entry(key=key, value=value)])
        return Entry(address=TestConfigView._address(key),
                     data=setting.SerializeToString()).SerializeToString()
