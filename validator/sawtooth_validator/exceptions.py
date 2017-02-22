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


class LocalConfigurationError(Exception):
    """
    General error thrown when a local configuration issue should prevent
    the validator from starting.
    """
    pass


class GenesisError(Exception):
    """
    General Error thrown when an error occurs as a result of an incomplete
    or erroneous genesis action.
    """
    pass


class InvalidGenesisStateError(GenesisError):
    """
    Error thrown when there is an invalid initial state during the genesis
    block generation process.
    """
    pass


class NotAvailableException(Exception):
    """
    Indicates a required service is not available and the action should be
    tried again later.
    """
    pass


class UnknownConsensusModuleError(Exception):
    """Error thrown when there is an invalid consensus module configuration.
    """
    pass
