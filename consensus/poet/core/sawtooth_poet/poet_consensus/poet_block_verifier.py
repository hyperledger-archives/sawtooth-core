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

import logging

from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.consensus.consensus \
    import BlockVerifierInterface

from sawtooth_poet.poet_consensus import poet_enclave_factory as factory
from sawtooth_poet.poet_consensus import utils
from sawtooth_poet.poet_consensus.wait_timer import WaitTimer

from sawtooth_poet_common.validator_registry_view.validator_registry_view \
    import ValidatorRegistryView

LOGGER = logging.getLogger(__name__)


class PoetBlockVerifier(BlockVerifierInterface):
    """BlockVerifier provides services for the Journal(ChainController) to
    determine if a block is valid (for the consensus rules) to be
    considered as part of the fork being evaluated. BlockVerifier must be
    independent of block publishing activities.
    """
    def __init__(self, block_cache, state_view_factory, data_dir):
        """Initialize the object, is passed (read-only) state access objects.
            Args:
                block_cache (BlockCache): Dict interface to the block cache.
                    Any predecessor block to blocks handed to this object will
                    be present in this dict.
                state_view_factory (StateViewFactory): A factory that can be
                    used to create read-only views of state for a particular
                    merkle root, in particular the state as it existed when a
                    particular block was the chain head.
                data_dir (str): path to location where persistent data for the
                    consensus module can be stored.
            Returns:
                none.
        """
        super().__init__(block_cache, state_view_factory, data_dir)

        self._block_cache = block_cache
        self._state_view_factory = state_view_factory
        self._data_dir = data_dir

    def verify_block(self, block_wrapper):
        """Check that the block received conforms to the consensus rules.

        Args:
            block_wrapper (BlockWrapper): The block to validate.
        Returns:
            Boolean: True if the Block is valid, False if the block is invalid.
        """
        # Get the state view for the previous block in the chain so we can
        # create a PoET enclave and validator registry view
        previous_block = None
        try:
            previous_block = \
                self._block_cache[block_wrapper.previous_block_id]
        except KeyError:
            pass

        state_view = \
            BlockWrapper.state_view_for_block(
                block_wrapper=previous_block,
                state_view_factory=self._state_view_factory)

        poet_enclave_module = \
            factory.PoetEnclaveFactory.get_poet_enclave_module(state_view)

        validator_registry_view = ValidatorRegistryView(state_view)
        try:
            # Grab the validator info based upon the block signer's public
            # key
            try:
                validator_info = \
                    validator_registry_view.get_validator_info(
                        block_wrapper.header.signer_pubkey)
            except KeyError:
                raise \
                    ValueError(
                        'Received block from an unregistered validator '
                        '{}...{}'.format(
                            block_wrapper.header.signer_pubkey[:8],
                            block_wrapper.header.signer_pubkey[-8:]))

            LOGGER.debug(
                'Block Signer Name=%s, ID=%s...%s, PoET public key='
                '%s...%s',
                validator_info.name,
                validator_info.id[:8],
                validator_info.id[-8:],
                validator_info.signup_info.poet_public_key[:8],
                validator_info.signup_info.poet_public_key[-8:])

            # Create a list of certificates leading up to this block.
            # This seems to have a little too much knowledge of the
            # WaitTimer implementation, but there is no use getting more
            # than WaitTimer.certificate_sample_length wait certificates.
            certificates = \
                utils.build_certificate_list(
                    block_header=block_wrapper.header,
                    block_cache=self._block_cache,
                    poet_enclave_module=poet_enclave_module,
                    maximum_number=WaitTimer.certificate_sample_length)

            # For the candidate block, reconstitute the wait certificate
            # and verify that it is valid
            wait_certificate = \
                utils.deserialize_wait_certificate(
                    block=block_wrapper,
                    poet_enclave_module=poet_enclave_module)
            if wait_certificate is None:
                raise \
                    ValueError(
                        'Being asked to verify a block that was not '
                        'created by PoET consensus module')

            try:
                poet_public_key = \
                    validator_info.signup_info.poet_public_key
                wait_certificate.check_valid(
                    poet_enclave_module=poet_enclave_module,
                    certificates=certificates,
                    poet_public_key=poet_public_key)
            except ValueError as ve:
                LOGGER.error('Wait certificate is not valid: %s', str(ve))
                LOGGER.warning('We will accept for now')
        except ValueError as error:
            LOGGER.error('Failed to verify block: %s', error)
            return False

        return True
