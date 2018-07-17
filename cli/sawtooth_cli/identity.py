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

from base64 import b64decode
import csv
import getpass
import hashlib
import json
import os
import sys
import time
import random
import yaml

from sawtooth_cli.exceptions import CliException
from sawtooth_cli.rest_client import RestClient
from sawtooth_cli import tty

from sawtooth_cli.protobuf.identities_pb2 import IdentityPayload
from sawtooth_cli.protobuf.identity_pb2 import Policy
from sawtooth_cli.protobuf.identity_pb2 import PolicyList
from sawtooth_cli.protobuf.identity_pb2 import Role
from sawtooth_cli.protobuf.identity_pb2 import RoleList
from sawtooth_cli.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_cli.protobuf.transaction_pb2 import Transaction
from sawtooth_cli.protobuf.batch_pb2 import BatchHeader
from sawtooth_cli.protobuf.batch_pb2 import Batch
from sawtooth_cli.protobuf.batch_pb2 import BatchList
from sawtooth_cli.sawset import setting_key_to_address

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_signing import ParseError
from sawtooth_signing.secp256k1 import Secp256k1PrivateKey


IDENTITY_NAMESPACE = '00001d'

_MIN_PRINT_WIDTH = 15
_MAX_KEY_PARTS = 4
_FIRST_ADDRESS_PART_SIZE = 14
_ADDRESS_PART_SIZE = 16
_POLICY_PREFIX = "00"
_ROLE_PREFIX = "01"
_EMPTY_PART = hashlib.sha256("".encode()).hexdigest()[:_ADDRESS_PART_SIZE]
_REQUIRED_INPUT = setting_key_to_address("sawtooth.identity.allowed_keys")


def add_identity_parser(subparsers, parent_parser):
    """Creates the arg parsers needed for the identity command and
    its subcommands.
    """
    # identity
    parser = subparsers.add_parser(
        'identity',
        help='Works with optional roles, policies, and permissions',
        description='Provides subcommands to work with roles and policies.')

    identity_parsers = parser.add_subparsers(
        title="subcommands",
        dest="subcommand")

    identity_parsers.required = True

    # policy
    policy_parser = identity_parsers.add_parser(
        'policy',
        help='Provides subcommands to display existing policies and create '
        'new policies',
        description='Provides subcommands to list the current policies '
        'stored in state and to create new policies.')

    policy_parsers = policy_parser.add_subparsers(
        title='policy',
        dest='policy_cmd')

    policy_parsers.required = True

    # policy create
    create_parser = policy_parsers.add_parser(
        'create',
        help='Creates batches of sawtooth-identity transactions for setting a '
        'policy',
        description='Creates a policy that can be set to a role or changes a '
        'policy without resetting the role.')

    create_parser.add_argument(
        '-k', '--key',
        type=str,
        help='specify the signing key for the resulting batches')

    create_target_group = create_parser.add_mutually_exclusive_group()

    create_target_group.add_argument(
        '-o', '--output',
        type=str,
        help='specify the output filename for the resulting batches')

    create_target_group.add_argument(
        '--url',
        type=str,
        help="identify the URL of a validator's REST API",
        default='http://localhost:8008')

    create_parser.add_argument(
        '--wait',
        type=int,
        default=15,
        help="set time, in seconds, to wait for the policy to commit when "
             "submitting to the REST API.")

    create_parser.add_argument(
        'name',
        type=str,
        help='name of the new policy')

    create_parser.add_argument(
        'rule',
        type=str,
        nargs="+",
        help='rule with the format "PERMIT_KEY <key>" or "DENY_KEY <key> '
        '(multiple "rule" arguments can be specified)')

    # policy list
    list_parser = policy_parsers.add_parser(
        'list',
        help='Lists the current policies',
        description='Lists the policies that are currently set in state.')

    list_parser.add_argument(
        '--url',
        type=str,
        help="identify the URL of a validator's REST API",
        default='http://localhost:8008')

    list_parser.add_argument(
        '--format',
        default='default',
        choices=['default', 'csv', 'json', 'yaml'],
        help='choose the output format')

    # role
    role_parser = identity_parsers.add_parser(
        'role',
        help='Provides subcommands to display existing roles and create '
        'new roles',
        description='Provides subcommands to list the current roles '
        'stored in state and to create new roles.')

    role_parsers = role_parser.add_subparsers(
        title='role',
        dest='role_cmd')

    role_parsers.required = True

    # role create
    create_parser = role_parsers.add_parser(
        'create',
        help='Creates a new role that can be used to enforce permissions',
        description='Creates a new role that can be used to enforce '
        'permissions.')

    create_parser.add_argument(
        '-k', '--key',
        type=str,
        help='specify the signing key for the resulting batches')

    create_parser.add_argument(
        '--wait',
        type=int,
        default=15,
        help='set time, in seconds, to wait for a role to commit '
        'when submitting to  the REST API.')

    create_target_group = create_parser.add_mutually_exclusive_group()

    create_target_group.add_argument(
        '-o', '--output',
        type=str,
        help='specify the output filename for the resulting batches')

    create_target_group.add_argument(
        '--url',
        type=str,
        help="the URL of a validator's REST API",
        default='http://localhost:8008')

    create_parser.add_argument(
        'name',
        type=str,
        help='name of the role')

    create_parser.add_argument(
        'policy',
        type=str,
        help='identify policy that role will be restricted to')

    # role list
    list_parser = role_parsers.add_parser(
        'list',
        help='Lists the current keys and values of roles',
        description='Displays the roles that are currently set in state.')

    list_parser.add_argument(
        '--url',
        type=str,
        help="identify the URL of a validator's REST API",
        default='http://localhost:8008')

    list_parser.add_argument(
        '--format',
        default='default',
        choices=['default', 'csv', 'json', 'yaml'],
        help='choose the output format')


