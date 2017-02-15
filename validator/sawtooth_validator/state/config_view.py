# copyright 2017 intel corporation
#
# licensed under the apache license, version 2.0 (the "license");
# you may not use this file except in compliance with the license.
# you may obtain a copy of the license at
#
#     http://www.apache.org/licenses/license-2.0
#
# unless required by applicable law or agreed to in writing, software
# distributed under the license is distributed on an "as is" basis,
# without warranties or conditions of any kind, either express or implied.
# see the license for the specific language governing permissions and
# limitations under the license.
# ------------------------------------------------------------------------------

import hashlib

from sawtooth_validator.protobuf.setting_pb2 import Setting


class ConfigView(object):
    """
    A ConfigView is a snapshot view of on-chain configuration settings.
    """

    def __init__(self, state_view):
        """Creates a ConfigView, given a StateView as its snapshot.

        Args:
            state_view (:obj:`StateView`): a state view
        """
        self._state_view = state_view

    def get_setting(self, key, default_value=None, value_type=str):
        """Get the setting stored at the given key.

        Args:
            key (str): the setting key
            default_value (str, optional): The default value, if none is
                found. Defaults to None.
            type (function, optional): The type of a setting value.
                Defaults to `str`.

        Returns:
            str: The value of the setting if found, default_value
            otherwise.
        """
        try:
            state_entry = self._state_view.get(
                ConfigView._setting_address(key))
        except KeyError:
            return default_value

        if state_entry is not None:
            setting = Setting()
            setting.ParseFromString(state_entry.data)
            for setting_entry in setting.entries:
                if setting_entry.key == key:
                    return value_type(setting_entry.value)

        return default_value

    def get_setting_list(self,
                         key,
                         default_value=None,
                         delimiter=',',
                         value_type=str):
        """Get the setting stored at the given key and split it to a list.

        Args:
            key (str): the setting key
            default_value (list, optional): The default value, if none is
                found. Defaults to None.
            delimiter (list of str, optional): The delimiter to break on.
                Defaults to ','.
            type (function, optional): The type of a setting value in the list.
                Defaults to `str`.

        Returns:
            list of str: The values of the setting if found, default_value
            otherwise.

            If a value is found, it is split using the given delimiter.
        """
        value = self.get_setting(key)
        if value is not None:
            return [value_type(v) for v in value.split(delimiter)]
        else:
            return default_value

    @staticmethod
    def _setting_address(key):
        return '000000' + hashlib.sha256(key.encode()).hexdigest()


class ConfigViewFactory(object):
    """Creates ConfigView instances.
    """

    def __init__(self, state_view_factory):
        """Creates this view factory with a given state view factory.

        Args:
            state_view_factory (:obj:`StateViewFactory`): the state view
                factory
        """
        self._state_view_factory = state_view_factory

    def create_config_view(self, state_root_hash):
        """
        Returns:
            ConfigView: the configuration view at the given state root.
        """
        return ConfigView(
            self._state_view_factory.create_view(state_root_hash))
