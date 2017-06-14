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


class PoetEnclaveModuleWrapper(object):
    """A convenience wrapper class around the PoET enclave module.  It takes
    care of automatically initializing and shutting down the enclave.  Use it
    like this:

    with PoetEnclaveModuleWrapper(enclave_module=..., config_dir=...) as mod:
        mod.function(...)

    Call PoET enclave modules as you normally would.  It couldn't be more
    simple =) and now you don't have to worry about cleaning up.
    """
    __SIMULATOR_MODULE = \
        'sawtooth_poet_simulator.poet_enclave_simulator.poet_enclave_simulator'
    __SGX_MODULE = 'sawtooth_poet_sgx.poet_enclave_sgx.poet_enclave'

    def __init__(self, enclave_module, config_dir, data_dir):
        """Create the PoET enclave wrapper

        Args:
            enclave_module (str): The type of enclave desired ("simulator" or`
                "sgx")
            config_dir (str): The directory where configuration files can be
                found
            data_dir (str): The directory where data files can be found
        """
        if enclave_module == 'simulator':
            module_name = self.__SIMULATOR_MODULE
        elif enclave_module == 'sgx':
            module_name = self.__SGX_MODULE
        else:
            raise \
                AssertionError(
                    'Unknown enclave module: {}'.format(enclave_module))

        try:
            self._poet_enclave_module = importlib.import_module(module_name)
        except ImportError as e:
            raise AssertionError(str(e))

        self._poet_enclave_module.initialize(config_dir, data_dir)

    def __enter__(self):
        return self._poet_enclave_module

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._poet_enclave_module.shutdown()
