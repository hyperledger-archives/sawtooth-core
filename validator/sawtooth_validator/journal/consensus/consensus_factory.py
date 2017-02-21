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
import importlib

from sawtooth_validator.exceptions import UnknownConsensusModuleError


class ConsensusFactory(object):
    """ConsensusFactory returns consensus modules by short name.
    """

    @staticmethod
    def get_consensus_module(module_name):
        """Returns a consensus module by name.

        Args:
            module_name (str): The name of the module to load.

        Returns:
            module: The consensus module.

        Raises:
            UnknownConsensusModuleError: Raised if the given module_name does
                not correspond to a consensus implementation.
        """
        if module_name == 'devmode':
            return importlib.import_module(
                'sawtooth_validator.journal.consensus.dev_mode.'
                'dev_mode_consensus')
        elif module_name == 'poet1':
            return importlib.import_module(
                'sawtooth_validator.journal.consensus.poet1.poet_consensus')
        else:
            raise UnknownConsensusModuleError(
                'Consensus module "{}" does not exist.'.format(module_name))
