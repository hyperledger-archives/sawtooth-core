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

    def test_key_block_claim_limit(self, mock_config_view):
        """Verify that retrieving key block claim limit works for invalid
        cases (missing, invalid format, invalid value) as well as valid case.
        """

        poet_config_view = PoetConfigView(state_view=None)

        # Underlying config setting does not parse to an integer
        mock_config_view.return_value.get_setting.side_effect = \
            ValueError('bad value')

        # pylint: disable=protected-access
        self.assertEqual(
            poet_config_view.key_block_claim_limit,
            PoetConfigView._DEFAULT_KEY_CLAIM_LIMIT_)

        _, kwargs = \
            mock_config_view.return_value.get_setting.call_args

        self.assertEqual(kwargs['key'], 'sawtooth.poet.key_block_claim_limit')
        # pylint: disable=protected-access
        self.assertEqual(
            kwargs['default_value'],
            PoetConfigView._DEFAULT_KEY_CLAIM_LIMIT_)
        self.assertEqual(kwargs['value_type'], int)

        # Underlying config setting is not a valid value
        mock_config_view.return_value.get_setting.side_effect = None
        mock_config_view.return_value.get_setting.return_value = -1
        # pylint: disable=protected-access
        self.assertEqual(
            poet_config_view.key_block_claim_limit,
            PoetConfigView._DEFAULT_KEY_CLAIM_LIMIT_)

        mock_config_view.return_value.get_setting.return_value = 0
        # pylint: disable=protected-access
        self.assertEqual(
            poet_config_view.key_block_claim_limit,
            PoetConfigView._DEFAULT_KEY_CLAIM_LIMIT_)

        # Underlying config setting is a valid value
        mock_config_view.return_value.get_setting.return_value = 1
        self.assertEqual(
            poet_config_view.key_block_claim_limit,
            1)
