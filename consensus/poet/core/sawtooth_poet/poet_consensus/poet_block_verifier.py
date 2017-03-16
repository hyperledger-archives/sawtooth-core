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

from sawtooth_validator.journal.consensus.consensus \
    import BlockVerifierInterface

from sawtooth_validator.journal.consensus.poet.poet_consensus \
    import poet_enclave_factory as factory
from sawtooth_validator.journal.consensus.poet.poet_consensus import utils
from sawtooth_validator.journal.consensus.poet.wait_timer import WaitTimer
from sawtooth_validator.journal.consensus.poet.validator_registry_view import \
    ValidatorRegistryView

LOGGER = logging.getLogger(__name__)


class PoetBlockVerifier(BlockVerifierInterface):
    """BlockVerifier provides services for the Journal(ChainController) to
    determine if a block is valid (for the consensus rules) to be
    considered as part of the fork being evaluated. BlockVerifier must be
    independent of block publishing activities.
    """
    def __init__(self, block_cache, state_view, data_dir):
        """Initialize the object, is passed (read-only) state access objects.
            Args:
                block_cache: Dict interface to the block cache. Any predecessor
                block to blocks handed to this object will be present in this
                dict.
                state_view: A read only view of state for the last committed
                block in the chain. For the BlockVerifier this is the previous
                block in the chain.
                data_dir: path to location where persistent data for the
                consensus module can be stored.
            Returns:
                none.
        """
        super().__init__(block_cache, state_view, data_dir)

        self._block_cache = block_cache
        self._state_view = state_view
        self._poet_enclave_module = \
            factory.PoetEnclaveFactory.get_poet_enclave_module(state_view)

    def verify_block(self, block_wrapper):
        """Check that the block received conforms to the consensus rules.

        Args:
            block_wrapper (BlockWrapper): The block to validate.
        Returns:
            Boolean: True if the Block is valid, False if the block is invalid.
        """
        # HACER: If we don't have any validators registered yet, we are going
        # to immediately approve the block.  We cannot test the block's wait
        # certificate until we can retrieve the block signer's corresponding
        # public key.  We cannot do that until the genesis block is populated
        # with the "initial" validator's signup information
        validator_registry_view = ValidatorRegistryView(self._state_view)
        if len(validator_registry_view.get_validators()) > 0:
            try:
                # Grab the validator info based upon the block signer's public
                # key
                validator_info = \
                    validator_registry_view.get_validator_info(
                        block_wrapper.header.signer_pubkey)

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
                        poet_enclave_module=self._poet_enclave_module,
                        maximum_number=WaitTimer.certificate_sample_length)

                # For the candidate block, reconstitute the wait certificate
                # and verify that it is valid
                wait_certificate = \
                    utils.deserialize_wait_certificate(
                        block=block_wrapper,
                        poet_enclave_module=self._poet_enclave_module)
                wait_certificate.check_valid(
                    poet_enclave_module=self._poet_enclave_module,
                    certificates=certificates,
                    poet_public_key=validator_info.signup_info.poet_public_key)
            except KeyError:
                LOGGER.error(
                    'Attempted to verify block from validator with no '
                    'validator registry entry')
                return False
            except ValueError as ve:
                LOGGER.error('Wait certificate is not valid: %s', str(ve))
                LOGGER.warning('We will accept for now')
        else:
            LOGGER.warning(
                'Block accepted by default because no validators registered')

        return True
