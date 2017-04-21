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
import hashlib
import time
import json

import sawtooth_signing as signing

from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
from sawtooth_validator.journal.block_wrapper import BlockWrapper
from sawtooth_validator.journal.consensus.consensus \
    import BlockPublisherInterface
import sawtooth_validator.protobuf.transaction_pb2 as txn_pb

from sawtooth_poet.poet_consensus import poet_enclave_factory as factory
from sawtooth_poet.poet_consensus.consensus_state import ConsensusState
from sawtooth_poet.poet_consensus.consensus_state_store \
    import ConsensusStateStore
from sawtooth_poet.poet_consensus.poet_config_view import PoetConfigView
from sawtooth_poet.poet_consensus.signup_info import SignupInfo
from sawtooth_poet.poet_consensus.poet_key_state_store \
    import PoetKeyState
from sawtooth_poet.poet_consensus.poet_key_state_store \
    import PoetKeyStateStore
from sawtooth_poet.poet_consensus.wait_timer import WaitTimer
from sawtooth_poet.poet_consensus.wait_certificate import WaitCertificate
from sawtooth_poet.poet_consensus import utils

import sawtooth_poet_common.protobuf.validator_registry_pb2 as vr_pb

from sawtooth_poet_common.validator_registry_view.validator_registry_view \
    import ValidatorRegistryView

LOGGER = logging.getLogger(__name__)


