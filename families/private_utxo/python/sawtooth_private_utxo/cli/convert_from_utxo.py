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
from sawtooth_private_utxo.cli.common import create_client

from sawtooth_private_utxo.protobuf.utxo_document_pb2 import UtxoDocument


def add_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'convert_from_utxo', parents=[parent_parser])

    parser.add_argument(
        '--utxo-document',
        type=str,
        required=True,
        help='the name of the file to read the UTXO document from.')


def run(args, config):
    """
    Send CONVERT_FROM_UTXO transaction to the server
    """
    client = create_client(config)

    uxto_document = UtxoDocument()
    with open(args.utxo_document, "rb") as in_file:
        uxto_document.ParseFromString(in_file.read())

    result = client.convert_from_utxo(uxto_document, args.wait)
    print(result)


CONVERT_FROM_UTXO_HANDLER = {
    'name': 'convert_from_utxo',
    'parser': add_parser,
    'run': run
}
