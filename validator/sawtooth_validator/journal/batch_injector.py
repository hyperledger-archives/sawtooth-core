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

import abc
import importlib

from sawtooth_validator.state.settings_view import SettingsView


class BatchInjectorFactory(object, metaclass=abc.ABCMeta):
    """The interface to implement for constructing batch injectors"""

    @abc.abstractmethod
    def create_injectors(self, previous_block_id):
        """
        Instantiate all batch injectors that are enabled.

        Returns:
            A list of BatchInjectors.
        """
        raise NotImplementedError()


class BatchInjector(object, metaclass=abc.ABCMeta):
    """The interface to implement for injecting batches during block
    publishing."""

    @abc.abstractmethod
    def block_start(self, previous_block_id):
        """Returns an ordered list of batches to inject at the beginning of the
        block. Can also return None if no batches should be injected.

        Args:
            previous_block_id (str): The signature of the previous block.

        Returns:
            A list of batches to inject.
        """
        raise NotImplementedError()


class UnknownBatchInjectorError(Exception):
    def __init__(self, injector_name):
        super().__init__("Unknown injector: %s" % injector_name)


class DefaultBatchInjectorFactory:
    def __init__(self, block_store, state_view_factory, signer):
        """
        Args:
            block_store (:obj:`BlockStore`): The block store, for passing to
                batch injectors that require it.
            state_view_factory (:obj:`StateViewFactory`): The state view
                factory, for passing to injectors that require it.
            signer (:obj:`Signer`): The cryptographic signer of the validator.
        """
        self._block_store = block_store
        self._state_view_factory = state_view_factory
        self._signer = signer

    def _read_injector_setting(self, block_id):
        state_view = self._state_view_factory.create_view(
            self._block_store[block_id].state_root_hash)
        settings_view = SettingsView(state_view)
        batch_injector_setting = settings_view.get_setting(
            "sawtooth.validator.batch_injectors")
        return [] if not batch_injector_setting \
            else batch_injector_setting.split(',')

    def create_injectors(self, chain_head_id):
        injectors = self._read_injector_setting(chain_head_id)
        return [self._create_injector(i) for i in injectors]

    def _create_injector(self, injector):
        """Returns a new batch injector"""
        if injector == "block_info":
            block_info_injector = importlib.import_module(
                "sawtooth_block_info.injector")

            return block_info_injector.BlockInfoInjector(
                self._block_store, self._state_view_factory, self._signer)

        raise UnknownBatchInjectorError(injector)
