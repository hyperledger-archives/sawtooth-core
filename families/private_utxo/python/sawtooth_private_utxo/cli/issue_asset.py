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
import time

from sawtooth_private_utxo.common.addressing import Addressing

from sawtooth_private_utxo.cli.common import create_client


def add_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('issue_asset', parents=[parent_parser])

    parser.add_argument(
        '--name',
        type=str,
        required=True,
        help='the name of the asset to issue.')

    parser.add_argument(
        '--amount',
        type=int,
        required=True,
        help='the amount of the asset to issue to the participant.')

    parser.add_argument(
        '--nonce',
        type=str,
        help='the nonce for the asset.')


def run(args, config):
    """
    Send ISSUE_ASSET transaction to the server
    """
    client = create_client(config)
    nonce = args.nonce
    if nonce is None:
        nonce = str(time.time())

    asset_type_address = Addressing.asset_type_address(
        client.public_key, args.name, nonce)
    client.issue_asset(args.name, args.amount, nonce, args.wait)

    print("Issued {} units of asset type: {}".format(
        args.amount, asset_type_address))
    print("{")
    print("    originator: {}".format(client.public_key))
    print("    name: {}".format(args.name))
    print("    nonce: {}".format(nonce))
    print("}")


ISSUE_ASSET_HANDLER = {
    'name': 'issue_asset',
    'parser': add_parser,
    'run': run
}
