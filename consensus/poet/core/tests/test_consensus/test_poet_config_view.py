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

from sawtooth_poet.poet_consensus.poet_config_view import PoetConfigView


@patch('sawtooth_poet.poet_consensus.poet_config_view.ConfigView')
class TestPoetConfigView(unittest.TestCase):

    # pylint: disable=invalid-name
    _EXPECTED_DEFAULT_BLOCK_CLAIM_DELAY_ = 1
    _EXPECTED_DEFAULT_FIXED_DURATION_BLOCK_COUNT_ = 50
    _EXPECTED_DEFAULT_KEY_BLOCK_CLAIM_LIMIT_ = 25
    _EXPECTED_DEFAULT_ZTEST_MAXIMUM_WIN_DEVIATION_ = 3.075
    _EXPECTED_DEFAULT_ZTEST_MINIMUM_WIN_COUNT_ = 3

    def test_block_claim_delay(self, mock_config_view):
        """Verify that retrieving block claim delay works for invalid
        cases (missing, invalid format, invalid value) as well as valid case.
        """

        poet_config_view = PoetConfigView(state_view=None)

        # Underlying config setting does not parse to an integer
        mock_config_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_config_view.block_claim_delay,
            TestPoetConfigView._EXPECTED_DEFAULT_BLOCK_CLAIM_DELAY_)

        _, kwargs = \
            mock_config_view.return_value.get_setting.call_args

        self.assertEqual(kwargs['key'], 'sawtooth.poet.block_claim_delay')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetConfigView._EXPECTED_DEFAULT_BLOCK_CLAIM_DELAY_)
        self.assertEqual(kwargs['value_type'], int)

        # Underlying config setting is not a valid value
        mock_config_view.return_value.get_setting.side_effect = None
        for bad_value in [-100, -1]:
            mock_config_view.return_value.get_setting.return_value = bad_value
            self.assertEqual(
                poet_config_view.block_claim_delay,
                TestPoetConfigView._EXPECTED_DEFAULT_BLOCK_CLAIM_DELAY_)

        # Underlying config setting is a valid value
        mock_config_view.return_value.get_setting.return_value = 0
        self.assertEqual(poet_config_view.block_claim_delay, 0)
        mock_config_view.return_value.get_setting.return_value = 1
        self.assertEqual(poet_config_view.block_claim_delay, 1)

    def test_fixed_duration_block_count(self, mock_config_view):
        """Verify that retrieving fixed duration block count works for invalid
        cases (missing, invalid format, invalid value) as well as valid case.
        """

        poet_config_view = PoetConfigView(state_view=None)

        # Underlying config setting does not parse to an integer
        mock_config_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_config_view.fixed_duration_block_count,
            TestPoetConfigView._EXPECTED_DEFAULT_FIXED_DURATION_BLOCK_COUNT_)

        _, kwargs = \
            mock_config_view.return_value.get_setting.call_args

        self.assertEqual(
            kwargs['key'],
            'sawtooth.poet.fixed_duration_block_count')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetConfigView._EXPECTED_DEFAULT_FIXED_DURATION_BLOCK_COUNT_)
        self.assertEqual(kwargs['value_type'], int)

        # Underlying config setting is not a valid value
        mock_config_view.return_value.get_setting.side_effect = None
        for bad_value in [-100, -1, 0]:
            mock_config_view.return_value.get_setting.return_value = bad_value
            self.assertEqual(
                poet_config_view.fixed_duration_block_count,
                TestPoetConfigView.
                _EXPECTED_DEFAULT_FIXED_DURATION_BLOCK_COUNT_)

        # Underlying config setting is a valid value
        mock_config_view.return_value.get_setting.return_value = 1
        self.assertEqual(poet_config_view.fixed_duration_block_count, 1)

    def test_key_block_claim_limit(self, mock_config_view):
        """Verify that retrieving key block claim limit works for invalid
        cases (missing, invalid format, invalid value) as well as valid case.
        """

        poet_config_view = PoetConfigView(state_view=None)

        # Underlying config setting does not parse to an integer
        mock_config_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_config_view.key_block_claim_limit,
            TestPoetConfigView._EXPECTED_DEFAULT_KEY_BLOCK_CLAIM_LIMIT_)

        _, kwargs = \
            mock_config_view.return_value.get_setting.call_args

        self.assertEqual(kwargs['key'], 'sawtooth.poet.key_block_claim_limit')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetConfigView._EXPECTED_DEFAULT_KEY_BLOCK_CLAIM_LIMIT_)
        self.assertEqual(kwargs['value_type'], int)

        # Underlying config setting is not a valid value
        mock_config_view.return_value.get_setting.side_effect = None
        for bad_value in [-100, -1, 0]:
            mock_config_view.return_value.get_setting.return_value = bad_value
            self.assertEqual(
                poet_config_view.key_block_claim_limit,
                TestPoetConfigView._EXPECTED_DEFAULT_KEY_BLOCK_CLAIM_LIMIT_)

        # Underlying config setting is a valid value
        mock_config_view.return_value.get_setting.return_value = 1
        self.assertEqual(poet_config_view.key_block_claim_limit, 1)

    def test_ztest_maximum_win_deviation(self, mock_config_view):
        """Verify that retrieving zTest maximum win deviation works for
        invalid cases (missing, invalid format, invalid value) as well as
        valid case.
        """

        poet_config_view = PoetConfigView(state_view=None)

        # Underlying config setting does not parse to an integer
        mock_config_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_config_view.ztest_maximum_win_deviation,
            TestPoetConfigView._EXPECTED_DEFAULT_ZTEST_MAXIMUM_WIN_DEVIATION_)

        _, kwargs = \
            mock_config_view.return_value.get_setting.call_args

        self.assertEqual(
            kwargs['key'],
            'sawtooth.poet.ztest_maximum_win_deviation')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetConfigView._EXPECTED_DEFAULT_ZTEST_MAXIMUM_WIN_DEVIATION_)
        self.assertEqual(kwargs['value_type'], float)

        # Underlying config setting is not a valid value
        mock_config_view.return_value.get_setting.side_effect = None
        for bad_value in \
                [-100.0, -1.0, 0.0, float('nan'), float('inf'), float('-inf')]:
            mock_config_view.return_value.get_setting.return_value = bad_value
            self.assertEqual(
                poet_config_view.ztest_maximum_win_deviation,
                TestPoetConfigView.
                _EXPECTED_DEFAULT_ZTEST_MAXIMUM_WIN_DEVIATION_)

        # Underlying config setting is a valid value
        mock_config_view.return_value.get_setting.return_value = 2.575
        self.assertEqual(poet_config_view.ztest_maximum_win_deviation, 2.575)

    def test_ztest_minimum_win_count(self, mock_config_view):
        """Verify that retrieving zTest minimum win observations works for
        invalid cases (missing, invalid format, invalid value) as well as
        valid case.
        """

        poet_config_view = PoetConfigView(state_view=None)

        # Underlying config setting does not parse to an integer
        mock_config_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        self.assertEqual(
            poet_config_view.ztest_minimum_win_count,
            TestPoetConfigView._EXPECTED_DEFAULT_ZTEST_MINIMUM_WIN_COUNT_)

        _, kwargs = \
            mock_config_view.return_value.get_setting.call_args

        self.assertEqual(
            kwargs['key'],
            'sawtooth.poet.ztest_minimum_win_count')
        self.assertEqual(
            kwargs['default_value'],
            TestPoetConfigView._EXPECTED_DEFAULT_ZTEST_MINIMUM_WIN_COUNT_)
        self.assertEqual(kwargs['value_type'], int)

        # Underlying config setting is not a valid value
        mock_config_view.return_value.get_setting.side_effect = None
        for bad_value in [-100, -1]:
            mock_config_view.return_value.get_setting.return_value = bad_value
            self.assertEqual(
                poet_config_view.ztest_minimum_win_count,
                TestPoetConfigView._EXPECTED_DEFAULT_ZTEST_MINIMUM_WIN_COUNT_)

        # Underlying config setting is a valid value
        mock_config_view.return_value.get_setting.return_value = 0
        self.assertEqual(poet_config_view.ztest_minimum_win_count, 0)