class PoetBlockPublisher(BlockPublisherInterface):
    """Consensus objects provide the following services to the Journal:
    1) Build candidate blocks ( this temporary until the block types are
    combined into a single block type)
    2) Check if it is time to claim the current candidate blocks.
    3) Provide the data a signatures required for a block to be validated by
    other consensus algorithms
    """

    _poet_public_key = None
    _previous_block_id = None

    _validator_registry_namespace = \
        hashlib.sha256('validator_registry'.encode()).hexdigest()[0:6]
    _validator_map_address = \
        _validator_registry_namespace + \
        hashlib.sha256('validator_map'.encode()).hexdigest()

    def __init__(self,
                 block_cache,
                 state_view_factory,
                 batch_publisher,
                 data_dir,
                 validator_id):
        """Initialize the object, is passed (read-only) state access objects.
            Args:
                block_cache (BlockCache): Dict interface to the block cache.
                    Any predecessor block to blocks handed to this object will
                    be present in this dict.
                state_view_factory (StateViewFactory): A factory that can be
                    used to create read-only views of state for a particular
                    merkle root, in particular the state as it existed when a
                    particular block was the chain head.
                batch_publisher (BatchPublisher): An interface implementing
                    send(txn_list) which wrap the transactions in a batch and
                    broadcast that batch to the network.
                data_dir (str): path to location where persistent data for the
                    consensus module can be stored.
                validator_id (str): A unique ID for this validator
            Returns:
                none.
        """
        super().__init__(
            block_cache,
            state_view_factory,
            batch_publisher,
            data_dir,
            validator_id)

        self._block_cache = block_cache
        self._state_view_factory = state_view_factory
        self._batch_publisher = batch_publisher
        self._data_dir = data_dir
        self._validator_id = validator_id
        self._consensus_state_store = \
            ConsensusStateStore(
                data_dir=self._data_dir,
                validator_id=self._validator_id)
        self._poet_key_state_store = \
            PoetKeyStateStore(
                data_dir=self._data_dir,
                validator_id=self._validator_id)
        self._wait_timer = None

    def _register_signup_information(self, block_header, poet_enclave_module):
        # Find the most-recent block in the block cache, if such a block
        # exists, and get its wait certificate ID
        wait_certificate_id = NULL_BLOCK_IDENTIFIER
        most_recent_block = self._block_cache.block_store.chain_head
        if most_recent_block is not None:
            wait_certificate = \
                utils.deserialize_wait_certificate(
                    block=most_recent_block,
                    poet_enclave_module=poet_enclave_module)
            if wait_certificate is not None:
                wait_certificate_id = wait_certificate.identifier

        # Create signup information for this validator
        public_key_hash = \
            hashlib.sha256(
                block_header.signer_pubkey.encode()).hexdigest()
        signup_info = \
            SignupInfo.create_signup_info(
                poet_enclave_module=poet_enclave_module,
                validator_address=block_header.signer_pubkey,
                originator_public_key_hash=public_key_hash,
                most_recent_wait_certificate_id=wait_certificate_id)

        # Create the validator registry payload
        payload = \
            vr_pb.ValidatorRegistryPayload(
                verb='register',
                name='validator-{}'.format(block_header.signer_pubkey[:8]),
                id=block_header.signer_pubkey,
                signup_info=vr_pb.SignUpInfo(
                    poet_public_key=signup_info.poet_public_key,
                    proof_data=signup_info.proof_data,
                    anti_sybil_id=signup_info.anti_sybil_id),
            )
        serialized = payload.SerializeToString()

        # Create the address that will be used to look up this validator
        # registry transaction.  Seems like a potential for refactoring..
        validator_entry_address = \
            PoetBlockPublisher._validator_registry_namespace + \
            hashlib.sha256(block_header.signer_pubkey.encode()).hexdigest()

        # Create a transaction header and transaction for the validator
        # registry update amd then hand it off to the batch publisher to
        # send out.
        addresses = \
            [validator_entry_address,
             PoetBlockPublisher._validator_map_address]

        header = \
            txn_pb.TransactionHeader(
                signer_pubkey=block_header.signer_pubkey,
                family_name='sawtooth_validator_registry',
                family_version='1.0',
                inputs=addresses,
                outputs=addresses,
                dependencies=[],
                payload_encoding="application/protobuf",
                payload_sha512=hashlib.sha512(serialized).hexdigest(),
                batcher_pubkey=block_header.signer_pubkey,
                nonce=time.time().hex().encode()).SerializeToString()
        signature = \
            signing.sign(header, self._batch_publisher.identity_signing_key)

        transaction = \
            txn_pb.Transaction(
                header=header,
                payload=serialized,
                header_signature=signature)

        LOGGER.info(
            'Register Validator Name=%s, ID=%s...%s, PoET public key=%s...%s',
            payload.name,
            payload.id[:8],
            payload.id[-8:],
            payload.signup_info.poet_public_key[:8],
            payload.signup_info.poet_public_key[-8:])

        self._batch_publisher.send([transaction])

        # Store the key state so that we can look it up later if need be
        LOGGER.info(
            'Save key state PPK=%s...%s => SSD=%s...%s',
            signup_info.poet_public_key[:8],
            signup_info.poet_public_key[-8:],
            signup_info.sealed_signup_data[:8],
            signup_info.sealed_signup_data[-8:])
        self._poet_key_state_store[signup_info.poet_public_key] = \
            PoetKeyState(
                sealed_signup_data=signup_info.sealed_signup_data,
                has_been_refreshed=False)

        # Cache the PoET public key in a class to indicate that this is the
        # current public key for the PoET enclave
        PoetBlockPublisher._poet_public_key = signup_info.poet_public_key

    def initialize_block(self, block_header):
        """Do initialization necessary for the consensus to claim a block,
        this may include initiating voting activities, starting proof of work
        hash generation, or create a PoET wait timer.

        Args:
            block_header (BlockHeader): The BlockHeader to initialize.
        Returns:
            Boolean: True if the candidate block should be built. False if
            no candidate should be built.
        """
        # If the previous block ID matches our cached one, that means that we
        # have already determined that even if we initialize the requested
        # block we would not be able to claim it.  So, instead of wasting time
        # doing all of the checking again, simply short-circuit the failure so
        # that the validator can go do something more useful.
        if block_header.previous_block_id == \
                PoetBlockPublisher._previous_block_id:
            return False
        PoetBlockPublisher._previous_block_id = block_header.previous_block_id

        # Using the current chain head, we need to create a state view so we
        # can create a PoET enclave.
        state_view = \
            BlockWrapper.state_view_for_block(
                block_wrapper=self._block_cache.block_store.chain_head,
                state_view_factory=self._state_view_factory)

        poet_enclave_module = \
            factory.PoetEnclaveFactory.get_poet_enclave_module(state_view)

        # Get our validator registry entry to see what PoET public key
        # other validators think we are using.
        validator_registry_view = ValidatorRegistryView(state_view)
        validator_info = None

        try:
            validator_id = block_header.signer_pubkey
            validator_info = \
                validator_registry_view.get_validator_info(
                    validator_id=validator_id)
        except KeyError:
            pass

        # If we don't have a validator registry entry, then check our cached
        # PoET public key.  If we don't have one, then we need to sign up.
        # If we do have one, then our validator registry entry has not
        # percolated through the system, so nothing to to but wait.
        if validator_info is None:
            if PoetBlockPublisher._poet_public_key is None:
                LOGGER.debug(
                    'No public key found, so going to register new signup '
                    'information')
                self._register_signup_information(
                    block_header=block_header,
                    poet_enclave_module=poet_enclave_module)

            return False

        # Otherwise, we have a current validator registry entry.  In that
        # case, we need to make sure that we are using the same PPK that the
        # other validators think we are using.  If not, then we need to switch
        # the PoET enclave to using the correct keys.
        elif validator_info.signup_info.poet_public_key != \
                PoetBlockPublisher._poet_public_key:
            # Retrieve the key state corresponding to the PoET public key and
            # use it to re-establish the key used by the enclave.
            poet_key_state = \
                self._poet_key_state_store[
                    validator_info.signup_info.poet_public_key]

            PoetBlockPublisher._poet_public_key = \
                SignupInfo.unseal_signup_data(
                    poet_enclave_module=poet_enclave_module,
                    validator_address=block_header.signer_pubkey,
                    sealed_signup_data=poet_key_state.sealed_signup_data)

            assert PoetBlockPublisher._poet_public_key == \
                validator_info.signup_info.poet_public_key

            LOGGER.debug(
                'Switched to public key: %s...%s',
                PoetBlockPublisher._poet_public_key[:8],
                PoetBlockPublisher._poet_public_key[-8:])
            LOGGER.debug(
                'Unseal signup data: %s...%s',
                poet_key_state.sealed_signup_data[:8],
                poet_key_state.sealed_signup_data[-8:])

        consensus_state = \
            ConsensusState.consensus_state_for_block_id(
                block_id=block_header.previous_block_id,
                block_cache=self._block_cache,
                state_view_factory=self._state_view_factory,
                consensus_state_store=self._consensus_state_store,
                poet_enclave_module=poet_enclave_module)
        poet_config_view = PoetConfigView(state_view)

        # Using the consensus state for the block upon which we want to
        # build, check to see how many blocks we have claimed on this chain
        # with this PoET key.  If we have hit the key block claim limit, then
        # we need to check if the key has been refreshed.
        if consensus_state.validator_has_claimed_block_limit(
                validator_info=validator_info,
                poet_config_view=poet_config_view):
            # Because we have hit the limit, check to see if we have already
            # submitted a validator registry transaction with new signup
            # information, and therefore a new PoET public key.  If not, then
            # mark this PoET public key in the store as having been refreshed
            # and register new signup information.  Regardless, since we have
            # hit the key block claim limit, we won't even bother initializing
            # a block on this chain as it will be rejected by other
            # validators.
            poet_key_state = \
                self._poet_key_state_store[
                    PoetBlockPublisher._poet_public_key]
            if not poet_key_state.has_been_refreshed:
                LOGGER.info(
                    'Reached block claim limit for key: %s...%s',
                    PoetBlockPublisher._poet_public_key[:8],
                    PoetBlockPublisher._poet_public_key[-8:])

                sealed_signup_data = poet_key_state.sealed_signup_data
                self._poet_key_state_store[
                    PoetBlockPublisher._poet_public_key] = \
                    PoetKeyState(
                        sealed_signup_data=sealed_signup_data,
                        has_been_refreshed=True)

                self._register_signup_information(
                    block_header=block_header,
                    poet_enclave_module=poet_enclave_module)

            LOGGER.error(
                'Reject building on block %s: Validator has reached maximum '
                'number of blocks with key pair.',
                block_header.previous_block_id[:8])
            return False

        # Verify that we are abiding by the block claim delay (i.e., waiting a
        # certain number of blocks since our validator registry was added/
        # updated).
        if consensus_state.validator_is_claiming_too_early(
                validator_info=validator_info,
                block_number=block_header.block_num,
                validator_registry_view=validator_registry_view,
                poet_config_view=poet_config_view,
                block_store=self._block_cache.block_store):
            LOGGER.error(
                'Reject building on block %s: Validator has not waited long '
                'enough since registering validator information.',
                block_header.previous_block_id[:8])
            return False

        # We need to create a wait timer for the block...this is what we
        # will check when we are asked if it is time to publish the block
        previous_certificate_id = \
            utils.get_previous_certificate_id(
                block_header=block_header,
                block_cache=self._block_cache,
                poet_enclave_module=poet_enclave_module)
        wait_timer = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=poet_enclave_module,
                validator_address=block_header.signer_pubkey,
                previous_certificate_id=previous_certificate_id,
                consensus_state=consensus_state,
                poet_config_view=poet_config_view)

        # NOTE - we do the zTest after we create the wait timer because we
        # need its population estimate to see if this block would be accepted
        # by other validators based upon the zTest.

        # Check to see if by chance we were to be able to claim this block
        # if it would result in us winning more frequently than statistically
        # expected.  If so, then refuse to initialize the block because other
        # validators will not accept anyway.
        if consensus_state.validator_is_claiming_too_frequently(
                validator_info=validator_info,
                previous_block_id=block_header.previous_block_id,
                poet_config_view=poet_config_view,
                population_estimate=wait_timer.population_estimate(
                    poet_config_view=poet_config_view),
                block_cache=self._block_cache,
                poet_enclave_module=poet_enclave_module):
            LOGGER.error(
                'Reject building on block %s: Validator is claiming blocks '
                'too frequently.',
                block_header.previous_block_id[:8])
            return False

        # At this point, we know that if we are able to claim the block we are
        # initializing, we will not be prevented from doing so because of PoET
        # policies.

        self._wait_timer = wait_timer
        PoetBlockPublisher._previous_block_id = None

        LOGGER.debug('Created wait timer: %s', self._wait_timer)

        return True

    def check_publish_block(self, block_header):
        """Check if a candidate block is ready to be claimed.

        Args:
            block_header (BlockHeader): The block header for the candidate
                block that is checked for readiness for publishing.
        Returns:
            Boolean: True if the candidate block should be claimed. False if
            the block is not ready to be claimed.
        """

        # Only claim readiness if the wait timer has expired
        return self._wait_timer.has_expired(now=time.time())

    def finalize_block(self, block_header):
        """Finalize a block to be claimed. Provide any signatures and
        data updates that need to be applied to the block before it is
        signed and broadcast to the network.

        Args:
            block_header (BlockHeader): The block header for the candidate
                block that needs to be finalized.
        Returns:
            Boolean: True if the candidate block good and should be generated.
            False if the block should be abandoned.
        """
        # To compute the block hash, we are going to perform a hash using the
        # previous block ID and the batch IDs contained in the block
        hasher = hashlib.sha256(block_header.previous_block_id.encode())
        for batch_id in block_header.batch_ids:
            hasher.update(batch_id.encode())
        block_hash = hasher.hexdigest()

        # Using the current chain head, we need to create a state view so we
        # can create a PoET enclave.
        state_view = \
            BlockWrapper.state_view_for_block(
                block_wrapper=self._block_cache.block_store.chain_head,
                state_view_factory=self._state_view_factory)

        poet_enclave_module = \
            factory.PoetEnclaveFactory.get_poet_enclave_module(state_view)

        # We need to create a wait certificate for the block and then serialize
        # that into the block header consensus field.
        try:
            wait_certificate = \
                WaitCertificate.create_wait_certificate(
                    poet_enclave_module=poet_enclave_module,
                    wait_timer=self._wait_timer,
                    block_hash=block_hash)
            block_header.consensus = \
                json.dumps(wait_certificate.dump()).encode()
        except ValueError as ve:
            LOGGER.error('Failed to create wait certificate: %s', ve)
            return False

        LOGGER.debug('Created wait certificate: %s', wait_certificate)

        return True
