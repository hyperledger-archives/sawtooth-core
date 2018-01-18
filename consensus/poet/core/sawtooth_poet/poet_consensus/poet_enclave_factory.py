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

import threading
import importlib
import logging

from sawtooth_poet.poet_consensus.poet_settings_view import PoetSettingsView

LOGGER = logging.getLogger(__name__)


class PoetEnclaveFactory(object):
    """PoetEnclaveFactory provides a mechanism for abstracting the loading of
    a PoET enclave module.
    """

    _lock = threading.Lock()
    _poet_enclave_module = None

    @classmethod
    def get_poet_enclave_module(cls, state_view, config_dir, data_dir):
        """Returns the PoET enclave module based upon the corresponding value
        set by the sawtooth_settings transaction family.  If no PoET enclave
        module has been set in the configuration, it defaults to the PoET
        enclave simulator.

        Args:
            state_view (StateView): The current state view.
            config_dir (str): path to location where configuration for the
                poet enclave module can be found.
            data_dir (str): path to location where data for the
                poet enclave module can be found.
        Returns:
            module: The configured PoET enclave module, or the PoET enclave
                simulator module if none configured.

        Raises:
            ImportError: Raised if the given module_name does
                not correspond to a consensus implementation.
        """

        with cls._lock:
            # We are only going to load the PoET enclave if we haven't already
            # done so.  Otherwise, we are just going to return the previously-
            # loaded enclave module.
            if cls._poet_enclave_module is None:
                # Get the configured PoET enclave module name.
                poet_settings_view = PoetSettingsView(state_view)
                module_name = poet_settings_view.enclave_module_name

                LOGGER.info(
                    'Load PoET enclave module: %s; '
                    'Target wait time: %f; '
                    'Initial wait time: %f; '
                    'Population estimate sample size: %d; ',
                    module_name,
                    poet_settings_view.target_wait_time,
                    poet_settings_view.initial_wait_time,
                    poet_settings_view.population_estimate_sample_size)

                # Load and initialize the module
                module = importlib.import_module(module_name)
                module.initialize(config_dir, data_dir)

                cls._poet_enclave_module = module

        return cls._poet_enclave_module
