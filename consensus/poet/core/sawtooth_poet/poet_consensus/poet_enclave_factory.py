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

from sawtooth_validator.state.config_view import ConfigView

from sawtooth_poet.poet_consensus.poet_config_view import PoetConfigView
from sawtooth_poet.poet_consensus import wait_timer

LOGGER = logging.getLogger(__name__)


class PoetEnclaveFactory(object):
    """PoetEnclaveFactory provides a mechanism for abstracting the loading of
    a PoET enclave module.
    """

    _lock = threading.Lock()
    _poet_enclave_module = None

    @classmethod
    def get_poet_enclave_module(cls, state_view):
        """Returns the PoET enclave module based upon the corresponding value
        set by the sawtooth_config transaction family.  If no PoET enclave
        module has been set in the configuration, it defaults to the PoET
        enclave simulator.

        Args:
            state_view (StateView): The current state view.

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
                # Get the configured PoET enclave module name, defaulting to
                # the PoET enclave simulator module if not present.
                config_view = ConfigView(state_view)
                module_name = \
                    config_view.get_setting(
                        key='sawtooth.poet.enclave_module',
                        default_value='sawtooth_poet_simulator.'
                                      'poet_enclave_simulator.'
                                      'poet_enclave_simulator')

                LOGGER.info('Load PoET enclave module: %s', module_name)

                poet_config_view = PoetConfigView(state_view)

                # For now, configure the wait timer settings based upon the
                # values in the configuration if present.
                target_wait_time = \
                    config_view.get_setting(
                        key='sawtooth.poet.target_wait_time',
                        default_value=wait_timer.WaitTimer.target_wait_time,
                        value_type=float)
                initial_wait_time = \
                    config_view.get_setting(
                        key='sawtooth.poet.initial_wait_time',
                        default_value=wait_timer.WaitTimer.initial_wait_time,
                        value_type=float)
                population_estimate_sample_size = \
                    poet_config_view.population_estimate_sample_size
                minimum_wait_time = \
                    config_view.get_setting(
                        key='sawtooth.poet.minimum_wait_time',
                        default_value=wait_timer.WaitTimer.minimum_wait_time,
                        value_type=float)

                LOGGER.info(
                    'sawtooth.poet.target_wait_time: %f',
                    target_wait_time)
                LOGGER.info(
                    'sawtooth.poet.initial_wait_time: %f',
                    initial_wait_time)
                LOGGER.info(
                    'sawtooth.poet.population_estimate_sample_size: %d',
                    poet_config_view.population_estimate_sample_size)
                LOGGER.info(
                    'sawtooth.poet.minimum_wait_time: %f',
                    minimum_wait_time)

                wait_timer.set_wait_timer_globals(
                    target_wait_time=target_wait_time,
                    initial_wait_time=initial_wait_time,
                    certificate_sample_length=population_estimate_sample_size,
                    fixed_duration_blocks=population_estimate_sample_size,
                    minimum_wait_time=minimum_wait_time)

                # Load and initialize the module
                module = importlib.import_module(module_name)
                module.initialize(**{})

                cls._poet_enclave_module = module

        return cls._poet_enclave_module