def do_identity(args):
    """Executes the config commands subcommands.
    """
    if args.subcommand == 'policy' and args.policy_cmd == 'create':
        _do_identity_policy_create(args)
    elif args.subcommand == 'policy' and args.policy_cmd == 'list':
        _do_identity_policy_list(args)
    elif args.subcommand == 'role' and args.role_cmd == 'create':
        _do_identity_role_create(args)
    elif args.subcommand == 'role' and args.role_cmd == 'list':
        _do_identity_role_list(args)
    else:
        raise AssertionError(
            '"{}" is not a valid subcommand of "identity"'.format(
                args.subcommand))


def _do_identity_policy_create(args):
    """Executes the 'policy create' subcommand.  Given a key file, and a
    series of entries, it generates a batch of sawtooth_identity
    transactions in a BatchList instance. The BatchList is either stored to a
    file or submitted to a validator, depending on the supplied CLI arguments.
    """
    signer = _read_signer(args.key)

    txns = [_create_policy_txn(signer, args.name, args.rule)]

    batch = _create_batch(signer, txns)

    batch_list = BatchList(batches=[batch])

    if args.output is not None:
        try:
            with open(args.output, 'wb') as batch_file:
                batch_file.write(batch_list.SerializeToString())
        except IOError as e:
            raise CliException(
                'Unable to write to batch file: {}'.format(str(e)))
    elif args.url is not None:
        rest_client = RestClient(args.url)
        rest_client.send_batches(batch_list)
        if args.wait and args.wait > 0:
            batch_id = batch.header_signature
            wait_time = 0
            start_time = time.time()

            while wait_time < args.wait:
                statuses = rest_client.get_statuses(
                    [batch_id],
                    args.wait - int(wait_time))
                wait_time = time.time() - start_time
                if statuses[0]['status'] == 'COMMITTED':
                    print(
                        'Policy committed in {:.6} sec'.format(wait_time))
                    return

                # Wait a moment so as not to hammer the Rest Api
                time.sleep(0.2)

            print('Wait timed out! Policy was not committed...')
            print('{:128.128}  {}'.format(
                batch_id,
                statuses[0]['status']))
            exit(1)
    else:
        raise AssertionError('No target for create set.')


def _do_identity_policy_list(args):
    rest_client = RestClient(args.url)
    state = rest_client.list_state(subtree=IDENTITY_NAMESPACE + _POLICY_PREFIX)

    head = state['head']
    state_values = state['data']
    printable_policies = []
    for state_value in state_values:
        policies_list = PolicyList()
        decoded = b64decode(state_value['data'])
        policies_list.ParseFromString(decoded)

        for policy in policies_list.policies:
            printable_policies.append(policy)

    printable_policies.sort(key=lambda p: p.name)

    if args.format == 'default':
        tty_width = tty.width()
        for policy in printable_policies:
            # Set value width to the available terminal space, or the min width
            width = tty_width - len(policy.name) - 3
            width = width if width > _MIN_PRINT_WIDTH else _MIN_PRINT_WIDTH
            value = "Entries:\n"
            for entry in policy.entries:
                entry_string = (" " * 4) + Policy.EntryType.Name(entry.type) \
                    + " " + entry.key
                value += (entry_string[:width] + '...'
                          if len(entry_string) > width
                          else entry_string) + "\n"
            print('{}: \n  {}'.format(policy.name, value))
    elif args.format == 'csv':
        try:
            writer = csv.writer(sys.stdout, quoting=csv.QUOTE_ALL)
            writer.writerow(['POLICY NAME', 'ENTRIES'])
            for policy in printable_policies:
                output = [policy.name]
                for entry in policy.entries:
                    output.append(
                        Policy.EntryType.Name(entry.type) + " " + entry.key)
                writer.writerow(output)
        except csv.Error:
            raise CliException('Error writing CSV')
    elif args.format == 'json' or args.format == 'yaml':
        output = {}
        for policy in printable_policies:
            value = "Entries: "
            for entry in policy.entries:
                entry_string = Policy.EntryType.Name(entry.type) + " " \
                    + entry.key
                value += entry_string + " "
            output[policy.name] = value

        policies_snapshot = {
            'head': head,
            'policies': output
        }
        if args.format == 'json':
            print(json.dumps(policies_snapshot, indent=2, sort_keys=True))
        else:
            print(yaml.dump(policies_snapshot, default_flow_style=False)[0:-1])
    else:
        raise AssertionError('Unknown format {}'.format(args.format))


