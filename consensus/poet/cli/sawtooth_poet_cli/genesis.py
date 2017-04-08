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
from hashlib import sha512
from hashlib import sha256
import importlib
import os
import time

from sawtooth_poet_cli import config
from sawtooth_poet_cli.exceptions import CliException
from sawtooth_poet.poet_consensus.signup_info import SignupInfo
from sawtooth_poet.poet_consensus.poet_key_state_store \
    import PoetKeyState
from sawtooth_poet.poet_consensus.poet_key_state_store \
    import PoetKeyStateStore
import sawtooth_poet_common.protobuf.validator_registry_pb2 as vr_pb

import sawtooth_signing as signing

from sawtooth_validator.journal.block_wrapper import NULL_BLOCK_IDENTIFIER
import sawtooth_validator.protobuf.transaction_pb2 as txn_pb
import sawtooth_validator.protobuf.batch_pb2 as batch_pb


SIMUATOR_MODULE = \
    'sawtooth_poet_simulator.poet_enclave_simulator.poet_enclave_simulator'
SGX_MODULE = 'sawtooth_poet_sgx.poet_enclave_sgx.poet_enclave'

VR_NAMESPACE = sha256('validator_registry'.encode()).hexdigest()[0:6]
VALIDATOR_MAP_ADDRESS = \
    VR_NAMESPACE + sha256('validator_map'.encode()).hexdigest()


def add_genesis_parser(subparsers, parent_parser):
    """Add argument parser arguments for the `poet genesis` subcommand.
    """
    parser = subparsers.add_parser('genesis')

    parser.add_argument(
        '--enclave_module',
        default='simulator',
        choices=['simulator', 'sgx'],
        type=str,
        help='configure the enclave module to use')

    parser.add_argument(
        '-k', '--key',
        type=str,
        help='path to transaction signing key in WIF format')

    parser.add_argument(
        '-o', '--output',
        default='poet-genesis.batch',
        type=str,
        help='the name of the file to ouput the resulting batches')


def do_genesis(args):
    """Executes the `poet genesis` subcommand.

    This command generates a validator registry transaction and saves it to a
    file, whose location is determined by the args.  The signup data, generated
    by the selected enclave, is also stored in a well-known location.
    """
    if args.enclave_module == 'simulator':
        module_name = SIMUATOR_MODULE
    elif args.enclave_module == 'sgx':
        module_name = SGX_MODULE
    else:
        raise AssertionError('Unknown enclave module: {}'.format(
            args.enclave_module))

    try:
        poet_enclave_module = importlib.import_module(module_name)
    except ImportError as e:
        raise AssertionError(str(e))

    poet_enclave_module.initialize(**{})

    pubkey, signing_key = _read_signing_keys(args.key)

    public_key_hash = sha256(pubkey.encode()).hexdigest()
    signup_info = SignupInfo.create_signup_info(
        poet_enclave_module=poet_enclave_module,
        validator_address=pubkey,
        originator_public_key_hash=public_key_hash,
        most_recent_wait_certificate_id=NULL_BLOCK_IDENTIFIER)

    print(
        'Writing key state for PoET public key: {}...{}'.format(
            signup_info.poet_public_key[:8],
            signup_info.poet_public_key[-8:]))

    # Store the newly-created PoET key state, associating it with its
    # corresponding public key
    poet_key_state_store = \
        PoetKeyStateStore(
            data_dir=config.get_data_dir(),
            validator_id=pubkey)
    poet_key_state_store[signup_info.poet_public_key] = \
        PoetKeyState(
            sealed_signup_data=signup_info.sealed_signup_data,
            has_been_refreshed=False)

    # Create the validator registry payload
    payload = \
        vr_pb.ValidatorRegistryPayload(
            verb='register',
            name='validator-{}'.format(pubkey[:8]),
            id=pubkey,
            signup_info=vr_pb.SignUpInfo(
                poet_public_key=signup_info.poet_public_key,
                proof_data=signup_info.proof_data,
                anti_sybil_id=signup_info.anti_sybil_id),
        )
    serialized = payload.SerializeToString()

    # Create the address that will be used to look up this validator
    # registry transaction.  Seems like a potential for refactoring..
    validator_entry_address = \
        VR_NAMESPACE + sha256(pubkey.encode()).hexdigest()

    # Create a transaction header and transaction for the validator
    # registry update amd then hand it off to the batch publisher to
    # send out.
    addresses = [validator_entry_address, VALIDATOR_MAP_ADDRESS]

    header = \
        txn_pb.TransactionHeader(
            signer_pubkey=pubkey,
            family_name='sawtooth_validator_registry',
            family_version='1.0',
            inputs=addresses,
            outputs=addresses,
            dependencies=[],
            payload_encoding="application/protobuf",
            payload_sha512=sha512(serialized).hexdigest(),
            batcher_pubkey=pubkey,
            nonce=time.time().hex().encode()).SerializeToString()
    signature = signing.sign(header, signing_key)

    transaction = \
        txn_pb.Transaction(
            header=header,
            payload=serialized,
            header_signature=signature)

    batch = _create_batch(pubkey, signing_key, [transaction])
    batch_list = batch_pb.BatchList(batches=[batch])
    try:
        print('Generating {}'.format(args.output))
        with open(args.output, 'wb') as batch_file:
            batch_file.write(batch_list.SerializeToString())
    except IOError as e:
        raise CliException(
            'Unable to write to batch file: {}'.format(str(e)))


def _create_batch(pubkey, signing_key, transactions):
    """Creates a batch from a list of transactions and a public key, and signs
    the resulting batch with the given signing key.

    Args:
        pubkey (str): The public key associated with the signing key.
        signing_key (str): The private key for signing the batch.
        transactions (list of `Transaction`): The transactions to add to the
            batch.

    Returns:
        `Batch`: The constructed and signed batch.
    """
    txn_ids = [txn.header_signature for txn in transactions]
    batch_header = batch_pb.BatchHeader(
        signer_pubkey=pubkey,
        transaction_ids=txn_ids).SerializeToString()

    return batch_pb.Batch(
        header=batch_header,
        header_signature=signing.sign(batch_header, signing_key),
        transactions=transactions
    )


def _read_signing_keys(key_filename):
    """Reads the given file as a WIF formatted key.

    Args:
        key_filename: The filename where the key is stored. If None,
            defaults to the default key for the validator

    Returns:
        tuple (str, str): the public and private key pair

    Raises:
        CliException: If unable to read the file.
    """
    filename = key_filename
    if key_filename is None:
        filename = os.path.join(config.get_key_dir(), 'validator.wif')

    try:
        with open(filename, 'r') as key_file:
            signing_key = key_file.read().strip()
            pubkey = signing.generate_pubkey(signing_key)

            return pubkey, signing_key
    except IOError as e:
        raise CliException('Unable to read key file: {}'.format(str(e)))
