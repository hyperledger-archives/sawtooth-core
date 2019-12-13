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
import hashlib
import unittest

from sawtooth_validator.database.native_lmdb import NativeLmdbDatabase
from sawtooth_validator.protobuf.setting_pb2 import Setting

from sawtooth_validator.state.settings_view import SettingsViewFactory
from sawtooth_validator.state.state_view import StateViewFactory

from sawtooth_validator.state.merkle import MerkleDatabase


class TestSettingsView(unittest.TestCase):
    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None
        self._settings_view_factory = None
        self._current_root_hash = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()
        database = NativeLmdbDatabase(
            os.path.join(self._temp_dir, 'test_config_view.lmdb'),
            indexes=MerkleDatabase.create_index_configuration(),
            _size=10 * 1024 * 1024)
        state_view_factory = StateViewFactory(database)
        self._settings_view_factory = SettingsViewFactory(state_view_factory)

        merkle_db = MerkleDatabase(database)
        self._current_root_hash = merkle_db.update({
            TestSettingsView._address('my.setting'):
                TestSettingsView._setting_entry('my.setting', '10'),
            TestSettingsView._address('my.setting.list'):
                TestSettingsView._setting_entry('my.setting.list', '10,11,12'),
            TestSettingsView._address('my.other.list'):
                TestSettingsView._setting_entry('my.other.list', '13;14;15')
        }, virtual=False)

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    def test_get_setting(self):
        """Verifies the correct operation of get_setting() by using it to get
        the config setting stored as "my.setting" and compare it to '10' (the
        value set during setUp()).
        """
        settings_view = self._settings_view_factory.create_settings_view(
            self._current_root_hash)

        self.assertEqual('10', settings_view.get_setting('my.setting'))

    def test_get_setting_with_type_coercion(self):
        """Verifies the correct operation of get_setting() by using it to get
        the config setting stored as "my.setting" with a int type coercion
        function and compare it to the int 10 (the value set during setUp()).
        """
        settings_view = self._settings_view_factory.create_settings_view(
            self._current_root_hash)
        self.assertEqual(10, settings_view.get_setting('my.setting',
                                                       value_type=int))

    def test_get_setting_not_found(self):
        """Verifies the correct operation of get_setting() by using it to
        return None when an unknown setting is requested.
        """
        settings_view = self._settings_view_factory.create_settings_view(
            self._current_root_hash)

        self.assertIsNone(settings_view.get_setting('non-existant.setting'))

    def test_get_setting_not_found_with_default(self):
        """Verifies the correct operation of get_setting() by using it to
        return a default value when an unknown setting is requested.
        """
        settings_view = self._settings_view_factory.create_settings_view(
            self._current_root_hash)

        self.assertEqual('default',
                         settings_view.get_setting('non-existant.setting',
                                                   default_value='default'))

    def test_get_setting_list(self):
        """Verifies the correct operation of get_setting_list() by using it to
        get the config setting stored as "my.setting.list" and compare it to
        ['10', '11', '12'] (the split value set during setUp()).
        """
        settings_view = self._settings_view_factory.create_settings_view(
            self._current_root_hash)

        # Verify we can still get the "raw" setting
        self.assertEqual('10,11,12',
                         settings_view.get_setting('my.setting.list'))
        # And now the split setting
        self.assertEqual(
            ['10', '11', '12'],
            settings_view.get_setting_list('my.setting.list'))

    def test_get_setting_list_not_found(self):
        """Verifies the correct operation of get_setting_list() by using it to
        return None when an unknown setting is requested.
        """
        settings_view = self._settings_view_factory.create_settings_view(
            self._current_root_hash)
        self.assertIsNone(
            settings_view.get_setting_list('non-existant.setting.list'))

    def test_get_setting_list_not_found_with_default(self):
        """Verifies the correct operation of get_setting_list() by using it to
        return a default value when an unknown setting is requested.
        """
        settings_view = self._settings_view_factory.create_settings_view(
            self._current_root_hash)
        self.assertEqual(
            [],
            settings_view.get_setting_list('non-existant.list',
                                           default_value=[]))

    def test_get_setting_list_alternate_delimiter(self):
        """Verifies the correct operation of get_setting_list() by using it to
        get the config setting stored as "my.other.list" and compare it to
        ['13', '14', '15'] (the value, split along an alternate delimiter, set
        during setUp()).
        """
        settings_view = self._settings_view_factory.create_settings_view(
            self._current_root_hash)
        self.assertEqual(
            ['13', '14', '15'],
            settings_view.get_setting_list('my.other.list', delimiter=';'))

    def test_get_setting_list_with_type_coercion(self):
        """Verifies the correct operation of get_setting_list() by using it to
        get the integer type-coerced config setting stored as "my.setting.list"
        and compare it to [10, 11, 12] (the split, type-coerced, value set
        during setUp()).
        """
        settings_view = self._settings_view_factory.create_settings_view(
            self._current_root_hash)
        self.assertEqual(
            [10, 11, 12],
            settings_view.get_setting_list('my.setting.list', value_type=int))

    @staticmethod
    def _address(key):
        return '000000' + _key_to_address(key)

    @staticmethod
    def _setting_entry(key, value):
        return Setting(
            entries=[Setting.Entry(key=key, value=value)]
        ).SerializeToString()


_MAX_KEY_PARTS = 4
_ADDRESS_PART_SIZE = 16


def _short_hash(name):
    return hashlib.sha256(name.encode()).hexdigest()[:_ADDRESS_PART_SIZE]


def _key_to_address(key):
    key_parts = key.split('.', maxsplit=_MAX_KEY_PARTS - 1)
    key_parts.extend([''] * (_MAX_KEY_PARTS - len(key_parts)))
    return ''.join(_short_hash(x) for x in key_parts)