def _do_identity_role_create(args):
    """Executes the 'role create' subcommand.  Given a key file, a role name,
    and a policy name it generates a batch of sawtooth_identity
    transactions in a BatchList instance. The BatchList is either stored to a
    file or submitted to a validator, depending on the supplied CLI arguments.
    """
    signer = _read_signer(args.key)
    txns = [_create_role_txn(signer, args.name,
                             args.policy)]

    batch = _create_batch(signer, txns)

    batch_list = BatchList(batches=[batch])

    if args.output is not None:
        try:
            with open(args.output, 'wb') as batch_file:
                batch_file.write(batch_list.SerializeToString())
        except IOError as e:
            raise CliException(
                'Unable to write to batch file: {}'.format(str(e)))
    elif args.url is not None:
        rest_client = RestClient(args.url)
        rest_client.send_batches(batch_list)
        if args.wait and args.wait > 0:
            batch_id = batch.header_signature
            wait_time = 0
            start_time = time.time()

            while wait_time < args.wait:
                statuses = rest_client.get_statuses(
                    [batch_id],
                    args.wait - int(wait_time))
                wait_time = time.time() - start_time

                if statuses[0]['status'] == 'COMMITTED':
                    print(
                        'Role committed in {:.6} sec'.format(wait_time))
                    return

                # Wait a moment so as not to hammer the Rest Api
                time.sleep(0.2)

            print('Wait timed out! Role was not committed...')
            print('{:128.128}  {}'.format(
                batch_id,
                statuses[0]['status']))
            exit(1)
    else:
        raise AssertionError('No target for create set.')


def _do_identity_role_list(args):
    """Lists the current on-chain configuration values.
    """
    rest_client = RestClient(args.url)
    state = rest_client.list_state(subtree=IDENTITY_NAMESPACE + _ROLE_PREFIX)

    head = state['head']
    state_values = state['data']
    printable_roles = []
    for state_value in state_values:
        role_list = RoleList()
        decoded = b64decode(state_value['data'])
        role_list.ParseFromString(decoded)

        for role in role_list.roles:
            printable_roles.append(role)

    printable_roles.sort(key=lambda r: r.name)

    if args.format == 'default':
        tty_width = tty.width()
        for role in printable_roles:
            # Set value width to the available terminal space, or the min width
            width = tty_width - len(role.name) - 3
            width = width if width > _MIN_PRINT_WIDTH else _MIN_PRINT_WIDTH
            value = (role.policy_name[:width] + '...'
                     if len(role.policy_name) > width
                     else role.policy_name)
            print('{}: {}'.format(role.name, value))
    elif args.format == 'csv':
        try:
            writer = csv.writer(sys.stdout, quoting=csv.QUOTE_ALL)
            writer.writerow(['KEY', 'VALUE'])
            for role in printable_roles:
                writer.writerow([role.name, role.policy_name])
        except csv.Error:
            raise CliException('Error writing CSV')
    elif args.format == 'json' or args.format == 'yaml':
        roles_snapshot = {
            'head': head,
            'roles': {role.name: role.policy_name
                      for role in printable_roles}
        }
        if args.format == 'json':
            print(json.dumps(roles_snapshot, indent=2, sort_keys=True))
        else:
            print(yaml.dump(roles_snapshot, default_flow_style=False)[0:-1])
    else:
        raise AssertionError('Unknown format {}'.format(args.format))


