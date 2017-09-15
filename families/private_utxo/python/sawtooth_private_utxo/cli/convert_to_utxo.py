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
import time

from sawtooth_private_utxo.cli.common import create_client
from sawtooth_private_utxo.common.addressing import Addressing
from sawtooth_private_utxo.cli.enclave_simulator.enclave import\
    generate_utxo_document


LOGGER = logging.getLogger(__name__)


def add_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('convert_to_utxo', parents=[parent_parser])

    parser.add_argument(
        '--type',
        type=str,
        required=True,
        help='the address of the asset type to transfer.')

    parser.add_argument(
        '--amount',
        type=int,
        required=True,
        help='the amount of the asset to issue to the participant.')

    parser.add_argument(
        '--utxo-document',
        type=str,
        required=True,
        help='the name of the file to write the UTXO document to.')


def run(args, config):
    """
    Send CONVERT_TO_UTXO transaction to the server
    """
    LOGGER.info('CONVERT_TO_UTXO')

    client = create_client(config)
    nonce = str(time.time())

    output_uxto_doc = generate_utxo_document(
        client.public_key, args.type, args.amount, nonce)

    output_uxto_doc_str = output_uxto_doc.SerializeToString()
    output_uxto = Addressing.utxo_address(output_uxto_doc_str)

    with open(args.utxo_document, "wb") as in_file:
        in_file.write(output_uxto_doc_str)

    result = client.convert_to_utxo(
        args.type, args.amount, nonce, output_uxto, args.wait)
    print(result)


CONVERT_TO_UTXO_HANDLER = {
    'name': 'convert_to_utxo',
    'parser': add_parser,
    'run': run
}
