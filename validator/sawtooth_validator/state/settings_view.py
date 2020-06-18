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
import weakref

from functools import lru_cache, wraps

from sawtooth_validator.protobuf.setting_pb2 import Setting


CONFIG_STATE_NAMESPACE = '000000'
_MAX_KEY_PARTS = 4
_ADDRESS_PART_SIZE = 16


def _short_hash(byte_str):
    return hashlib.sha256(byte_str).hexdigest()[:_ADDRESS_PART_SIZE]


_EMPTY_PART = _short_hash(b'')


# Wrapper of lru_cache that works for instance methods
def lru_cached_method(*lru_args, **lru_kwargs):
    def decorator(wrapped_fn):
        @wraps(wrapped_fn)
        def wrapped(self, *args, **kwargs):
            # Use a weak reference to self; this prevents a self-reference
            # cycle that fools the garbage collector into thinking the instance
            # shouldn't be dropped when all external references are dropped.
            weak_ref_to_self = weakref.ref(self)

            @wraps(wrapped_fn)
            @lru_cache(*lru_args, **lru_kwargs)
            def cached(*args, **kwargs):
                return wrapped_fn(weak_ref_to_self(), *args, **kwargs)
            setattr(self, wrapped_fn.__name__, cached)
            return cached(*args, **kwargs)
        return wrapped
    return decorator


class SettingsView:
    """
    A SettingsView provides access to on-chain configuration settings.

    The Config view provides access to configuration settings stored at a
    particular merkle tree root. This access is read-only.
    """

    def __init__(self, state_view):
        """Creates a SettingsView, given a StateView for merkle tree access.

        Args:
            state_view (:obj:`StateView`): a state view
        """
        self._state_view = state_view

    @lru_cached_method(maxsize=128)
    def get_setting(self, key, default_value=None, value_type=str):
        """Get the setting stored at the given key.

        Args:
            key (str): the setting key
            default_value (str, optional): The default value, if none is
                found. Defaults to None.
            value_type (function, optional): The type of a setting value.
                Defaults to `str`.

        Returns:
            str: The value of the setting if found, default_value
            otherwise.
        """
        try:
            state_entry = self._state_view.get(
                SettingsView.setting_address(key))
        except KeyError:
            return default_value

        if state_entry is not None:
            setting = Setting()
            setting.ParseFromString(state_entry)
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
            value_type (function, optional): The type of a setting value in the
                list. Defaults to `str`.

        Returns:
            list of str: The values of the setting if found, default_value
            otherwise.

            If a value is found, it is split using the given delimiter.
        """
        value = self.get_setting(key)
        if value is not None:
            setting_list = [value_type(v) for v in value.split(delimiter)]
        else:
            setting_list = default_value

        return setting_list

    @staticmethod
    @lru_cache(maxsize=128)
    def setting_address(key):
        """Computes the radix address for the given setting key.

        Keys are broken into four parts, based on the dots in the string. For
        example, the key `a.b.c` address is computed based on `a`, `b`, `c` and
        the empty string. A longer key, for example `a.b.c.d.e`, is still
        broken into four parts, but the remaining pieces are in the last part:
        `a`, `b`, `c` and `d.e`.

        Each of these peices has a short hash computed (the first 16 characters
        of its SHA256 hash in hex), and is joined into a single address, with
        the config namespace (`000000`) added at the beginning.

        Args:
            key (str): the setting key
        Returns:
            str: the computed address
        """
        # split the key into 4 parts, maximum
        key_parts = key.split('.', maxsplit=_MAX_KEY_PARTS - 1)
        # compute the short hash of each part
        addr_parts = [_short_hash(x.encode()) for x in key_parts]
        # pad the parts with the empty hash, if needed
        addr_parts.extend([_EMPTY_PART] * (_MAX_KEY_PARTS - len(addr_parts)))

        return CONFIG_STATE_NAMESPACE + ''.join(addr_parts)


class SettingsViewFactory:
    """Creates SettingsView instances.
    """

    def __init__(self, state_view_factory):
        """Creates this view factory with a given state view factory.

        Args:
            state_view_factory (:obj:`StateViewFactory`): the state view
                factory
        """
        self._state_view_factory = state_view_factory

    def create_settings_view(self, state_root_hash):
        """
        Returns:
            SettingsView: the configuration view at the given state root.
        """
        return SettingsView(
            self._state_view_factory.create_view(state_root_hash))