def _create_policy_txn(signer, policy_name, rules):
    entries = []
    for rule in rules:
        rule = rule.split(" ")
        if rule[0] == "PERMIT_KEY":
            entry = Policy.Entry(type=Policy.PERMIT_KEY,
                                 key=rule[1])
            entries.append(entry)
        elif rule[0] == "DENY_KEY":
            entry = Policy.Entry(type=Policy.DENY_KEY,
                                 key=rule[1])
            entries.append(entry)
    policy = Policy(name=policy_name, entries=entries)
    payload = IdentityPayload(type=IdentityPayload.POLICY,
                              data=policy.SerializeToString())

    policy_address = _policy_to_address(policy_name)

    header = TransactionHeader(
        signer_public_key=signer.get_public_key().as_hex(),
        family_name='sawtooth_identity',
        family_version='1.0',
        inputs=[_REQUIRED_INPUT, policy_address],
        outputs=[policy_address],
        dependencies=[],
        payload_sha512=hashlib.sha512(
            payload.SerializeToString()).hexdigest(),
        batcher_public_key=signer.get_public_key().as_hex(),
        nonce=hex(random.randint(0, 2**64)))

    header_bytes = header.SerializeToString()

    transaction = Transaction(
        header=header_bytes,
        payload=payload.SerializeToString(),
        header_signature=signer.sign(header_bytes))

    return transaction


def _create_role_txn(signer, role_name, policy_name):
    role = Role(name=role_name, policy_name=policy_name)
    payload = IdentityPayload(type=IdentityPayload.ROLE,
                              data=role.SerializeToString())

    policy_address = _policy_to_address(policy_name)
    role_address = _role_to_address(role_name)

    header = TransactionHeader(
        signer_public_key=signer.get_public_key().as_hex(),
        family_name='sawtooth_identity',
        family_version='1.0',
        inputs=[_REQUIRED_INPUT, policy_address, role_address],
        outputs=[role_address],
        dependencies=[],
        payload_sha512=hashlib.sha512(
            payload.SerializeToString()).hexdigest(),
        batcher_public_key=signer.get_public_key().as_hex(),
        nonce=hex(random.randint(0, 2**64)))

    header_bytes = header.SerializeToString()

    transaction = Transaction(
        header=header_bytes,
        payload=payload.SerializeToString(),
        header_signature=signer.sign(header_bytes))

    return transaction


def _read_signer(key_filename):
    """Reads the given file as a hex key.

    Args:
        key_filename: The filename where the key is stored. If None,
            defaults to the default key for the current user.

    Returns:
        Signer: the signer

    Raises:
        CliException: If unable to read the file.
    """
    filename = key_filename
    if filename is None:
        filename = os.path.join(os.path.expanduser('~'),
                                '.sawtooth',
                                'keys',
                                getpass.getuser() + '.priv')

    try:
        with open(filename, 'r') as key_file:
            signing_key = key_file.read().strip()
    except IOError as e:
        raise CliException('Unable to read key file: {}'.format(str(e)))

    try:
        private_key = Secp256k1PrivateKey.from_hex(signing_key)
    except ParseError as e:
        raise CliException('Unable to read key in file: {}'.format(str(e)))

    context = create_context('secp256k1')
    crypto_factory = CryptoFactory(context)
    return crypto_factory.new_signer(private_key)


def _create_batch(signer, transactions):
    """Creates a batch from a list of transactions and a public key, and signs
    the resulting batch with the given signing key.

    Args:
        signer (:obj:`Signer`): The cryptographic signer
        transactions (list of `Transaction`): The transactions to add to the
            batch.

    Returns:
        `Batch`: The constructed and signed batch.
    """
    txn_ids = [txn.header_signature for txn in transactions]
    batch_header = BatchHeader(
        signer_public_key=signer.get_public_key().as_hex(),
        transaction_ids=txn_ids).SerializeToString()

    return Batch(
        header=batch_header,
        header_signature=signer.sign(batch_header),
        transactions=transactions)


def _to_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _role_to_address(role_name):
    # split the key into 4 parts, maximum
    key_parts = role_name.split('.', maxsplit=_MAX_KEY_PARTS - 1)

    # compute the short hash of each part
    addr_parts = [_to_hash(key_parts[0])[:_FIRST_ADDRESS_PART_SIZE]]
    addr_parts += [_to_hash(x)[:_ADDRESS_PART_SIZE] for x in
                   key_parts[1:]]
    # pad the parts with the empty hash, if needed
    addr_parts.extend([_EMPTY_PART] * (_MAX_KEY_PARTS - len(addr_parts)))
    return IDENTITY_NAMESPACE + _ROLE_PREFIX + ''.join(addr_parts)


def _policy_to_address(policy_name):
    return IDENTITY_NAMESPACE + _POLICY_PREFIX + \
        _to_hash(policy_name)[:62]
