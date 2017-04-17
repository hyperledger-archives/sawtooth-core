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

import math
import logging

from sawtooth_validator.state.config_view import ConfigView

LOGGER = logging.getLogger(__name__)


class PoetConfigView(object):
    """A class to wrap the retrieval of PoET configuration settings from the
    configuration view.  For values that are not in the current state view
    or that are invalid, default values are returned.
    """

    _BLOCK_CLAIM_DELAY_ = 1
    _FIXED_DURATION_BLOCK_COUNT_ = 50
    _KEY_BLOCK_CLAIM_LIMIT_ = 25
    _ZTEST_MAXIMUM_WIN_DEVIATION_ = 3.075
    _ZTEST_MINIMUM_WIN_COUNT_ = 3

    def __init__(self, state_view):
        """Initialize a PoetConfigView object.

        Args:
            state_view (StateView): The current state view.

        Returns:
            None
        """

        self._config_view = ConfigView(state_view)

    def _get_config_setting(self,
                            name,
                            value_type,
                            default_value,
                            validate_function=None):
        """Retrieves a value from the config view, returning the default value
        if does not exist in the current state view or if the value is
        invalid.

        Args:
            name (str): The config setting to return.
            value_type (type): The value type, for example, int, float, etc.,
                of config value.
            default_value (object): The default value to be used if no value
                found or if value in config is invalid, for example, a
                non-integer value for an int config setting.
            validate_function (function): An optional function that can be
                applied to the setting to determine validity.  The function
                should return True if setting is valid, False otherwise.

        Returns:
            The value for the config setting.
        """

        try:
            value = \
                self._config_view.get_setting(
                    key=name,
                    default_value=default_value,
                    value_type=value_type)

            if validate_function is not None:
                if not validate_function(value):
                    raise \
                        ValueError(
                            'Value ({}) for {} is not valid'.format(
                                value,
                                name))
        except ValueError:
            value = default_value

        return value

    @property
    def block_claim_delay(self):
        """Return the block claim delay if config setting exists and
        is valid, otherwise return the default.

        The block claim delay is the number of blocks after a validator's
        signup information is committed to the validator registry before
        it can claim a block.
        """
        return \
            self._get_config_setting(
                name='sawtooth.poet.block_claim_delay',
                value_type=int,
                default_value=PoetConfigView._BLOCK_CLAIM_DELAY_,
                validate_function=lambda value: value >= 0)

    @property
    def fixed_duration_block_count(self):
        """Return the fixed duration block count if config setting exists and
        is valid, otherwise return the default.

        The fixed duration block count is the number of initial blocks in
        the chain that, as a validator network starts up, will have their
        local mean based on a ratio of the target and initial wait times
        instead of the history of wait timer local means.
        """
        return \
            self._get_config_setting(
                name='sawtooth.poet.fixed_duration_block_count',
                value_type=int,
                default_value=PoetConfigView._FIXED_DURATION_BLOCK_COUNT_,
                validate_function=lambda value: value > 0)

    @property
    def key_block_claim_limit(self):
        """Return the key block claim limit if config setting exists and
        is valid, otherwise return the default.

        The key block claim limit is the maximum number of blocks that a
        validator may claim with a PoET key pair before it needs to refresh
        its signup information.
        """
        return \
            self._get_config_setting(
                name='sawtooth.poet.key_block_claim_limit',
                value_type=int,
                default_value=PoetConfigView._KEY_BLOCK_CLAIM_LIMIT_,
                validate_function=lambda value: value > 0)

    @property
    def ztest_maximum_win_deviation(self):
        """Return the zTest maximum win deviation if config setting exists and
        is valid, otherwise return the default.

        The zTest maximum win deviation specifies the maximum allowed
        deviation from the expected win frequency for a particular validator
        before the zTest will fail and the claimed block will be rejected.
        The deviation corresponds to a confidence interval (i.e., how
        confident we are that we have truly detected a validator winning at
        a frequency we consider too frequent):

        3.075 ==> 99.9%
        2.575 ==> 99.5%
        2.321 ==> 99%
        1.645 ==> 95%
        """
        return \
            self._get_config_setting(
                name='sawtooth.poet.ztest_maximum_win_deviation',
                value_type=float,
                default_value=PoetConfigView._ZTEST_MAXIMUM_WIN_DEVIATION_,
                validate_function=lambda value:
                    math.isfinite(value) and value > 0)

    @property
    def ztest_minimum_win_count(self):
        """Return the zTest minimum win count if config setting exists and is
        valid, otherwise return the default.

        The zTest minimum win count is the number of blocks a validator
        must have successfully claimed (after the fixed duration block count
        has been exceeded) before the zTest will be applied to the validator's
        attempt to claim further blocks.
        """
        return \
            self._get_config_setting(
                name='sawtooth.poet.ztest_minimum_win_count',
                value_type=int,
                default_value=PoetConfigView._ZTEST_MINIMUM_WIN_COUNT_,
                validate_function=lambda value: value >= 0)
