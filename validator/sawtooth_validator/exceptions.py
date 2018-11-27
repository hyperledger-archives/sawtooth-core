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


class GenesisError(Exception):
    """
    General Error thrown when an error occurs as a result of an incomplete
    or erroneous genesis action.
    """


class InvalidGenesisStateError(GenesisError):
    """
    Error thrown when there is an invalid initial state during the genesis
    block generation process.
    """


class InvalidGenesisConsensusError(GenesisError):
    """
    Error thrown when the consensus algorithm refuses or fails to initialize
    or finalize the genesis block.
    """


class NotAvailableException(Exception):
    """
    Indicates a required service is not available and the action should be
    tried again later.
    """


class UnknownConsensusModuleError(Exception):
    """Error thrown when there is an invalid consensus module configuration.
    """


class PeeringException(Exception):
    """
    Indicates that a request to peer with this validator should not be allowed.
    """


class PossibleForkDetectedError(Exception):
    """Exception thrown when a possible fork has occurred while iterating
    through the block store.
    """


class NoProcessorVacancyError(Exception):
    """Error thrown when no processor has occupancy to handle a transaction
    """


class WaitCancelledException(Exception):
    """Exception thrown when a wait function has detected a cancellation event
    """
