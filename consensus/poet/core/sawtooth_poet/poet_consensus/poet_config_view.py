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

import logging

from sawtooth_validator.state.config_view import ConfigView

LOGGER = logging.getLogger(__name__)


class PoetConfigView(object):
    """A class to wrap the retrieval of PoET configuration settings from the
    configuration view.  For values that are not in the current state view
    or that are invalid, default values are returned.
    """

    _DEFAULT_KEY_CLAIM_LIMIT_ = 25

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
    def key_block_claim_limit(self):
        """Return the key block claim limit if config setting exists or
        default if not or value is invalid.
        """
        return \
            self._get_config_setting(
                name='sawtooth.poet.key_block_claim_limit',
                value_type=int,
                default_value=PoetConfigView._DEFAULT_KEY_CLAIM_LIMIT_,
                validate_function=lambda value: value > 0)
