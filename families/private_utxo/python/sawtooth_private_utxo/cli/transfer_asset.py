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


def add_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('transfer_asset', parents=[parent_parser])

    parser.add_argument(
        '--recipient',
        type=str,
        required=True,
        help='the address of the recipient of the asset.')

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


def run(args, config):
    """
    Send TRANSFER_ASSET transaction to the server.
    """
    client = create_client(config)
    result = client.transfer_asset(args.recipient, args.type,
                                   args.amount, args.wait)
    print(result)


TRANSFER_ASSET_HANDLER = {
    'name': 'transfer_asset',
    'parser': add_parser,
    'run': run
}
