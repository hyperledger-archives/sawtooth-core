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


class InvalidGenesisConsensusError(GenesisError):
    """
    Error thrown when the consensus algorithm refuses or fails to initialize
    or finalize the genesis block.
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


class PeeringException(Exception):
    """
    Indicates that a request to peer with this validator should not be allowed.
    """
    pass


class PossibleForkDetectedError(Exception):
    """Exception thrown when a possible fork has occurred while iterating
    through the block store.
    """
    pass

class ChainHeadUpdatedError(Exception):
    """Exception thrown when a the "chain_head_id" in the BlockStore does not
    match the expected value. This occurs when a BlockStore client is
    performing an operation on the BlockStore and has asserted the expected
    value of the "chain_head_id". When this occurs the client needs to abandon
    the work it is doing that assumes the previous state of the BlockStore.
    For example the block publisher should abandon the block it was building
    on top of the previous chain head and start a new block on top of the
    new chain head.
    """
    pass