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

from sawtooth_validator.journal.consensus.consensus \
    import BlockPublisherInterface
from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
import sawtooth_validator.protobuf.transaction_pb2 as txn_pb

from sawtooth_poet.poet_consensus import poet_enclave_factory as factory
from sawtooth_poet.poet_consensus.signup_info import SignupInfo
from sawtooth_poet.poet_consensus.wait_timer import WaitTimer
from sawtooth_poet.poet_consensus.wait_certificate import WaitCertificate
from sawtooth_poet.poet_consensus import utils

import sawtooth_poet_common.protobuf.validator_registry_pb2 as vr_pb

LOGGER = logging.getLogger(__name__)


class PoetBlockPublisher(BlockPublisherInterface):
    """Consensus objects provide the following services to the Journal:
    1) Build candidate blocks ( this temporary until the block types are
    combined into a single block type)
    2) Check if it is time to claim the current candidate blocks.
    3) Provide the data a signatures required for a block to be validated by
    other consensus algorithms
    """

    # HACER: For now, we need to keep some sealed signup data and serialized
    # signup information for the validator that creates the genesis block.
    # This is ony for bootstrapping the network until the genesis utility
    # adds the validator registry transaction for the genesis node.
    _sealed_signup_data = \
        b'eyJwb2V0X3ByaXZhdGVfa2V5IjogIjVKZVZXMThlU2lBV3VVQzdZWDlBVktR'\
        b'dkxGNXZ5bnUzR2lIN055ZjZNOHJpZDhQMWlUUCIsICJwb2V0X3B1YmxpY19r'\
        b'ZXkiOiAiMDM1MGRjY2YxNTlmNzYwNzkyODQxMDFkZDdjNWQ5MTliZDYxYmVm'\
        b'YzI1OGQzYjljODRhODUyOGMwYjRiY2UwOGMxIn0='
    _poet_public_key = None

    _validator_registry_namespace = \
        hashlib.sha256('validator_registry'.encode()).hexdigest()[0:6]
    _validator_map_address = \
        _validator_registry_namespace + \
        hashlib.sha256('validator_map'.encode()).hexdigest()

    def __init__(self,
                 block_cache,
                 state_view_factory,
                 batch_publisher,
                 data_dir):
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
            Returns:
                none.
        """
        super().__init__(
            block_cache,
            state_view_factory,
            batch_publisher,
            data_dir)

        self._block_cache = block_cache
        self._state_view_factory = state_view_factory
        self._batch_publisher = batch_publisher
        self._data_dir = data_dir

        self._wait_timer = None

    def _register_signup_information(self, block_header, poet_enclave_module):
        # Find the most-recent block in the block cache, if such a block
        # exists, and get its wait certificate ID
        wait_certificate_id = NULL_BLOCK_IDENTIFIER
        most_recent_block = self._block_cache.block_store.chain_head
        if most_recent_block is not None:
            wait_certificate_id = \
                utils.deserialize_wait_certificate(
                    block=most_recent_block,
                    poet_enclave_module=poet_enclave_module).identifier

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
                name='validator-{}'.format(block_header.signer_pubkey[-8:]),
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

        self._batch_publisher.send([transaction])

        LOGGER.info(
            'Register Validator Name=%s, ID=%s...%s, PoET public key=%s...%s',
            payload.name,
            payload.id[:8],
            payload.id[-8:],
            payload.signup_info.poet_public_key[:8],
            payload.signup_info.poet_public_key[-8:])

        # HACER: Once we have the consensus state implemented, we can
        # store this information in there.  For now, we will store in the
        # class so it persists for the lifetime of the validator.
        PoetBlockPublisher._sealed_signup_data = \
            signup_info.sealed_signup_data
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

        # Using the current chain head, we need to create a state view so we
        # can create a PoET enclave.  We are going to special case this until
        # the genesis consensus is available.  We know that the genesis block
        # is special cased to have a state view constructed for it.
        state_root_hash = \
            self._block_cache.block_store.chain_head.state_root_hash \
            if self._block_cache.block_store.chain_head is not None \
            else block_header.state_root_hash
        state_view = self._state_view_factory.create_view(state_root_hash)

        poet_enclave_module = \
            factory.PoetEnclaveFactory.get_poet_enclave_module(state_view)

        # HACER: Once we have PoET consensus state, we should be looking in
        # there for the sealed signup data.  For the time being, signup
        # information will be tied to the lifetime of the validator.

        # HACER: Once the genesis utility is creating the validator registry
        # transaction, we no longer need to do this.  But for now, if we are
        # creating the genesis block, we need to re-establish the state of
        # the enclave using pre-canned sealed signup data so that we can
        # create the wait timer and certificate.  Note that this is only
        # used for the genesis block.  Going forward after the genesis block,
        # all validators will use generated signup information.
        if utils.block_id_is_genesis(block_header.previous_block_id):
            LOGGER.debug(
                'Creating genesis block, so will use sealed signup data')
            SignupInfo.unseal_signup_data(
                poet_enclave_module=poet_enclave_module,
                validator_address=block_header.signer_pubkey,
                sealed_signup_data=PoetBlockPublisher._sealed_signup_data)

        # HACER: Otherwise, if it is not the first block and we don't already
        # have a public key, we need to create signup information and create a
        # transaction to add it to the validator registry.
        elif PoetBlockPublisher._poet_public_key is None:
            self._register_signup_information(
                block_header=block_header,
                poet_enclave_module=poet_enclave_module)

        # Create a list of certificates for the wait timer.  This seems to have
        # a little too much knowledge of the WaitTimer implementation, but
        # there is no use getting more than
        # WaitTimer.certificate_sample_length wait certificates.
        certificates = \
            utils.build_certificate_list(
                block_header=block_header,
                block_cache=self._block_cache,
                poet_enclave_module=poet_enclave_module,
                maximum_number=WaitTimer.certificate_sample_length)

        # We need to create a wait timer for the block...this is what we
        # will check when we are asked if it is time to publish the block
        self._wait_timer = \
            WaitTimer.create_wait_timer(
                poet_enclave_module=poet_enclave_module,
                validator_address=block_header.signer_pubkey,
                certificates=list(certificates))

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
        # can create a PoET enclave.  We are going to special case this until
        # the genesis consensus is available.  We know that the genesis block
        # is special cased to have a state view constructed for it.
        state_root_hash = \
            self._block_cache.block_store.chain_head.state_root_hash \
            if self._block_cache.block_store.chain_head is not None \
            else block_header.state_root_hash
        state_view = self._state_view_factory.create_view(state_root_hash)

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
