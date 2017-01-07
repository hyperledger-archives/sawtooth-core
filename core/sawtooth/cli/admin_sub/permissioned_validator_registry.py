# Copyright 2016 Intel Corporation
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

from __future__ import print_function

import json
import logging

from gossip.common import pretty_print_dict
from sawtooth.client import SawtoothClient
from sawtooth.exceptions import ClientException

LOGGER = logging.getLogger(__name__)


class PermissionedValidatorRegistryClient(SawtoothClient):
    def __init__(self,
                 keyfile,
                 base_url='http://localhost:8800'):
        super(PermissionedValidatorRegistryClient, self).__init__(
            base_url=base_url,
            store_name='PermissionedValidatorRegistryTransaction',
            name='PermissionedValidatorRegistryClient',
            txntype_name='/PermissionedValidatorRegistryTransaction',
            msgtype_name='/ledger.transaction.PermissionedValidatorRegistry/' +
                         'Transaction',
            keyfile=keyfile)

    def get_validator_list(self):
        """
        Retrieves the endpoint list from the validator.

        Args:
            N/A

        Returns:
            A list of endpoints.  Each endpoint is an OrderedDict of values
            from EndpointRegistryTransaction.
        """

        return [validator for validator in
                self.get_all_store_objects().itervalues()]

    def send_permissioned_validator_registry_txn(self, update):
        """
        This sets up the same defaults as the Transaction so when
        signing happens in sendtxn, the same payload is signed.
        Args:
            update: dict The data associated with the Xo data model
        Returns:
            txnid: str The txnid associated with the transaction

        """
        return self.sendtxn(
            '/PermissionedValidatorRegistryTransaction',
            '/ledger.transaction.PermissionedValidatorRegistry/Transaction',
            update)


def add_validator_parser(subparsers, parent_parser):

    epilog = '''
        details:
          --config accepts a comma-separated list.
          alternatively, multiple --config options
          can be specified
        '''

    parser = subparsers.add_parser('validator-registry', epilog=epilog)

    parser.add_argument('--config',
                        help='config files to load',
                        action='append')
    parser.add_argument('--conf-dir', help='name of the config directory')
    parser.add_argument(
        '--url',
        type=str,
        help='the URL to the validator')

    parser.add_argument('--keyfile', help='Name of the key file')
    parser.add_argument('--whitelist', help='Name of the whitelist file')


def do_permissioned_validator_registry(args):

    validator_url = 'http://localhost:8800'
    if args.url is not None:
        validator_url = args.url
    client =\
        PermissionedValidatorRegistryClient(args.keyfile,
                                            base_url=validator_url)
    try:
        with open(args.whitelist) as whitelist_fd:
            permissioned_validators = json.load(whitelist_fd)
    except IOError, ex:
        raise ClientException('IOError: {}'.format(str(ex)))

    result = {}

    whitelist = permissioned_validators["WhitelistOfPermissionedValidators"]

    if 'WhitelistName' in whitelist:
        whitelist_name = whitelist['WhitelistName']
    else:
        raise ClientException('No WhitelistName')

    if 'PermissionedValidatorPublicKeys' in whitelist:
        permissioned_public_keys =\
            whitelist['PermissionedValidatorPublicKeys']

    if 'PermissionedValidatorAddrs' in whitelist:
        permissioned_addrs = whitelist['PermissionedValidatorAddrs']

    update = {
        'whitelist_name': whitelist_name,
        'verb': 'reg',
        'permissioned_public_keys': permissioned_public_keys,
        'permissioned_addrs': permissioned_addrs
    }
    result['Update'] = update
    client.send_permissioned_validator_registry_txn(result)


def do_validator_registry(args):
    do_permissioned_validator_registry(args)


def list_validator_registry(args):
    validator_url = 'http://localhost:8800'
    if args.url is not None:
        validator_url = args.url
    client =\
        PermissionedValidatorRegistryClient(keyfile=args.keyfile,
                                            base_url=validator_url)
    print(pretty_print_dict(client.get_validator_list()))
