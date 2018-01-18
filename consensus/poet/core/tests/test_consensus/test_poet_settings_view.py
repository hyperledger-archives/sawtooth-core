# Copyright 2016, 2017 Intel Corporation
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
from unittest.mock import patch

from sawtooth_poet.poet_consensus.poet_settings_view import PoetSettingsView


@patch('sawtooth_poet.poet_consensus.poet_settings_view.SettingsView')
class TestPoetSettingsView(unittest.TestCase):

    # pylint: disable=invalid-name
    _EXPECTED_DEFAULT_BLOCK_CLAIM_DELAY_ = 1
    _EXPECTED_DEFAULT_ENCLAVE_MODULE_NAME_ = \
        'sawtooth_poet_simulator.poet_enclave_simulator.poet_enclave_simulator'
    _EXPECTED_DEFAULT_INITIAL_WAIT_TIME_ = 3000.0
    _EXPECTED_DEFAULT_KEY_BLOCK_CLAIM_LIMIT_ = 250
    _EXPECTED_DEFAULT_POPULATION_ESTIMATE_SAMPLE_SIZE_ = 50
    _EXPECTED_DEFAULT_SIGNUP_COMMIT_MAXIMUM_DELAY_ = 10
    _EXPECTED_DEFAULT_TARGET_WAIT_TIME_ = 20.0
    _EXPECTED_DEFAULT_ZTEST_MAXIMUM_WIN_DEVIATION_ = 3.075
    _EXPECTED_DEFAULT_ZTEST_MINIMUM_WIN_COUNT_ = 3

    def test_block_claim_delay(self, mock_settings_view):
        """Verify that retrieving block claim delay works for invalid
        cases (missing, invalid format, invalid value) as well as valid case.
        """

        poet_settings_view = PoetSettingsView(state_view=None)

        # Simulate an underlying error parsing value
        mock_settings_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_settings_view.block_claim_delay,
            TestPoetSettingsView._EXPECTED_DEFAULT_BLOCK_CLAIM_DELAY_)

        _, kwargs = \
            mock_settings_view.return_value.get_setting.call_args

        self.assertEqual(kwargs['key'], 'sawtooth.poet.block_claim_delay')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetSettingsView._EXPECTED_DEFAULT_BLOCK_CLAIM_DELAY_)
        self.assertEqual(kwargs['value_type'], int)

        # Underlying config setting is not a valid value
        mock_settings_view.return_value.get_setting.side_effect = None
        for bad_value in [-100, -1]:
            mock_settings_view.return_value.get_setting.return_value = \
                bad_value
            poet_settings_view = PoetSettingsView(state_view=None)
            self.assertEqual(
                poet_settings_view.block_claim_delay,
                TestPoetSettingsView._EXPECTED_DEFAULT_BLOCK_CLAIM_DELAY_)

        # Underlying config setting is a valid value
        poet_settings_view = PoetSettingsView(state_view=None)
        mock_settings_view.return_value.get_setting.return_value = 0
        self.assertEqual(poet_settings_view.block_claim_delay, 0)
        poet_settings_view = PoetSettingsView(state_view=None)
        mock_settings_view.return_value.get_setting.return_value = 1
        self.assertEqual(poet_settings_view.block_claim_delay, 1)

    def test_enclave_module_name(self, mock_settings_view):
        """Verify that retrieving enclave module name works for invalid
        cases (missing, invalid format, invalid value) as well as valid case.
        """

        poet_settings_view = PoetSettingsView(state_view=None)

        # Simulate an underlying error parsing value
        mock_settings_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_settings_view.enclave_module_name,
            TestPoetSettingsView._EXPECTED_DEFAULT_ENCLAVE_MODULE_NAME_)

        _, kwargs = \
            mock_settings_view.return_value.get_setting.call_args

        self.assertEqual(kwargs['key'], 'sawtooth.poet.enclave_module_name')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetSettingsView._EXPECTED_DEFAULT_ENCLAVE_MODULE_NAME_)
        self.assertEqual(kwargs['value_type'], str)

        # Underlying config setting is not a valid value
        mock_settings_view.return_value.get_setting.side_effect = None
        mock_settings_view.return_value.get_setting.return_value = ''
        poet_settings_view = PoetSettingsView(state_view=None)
        self.assertEqual(
            poet_settings_view.enclave_module_name,
            TestPoetSettingsView._EXPECTED_DEFAULT_ENCLAVE_MODULE_NAME_)

        # Underlying config setting is a valid value
        mock_settings_view.return_value.get_setting.return_value = \
            'valid value'
        poet_settings_view = PoetSettingsView(state_view=None)
        self.assertEqual(poet_settings_view.enclave_module_name, 'valid value')

    def test_initial_wait_time(self, mock_settings_view):
        """Verify that retrieving initial wait time works for invalid cases
        (missing, invalid format, invalid value) as well as valid case.
        """

        poet_settings_view = PoetSettingsView(state_view=None)

        # Simulate an underlying error parsing value
        mock_settings_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_settings_view.initial_wait_time,
            TestPoetSettingsView._EXPECTED_DEFAULT_INITIAL_WAIT_TIME_)

        _, kwargs = \
            mock_settings_view.return_value.get_setting.call_args

        self.assertEqual(kwargs['key'], 'sawtooth.poet.initial_wait_time')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetSettingsView._EXPECTED_DEFAULT_INITIAL_WAIT_TIME_)
        self.assertEqual(kwargs['value_type'], float)

        # Underlying config setting is not a valid value
        mock_settings_view.return_value.get_setting.side_effect = None
        for bad_value in \
                [-100.0, -1.0, float('nan'), float('inf'), float('-inf')]:
            mock_settings_view.return_value.get_setting.return_value = \
                bad_value
            poet_settings_view = PoetSettingsView(state_view=None)
            self.assertEqual(
                poet_settings_view.initial_wait_time,
                TestPoetSettingsView._EXPECTED_DEFAULT_INITIAL_WAIT_TIME_)

        # Underlying config setting is a valid value
        mock_settings_view.return_value.get_setting.return_value = 3.1415
        poet_settings_view = PoetSettingsView(state_view=None)
        self.assertEqual(poet_settings_view.initial_wait_time, 3.1415)

    def test_key_block_claim_limit(self, mock_settings_view):
        """Verify that retrieving key block claim limit works for invalid
        cases (missing, invalid format, invalid value) as well as valid case.
        """

        poet_settings_view = PoetSettingsView(state_view=None)

        # Simulate an underlying error parsing value
        mock_settings_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_settings_view.key_block_claim_limit,
            TestPoetSettingsView._EXPECTED_DEFAULT_KEY_BLOCK_CLAIM_LIMIT_)

        _, kwargs = \
            mock_settings_view.return_value.get_setting.call_args

        self.assertEqual(kwargs['key'], 'sawtooth.poet.key_block_claim_limit')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetSettingsView._EXPECTED_DEFAULT_KEY_BLOCK_CLAIM_LIMIT_)
        self.assertEqual(kwargs['value_type'], int)

        # Underlying config setting is not a valid value
        mock_settings_view.return_value.get_setting.side_effect = None
        for bad_value in [-100, -1, 0]:
            mock_settings_view.return_value.get_setting.return_value = \
                bad_value
            poet_settings_view = PoetSettingsView(state_view=None)
            self.assertEqual(
                poet_settings_view.key_block_claim_limit,
                TestPoetSettingsView._EXPECTED_DEFAULT_KEY_BLOCK_CLAIM_LIMIT_)

        # Underlying config setting is a valid value
        mock_settings_view.return_value.get_setting.return_value = 1
        poet_settings_view = PoetSettingsView(state_view=None)
        self.assertEqual(poet_settings_view.key_block_claim_limit, 1)

    def test_population_estimate_sample_size(self, mock_settings_view):
        """Verify that retrieving population estimate sample size works for
        invalid cases (missing, invalid format, invalid value) as well as valid
        case.
        """

        poet_settings_view = PoetSettingsView(state_view=None)

        # Simulate an underlying error parsing value
        mock_settings_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_settings_view.population_estimate_sample_size,
            TestPoetSettingsView.
            _EXPECTED_DEFAULT_POPULATION_ESTIMATE_SAMPLE_SIZE_)

        _, kwargs = \
            mock_settings_view.return_value.get_setting.call_args

        self.assertEqual(
            kwargs['key'],
            'sawtooth.poet.population_estimate_sample_size')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetSettingsView.
            _EXPECTED_DEFAULT_POPULATION_ESTIMATE_SAMPLE_SIZE_)
        self.assertEqual(kwargs['value_type'], int)

        # Underlying config setting is not a valid value
        mock_settings_view.return_value.get_setting.side_effect = None
        for bad_value in [-100, -1, 0]:
            mock_settings_view.return_value.get_setting.return_value = \
                bad_value
            poet_settings_view = PoetSettingsView(state_view=None)
            self.assertEqual(
                poet_settings_view.population_estimate_sample_size,
                TestPoetSettingsView.
                _EXPECTED_DEFAULT_POPULATION_ESTIMATE_SAMPLE_SIZE_)

        # Underlying config setting is a valid value
        mock_settings_view.return_value.get_setting.return_value = 1
        poet_settings_view = PoetSettingsView(state_view=None)
        self.assertEqual(poet_settings_view.population_estimate_sample_size, 1)

    def test_target_wait_time(self, mock_settings_view):
        """Verify that retrieving target wait time works for invalid cases
        (missing, invalid format, invalid value) as well as valid case.
        """

        poet_settings_view = PoetSettingsView(state_view=None)

        # Simulate an underlying error parsing value
        mock_settings_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_settings_view.target_wait_time,
            TestPoetSettingsView._EXPECTED_DEFAULT_TARGET_WAIT_TIME_)

        _, kwargs = \
            mock_settings_view.return_value.get_setting.call_args

        self.assertEqual(kwargs['key'], 'sawtooth.poet.target_wait_time')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetSettingsView._EXPECTED_DEFAULT_TARGET_WAIT_TIME_)
        self.assertEqual(kwargs['value_type'], float)

        # Underlying config setting is not a valid value
        mock_settings_view.return_value.get_setting.side_effect = None
        for bad_value in \
                [-100.0, -1.0, 0.0, float('nan'), float('inf'), float('-inf')]:
            mock_settings_view.return_value.get_setting.return_value = \
                bad_value
            poet_settings_view = PoetSettingsView(state_view=None)
            self.assertEqual(
                poet_settings_view.target_wait_time,
                TestPoetSettingsView._EXPECTED_DEFAULT_TARGET_WAIT_TIME_)

        # Underlying config setting is a valid value
        mock_settings_view.return_value.get_setting.return_value = 3.1415
        poet_settings_view = PoetSettingsView(state_view=None)
        self.assertEqual(poet_settings_view.target_wait_time, 3.1415)

    def test_signup_commit_maximum_delay(self, mock_settings_view):
        """Verify that retrieving signup commit maximum delay works for invalid
        cases (missing, invalid format, invalid value) as well as valid case.
        """

        poet_settings_view = PoetSettingsView(state_view=None)

        # Simulate an underlying error parsing value
        mock_settings_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_settings_view.signup_commit_maximum_delay,
            TestPoetSettingsView.
            _EXPECTED_DEFAULT_SIGNUP_COMMIT_MAXIMUM_DELAY_)

        _, kwargs = \
            mock_settings_view.return_value.get_setting.call_args

        self.assertEqual(
            kwargs['key'],
            'sawtooth.poet.signup_commit_maximum_delay')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetSettingsView.
            _EXPECTED_DEFAULT_SIGNUP_COMMIT_MAXIMUM_DELAY_)
        self.assertEqual(kwargs['value_type'], int)

        # Underlying config setting is not a valid value
        mock_settings_view.return_value.get_setting.side_effect = None
        for bad_value in [-100, -1]:
            mock_settings_view.return_value.get_setting.return_value = \
                bad_value
            poet_settings_view = PoetSettingsView(state_view=None)
            self.assertEqual(
                poet_settings_view.signup_commit_maximum_delay,
                TestPoetSettingsView.
                _EXPECTED_DEFAULT_SIGNUP_COMMIT_MAXIMUM_DELAY_)

        # Underlying config setting is a valid value
        mock_settings_view.return_value.get_setting.return_value = 123
        poet_settings_view = PoetSettingsView(state_view=None)
        self.assertEqual(poet_settings_view.signup_commit_maximum_delay, 123)

    def test_ztest_maximum_win_deviation(self, mock_settings_view):
        """Verify that retrieving zTest maximum win deviation works for
        invalid cases (missing, invalid format, invalid value) as well as
        valid case.
        """

        poet_settings_view = PoetSettingsView(state_view=None)

        # Simulate an underlying error parsing value
        mock_settings_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_settings_view.ztest_maximum_win_deviation,
            TestPoetSettingsView.
            _EXPECTED_DEFAULT_ZTEST_MAXIMUM_WIN_DEVIATION_)

        _, kwargs = \
            mock_settings_view.return_value.get_setting.call_args

        self.assertEqual(
            kwargs['key'],
            'sawtooth.poet.ztest_maximum_win_deviation')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetSettingsView.
            _EXPECTED_DEFAULT_ZTEST_MAXIMUM_WIN_DEVIATION_)
        self.assertEqual(kwargs['value_type'], float)

        # Underlying config setting is not a valid value
        mock_settings_view.return_value.get_setting.side_effect = None
        for bad_value in \
                [-100.0, -1.0, 0.0, float('nan'), float('inf'), float('-inf')]:
            mock_settings_view.return_value.get_setting.return_value = \
                bad_value
            poet_settings_view = PoetSettingsView(state_view=None)
            self.assertEqual(
                poet_settings_view.ztest_maximum_win_deviation,
                TestPoetSettingsView.
                _EXPECTED_DEFAULT_ZTEST_MAXIMUM_WIN_DEVIATION_)

        # Underlying config setting is a valid value
        mock_settings_view.return_value.get_setting.return_value = 2.575
        poet_settings_view = PoetSettingsView(state_view=None)
        self.assertEqual(poet_settings_view.ztest_maximum_win_deviation, 2.575)

    def test_ztest_minimum_win_count(self, mock_settings_view):
        """Verify that retrieving zTest minimum win observations works for
        invalid cases (missing, invalid format, invalid value) as well as
        valid case.
        """

        poet_settings_view = PoetSettingsView(state_view=None)

        # Simulate an underlying error parsing value
        mock_settings_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_settings_view.ztest_minimum_win_count,
            TestPoetSettingsView._EXPECTED_DEFAULT_ZTEST_MINIMUM_WIN_COUNT_)

        _, kwargs = \
            mock_settings_view.return_value.get_setting.call_args

        self.assertEqual(
            kwargs['key'],
            'sawtooth.poet.ztest_minimum_win_count')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetSettingsView._EXPECTED_DEFAULT_ZTEST_MINIMUM_WIN_COUNT_)
        self.assertEqual(kwargs['value_type'], int)

        # Underlying config setting is not a valid value
        mock_settings_view.return_value.get_setting.side_effect = None
        for bad_value in [-100, -1]:
            mock_settings_view.return_value.get_setting.return_value = \
                bad_value
            poet_settings_view = PoetSettingsView(state_view=None)
            self.assertEqual(
                poet_settings_view.ztest_minimum_win_count,
                TestPoetSettingsView.
                _EXPECTED_DEFAULT_ZTEST_MINIMUM_WIN_COUNT_)

        # Underlying config setting is a valid value
        mock_settings_view.return_value.get_setting.return_value = 0
        poet_settings_view = PoetSettingsView(state_view=None)
        self.assertEqual(poet_settings_view.ztest_minimum_win_count, 0)
