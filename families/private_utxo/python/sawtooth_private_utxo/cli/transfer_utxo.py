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
import sawtooth_signing.secp256k1_signer as signing

from sawtooth_private_utxo.cli.common import create_client
from sawtooth_private_utxo.cli.enclave_simulator.enclave import transfer_utxo
from sawtooth_private_utxo.common.addressing import Addressing
from sawtooth_private_utxo.common.exceptions import PrivateUtxoException


def address_amount_pair(arg):
    # For simplity, assume arg is a pair of integers
    # separated by a comma. If you want to do more
    # validation, raise argparse.ArgumentError if you
    # encounter a problem.
    parts = arg.split(':')
    if len(parts) != 2:
        raise PrivateUtxoException(
            "invalid address:amount pair {}".format(arg))

    return (str(parts[0]), int(parts[1]))


def add_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('transfer_utxo', parents=[parent_parser])

    parser.add_argument(
        '--input',
        type=str,
        action='append',
        required=True,
        help='the name an input UTXO document.')

    parser.add_argument(
        '--recipient',
        type=address_amount_pair,
        action='append',
        required=True,
        help='the address of the recepient:amount.')


def run(args, config):
    """
    Send TRANSFER_UTXO transaction to the server
    """
    client = create_client(config)

    # load all the input documents
    input_docs = []
    input_utxo = []
    for doc_file in args.input:
        with open(doc_file, "rb") as in_file:
            encoded_doc = in_file.read()
            input_docs.append({
                'encoded_document': encoded_doc,
                'signature': signing.sign(encoded_doc, client.private_key)})
            input_utxo.append(Addressing.utxo_address(encoded_doc))

    # send all the documents and the output pairs to the enclave
    output_docs, attestation = transfer_utxo(
        input_docs, args.recipient)

    output_utxo = []
    for doc in output_docs:
        doc_file = "{}.utxo".format(doc.owner)
        with open(doc_file, "wb") as out_file:
            encoded_doc = doc.SerializeToString()
            out_file.write(encoded_doc)
            output_utxo.append(Addressing.utxo_address(encoded_doc))

    result = client.transfer_utxo(input_utxo, output_utxo, attestation,
                                  args.wait)
    print(result)


TRANSFER_UTXO_HANDLER = {
    'name': 'transfer_utxo',
    'parser': add_parser,
    'run': run
}
