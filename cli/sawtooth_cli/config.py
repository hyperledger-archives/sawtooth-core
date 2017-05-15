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
import datetime
import getpass
import hashlib
import json
import os
import sys
import yaml

from sawtooth_cli.exceptions import CliException
from sawtooth_cli.rest_client import RestClient

from sawtooth_cli.protobuf.config_pb2 import ConfigPayload
from sawtooth_cli.protobuf.config_pb2 import ConfigProposal
from sawtooth_cli.protobuf.config_pb2 import ConfigVote
from sawtooth_cli.protobuf.config_pb2 import ConfigCandidates
from sawtooth_cli.protobuf.setting_pb2 import Setting
from sawtooth_cli.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_cli.protobuf.transaction_pb2 import Transaction
from sawtooth_cli.protobuf.batch_pb2 import BatchHeader
from sawtooth_cli.protobuf.batch_pb2 import Batch
from sawtooth_cli.protobuf.batch_pb2 import BatchList

import sawtooth_signing as signing


CONFIG_NAMESPACE = '000000'
DEFAULT_COL_WIDTH = 15


def add_config_parser(subparsers, parent_parser):
    """Creates the arg parsers needed for the config command and
    its subcommands.
    """
    parser = subparsers.add_parser('config')

    config_parsers = parser.add_subparsers(title="subcommands",
                                           dest="subcommand")
    config_parsers.required = True

    # The following parser is for the `genesis` subcommand.
    # This command creates a batch that contains all of the initial
    # transactions for on-chain settings
    genesis_parser = config_parsers.add_parser('genesis')
    genesis_parser.add_argument(
        '-k', '--key',
        type=str,
        help='the signing key for the resulting batches '
             'and initial authorized key')

    genesis_parser.add_argument(
        '-o', '--output',
        type=str,
        default='config-genesis.batch',
        help='the name of the file to output the resulting batches')

    genesis_parser.add_argument(
        '-T', '--approval-threshold',
        type=int,
        help='the required number of votes to enable a setting change')

    genesis_parser.add_argument(
        '-A', '--authorized-key',
        type=str,
        action='append',
        help='a public key for an user authorized to submit '
             'config transactions')

    # The following parser is for the `proposal` subcommand group. These
    # commands allow the user to create proposals which may be applied
    # immediately or placed in ballot mode, depending on the current on-chain
    # settings.

    proposal_parser = config_parsers.add_parser('proposal')
    proposal_parsers = proposal_parser.add_subparsers(
        title='proposals',
        dest='proposal_cmd')
    proposal_parsers.required = True

    create_parser = proposal_parsers.add_parser(
        'create',
        help='creates batches of sawtooth-config transactions')

    create_parser.add_argument(
        '-k', '--key',
        type=str,
        help='the signing key for the resulting batches')

    create_target_group = create_parser.add_mutually_exclusive_group()
    create_target_group.add_argument(
        '-o', '--output',
        type=str,
        help='the name of the file to ouput the resulting batches')

    create_target_group.add_argument(
        '--url',
        type=str,
        help="the URL of a validator's REST API",
        default='http://localhost:8080')

    create_parser.add_argument(
        'setting',
        type=str,
        nargs='+',
        help='configuration setting, as a key/value pair: <key>=<value>')

    proposal_list_parser = proposal_parsers.add_parser(
        'list',
        help='lists the current proposed, but not active, settings')

    proposal_list_parser.add_argument(
        '--url',
        type=str,
        help="the URL of a validator's REST API",
        default='http://localhost:8080')

    proposal_list_parser.add_argument(
        '--public-key',
        type=str,
        default='',
        help='filters proposals from a particular public key.')

    proposal_list_parser.add_argument(
        '--filter',
        type=str,
        default='',
        help='filters keys that begin with this value')

    proposal_list_parser.add_argument(
        '--format',
        default='default',
        choices=['default', 'csv', 'json', 'yaml'],
        help='the format of the output')

    vote_parser = proposal_parsers.add_parser(
        'vote',
        help='votes for specific setting change proposals')

    vote_parser.add_argument(
        '--url',
        type=str,
        help="the URL of a validator's REST API",
        default='http://localhost:8080')

    vote_parser.add_argument(
        '-k', '--key',
        type=str,
        help='the signing key for the resulting transaction batch')

    vote_parser.add_argument(
        'proposal_id',
        type=str,
        help='the proposal to vote on')

    vote_parser.add_argument(
        'vote_value',
        type=str,
        choices=['accept', 'reject'],
        help='the value of the vote')

    # The following parser is for the settings subsection of commands.  These
    # commands display information about the currently applied on-chain
    # settings.

    settings_parser = config_parsers.add_parser('settings')
    settings_parsers = settings_parser.add_subparsers(
        title='settings',
        dest='settings_cmd')
    settings_parsers.required = True

    list_parser = settings_parsers.add_parser(
        'list',
        help='list the current keys and values of sawtooth-config settings')

    list_parser.add_argument(
        '--url',
        type=str,
        help="the URL of a validator's REST API",
        default='http://localhost:8080')

    list_parser.add_argument(
        '--filter',
        type=str,
        default='',
        help='filters keys that begin with this value')

    list_parser.add_argument(
        '--format',
        default='default',
        choices=['default', 'csv', 'json', 'yaml'],
        help='the format of the output')


def do_config(args):
    """Executes the config commands subcommands.
    """
    if args.subcommand == 'proposal' and args.proposal_cmd == 'create':
        _do_config_proposal_create(args)
    elif args.subcommand == 'proposal' and args.proposal_cmd == 'list':
        _do_config_proposal_list(args)
    elif args.subcommand == 'proposal' and args.proposal_cmd == 'vote':
        _do_config_proposal_vote(args)
    elif args.subcommand == 'settings' and args.settings_cmd == 'list':
        _do_config_list(args)
    elif args.subcommand == 'genesis':
        _do_config_genesis(args)
    else:
        raise AssertionError(
            '"{}" is not a valid subcommand of "config"'.format(
                args.subcommand))


def _do_config_proposal_create(args):
    """Executes the 'proposal create' subcommand.  Given a key file, and a
    series of key/value pairs, it generates batches of sawtooth_config
    transactions in a BatchList instance.  The BatchList is either stored to a
    file or submitted to a validator, depending on the supplied CLI arguments.
    """
    settings = [s.split('=', 1) for s in args.setting]

    pubkey, signing_key = _read_signing_keys(args.key)

    txns = [_create_propose_txn(pubkey, signing_key, setting)
            for setting in settings]

    batch = _create_batch(pubkey, signing_key, txns)

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
    else:
        raise AssertionError('No target for create set.')


def _do_config_proposal_list(args):
    """Executes the 'proposal list' subcommand.

    Given a url, optional filters on prefix and public key, this command lists
    the current pending proposals for settings changes.
    """
    def _accept(candidate, public_key, prefix):
        # Check to see if the first public key matches the given public key
        # (if it is not None).  This public key belongs to the user that
        # created it.
        has_pub_key = (not public_key or
                       candidate.votes[0].public_key == public_key)
        has_prefix = candidate.proposal.setting.startswith(prefix)
        return has_prefix and has_pub_key

    candidates_payload = _get_proposals(RestClient(args.url))
    candidates = [c for c in candidates_payload.candidates
                  if _accept(c, args.public_key, args.filter)]

    if args.format == 'default':
        for candidate in candidates:
            print('{}: {} => {}'.format(
                candidate.proposal_id,
                candidate.proposal.setting,
                candidate.proposal.value))
    elif args.format == 'csv':
        writer = csv.writer(sys.stdout, quoting=csv.QUOTE_ALL)
        writer.writerow(['PROPOSAL_ID', 'KEY', 'VALUE'])
        for candidate in candidates:
            writer.writerow([
                candidate.proposal_id,
                candidate.proposal.setting,
                candidate.proposal.value])
    elif args.format == 'json' or args.format == 'yaml':
        candidates_snapshot = \
            {c.proposal_id: {c.proposal.setting: c.proposal.value}
             for c in candidates}

        if args.format == 'json':
            print(json.dumps(candidates_snapshot, indent=2, sort_keys=True))
        else:
            print(yaml.dump(candidates_snapshot,
                  default_flow_style=False)[0:-1])
    else:
        raise AssertionError('Unknown format {}'.format(args.format))


def _do_config_proposal_vote(args):
    """Executes the 'proposal vote' subcommand.  Given a key file, a proposal
    id and a vote value, it generates a batch of sawtooth_config transactions
    in a BatchList instance.  The BatchList is file or submitted to a
    validator.
    """
    pubkey, signing_key = _read_signing_keys(args.key)
    rest_client = RestClient(args.url)

    proposals = _get_proposals(rest_client)

    proposal = None
    for candidate in proposals.candidates:
        if candidate.proposal_id == args.proposal_id:
            proposal = candidate
            break

    if proposal is None:
        raise CliException('No proposal exists with the given id')

    for vote_record in proposal.votes:
        if vote_record.public_key == pubkey:
            raise CliException(
                'A vote has already been recorded with this signing key')

    txn = _create_vote_txn(
        pubkey,
        signing_key,
        args.proposal_id,
        proposal.proposal.setting,
        args.vote_value)
    batch = _create_batch(pubkey, signing_key, [txn])

    batch_list = BatchList(batches=[batch])

    rest_client.send_batches(batch_list)


def _do_config_list(args):
    """Lists the current on-chain configuration values.
    """
    rest_client = RestClient(args.url)
    state = rest_client.list_state(subtree=CONFIG_NAMESPACE)

    prefix = args.filter

    head = state['head']
    state_values = state['data']
    printable_settings = []
    proposals_address = _key_to_address('sawtooth.config.vote.proposals')
    for state_value in state_values:
        if state_value['address'] == proposals_address:
            # This is completely internal setting and we won't list it here
            continue

        decoded = b64decode(state_value['data'])
        setting = Setting()
        setting.ParseFromString(decoded)

        for entry in setting.entries:
            if entry.key.startswith(prefix):
                printable_settings.append(entry)

    printable_settings.sort(key=lambda s: s.key)

    if args.format == 'default':
        for setting in printable_settings:
            value = (setting.value[:DEFAULT_COL_WIDTH] + '...'
                     if len(setting.value) > DEFAULT_COL_WIDTH
                     else setting.value)
            print('{}: {}'.format(setting.key, value))
    elif args.format == 'csv':
        try:
            writer = csv.writer(sys.stdout, quoting=csv.QUOTE_ALL)
            writer.writerow(['KEY', 'VALUE'])
            for setting in printable_settings:
                writer.writerow([setting.key, setting.value])
        except csv.Error:
            raise CliException('Error writing CSV')
    elif args.format == 'json' or args.format == 'yaml':
        settings_snapshot = {
            'head': head,
            'settings': {setting.key: setting.value
                         for setting in printable_settings}
        }
        if args.format == 'json':
            print(json.dumps(settings_snapshot, indent=2, sort_keys=True))
        else:
            print(yaml.dump(settings_snapshot, default_flow_style=False)[0:-1])
    else:
        raise AssertionError('Unknown format {}'.format(args.format))


def _do_config_genesis(args):
    pubkey, signing_key = _read_signing_keys(args.key)

    authorized_keys = args.authorized_key if args.authorized_key else [pubkey]
    if pubkey not in authorized_keys:
        authorized_keys.append(pubkey)

    txns = []

    txns.append(_create_propose_txn(
        pubkey, signing_key,
        ('sawtooth.config.vote.authorized_keys',
         ','.join(authorized_keys))))

    if args.approval_threshold is not None:
        if args.approval_threshold < 1:
            raise CliException('approval threshold must not be less than 1')

        if args.approval_threshold > len(authorized_keys):
            raise CliException(
                'approval threshold must not be greater than the number of '
                'authorized keys')

        txns.append(_create_propose_txn(
            pubkey, signing_key,
            ('sawtooth.config.vote.approval_threshold',
             str(args.approval_threshold))))

    batch = _create_batch(pubkey, signing_key, txns)
    batch_list = BatchList(batches=[batch])

    try:
        with open(args.output, 'wb') as batch_file:
            batch_file.write(batch_list.SerializeToString())
        print('Generated {}'.format(args.output))
    except IOError as e:
        raise CliException(
            'Unable to write to batch file: {}'.format(str(e)))


def _get_proposals(rest_client):
    state_leaf = rest_client.get_leaf(
        _key_to_address('sawtooth.config.vote.proposals'))

    config_candidates = ConfigCandidates()

    if state_leaf is not None:
        setting_bytes = b64decode(state_leaf['data'])
        setting = Setting()
        setting.ParseFromString(setting_bytes)

        candidates_bytes = None
        for entry in setting.entries:
            if entry.key == 'sawtooth.config.vote.proposals':
                candidates_bytes = entry.value

        if candidates_bytes is not None:
            decoded = b64decode(candidates_bytes)
            config_candidates.ParseFromString(decoded)

    return config_candidates


def _read_signing_keys(key_filename):
    """Reads the given file as a WIF formatted key.

    Args:
        key_filename: The filename where the key is stored. If None,
            defaults to the default key for the current user.

    Returns:
        tuple (str, str): the public and private key pair

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
            pubkey = signing.generate_pubkey(signing_key)

            return pubkey, signing_key
    except IOError as e:
        raise CliException('Unable to read key file: {}'.format(str(e)))


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
    batch_header = BatchHeader(signer_pubkey=pubkey,
                               transaction_ids=txn_ids).SerializeToString()

    return Batch(
        header=batch_header,
        header_signature=signing.sign(batch_header, signing_key),
        transactions=transactions
    )


def _create_propose_txn(pubkey, signing_key, setting_key_value):
    """Creates an individual sawtooth_config transaction for the given key and
    value.
    """
    setting_key, setting_value = setting_key_value
    nonce = str(datetime.datetime.utcnow().timestamp())
    proposal = ConfigProposal(
        setting=setting_key,
        value=setting_value,
        nonce=nonce)
    payload = ConfigPayload(data=proposal.SerializeToString(),
                            action=ConfigPayload.PROPOSE)

    return _make_txn(pubkey, signing_key, setting_key, payload)


def _create_vote_txn(pubkey, signing_key,
                     proposal_id, setting_key, vote_value):
    """Creates an individual sawtooth_config transaction for voting on a
    proposal for a particular setting key.
    """
    if vote_value == 'accept':
        vote_id = ConfigVote.ACCEPT
    else:
        vote_id = ConfigVote.REJECT

    vote = ConfigVote(proposal_id=proposal_id, vote=vote_id)
    payload = ConfigPayload(data=vote.SerializeToString(),
                            action=ConfigPayload.VOTE)

    return _make_txn(pubkey, signing_key, setting_key, payload)


def _make_txn(pubkey, signing_key, setting_key, payload):
    """Creates and signs a sawtooth_config transaction with with a payload.
    """
    serialized_payload = payload.SerializeToString()
    header = TransactionHeader(
        signer_pubkey=pubkey,
        family_name='sawtooth_config',
        family_version='1.0',
        inputs=_config_inputs(setting_key),
        outputs=_config_outputs(setting_key),
        dependencies=[],
        payload_encoding='application/protobuf',
        payload_sha512=hashlib.sha512(serialized_payload).hexdigest(),
        batcher_pubkey=pubkey
    ).SerializeToString()

    signature = signing.sign(header, signing_key)

    return Transaction(
        header=header,
        header_signature=signature,
        payload=serialized_payload)


def _config_inputs(key):
    """Creates the list of inputs for a sawtooth_config transaction, for a given
    setting key.
    """
    return [
        _key_to_address('sawtooth.config.vote.proposals'),
        _key_to_address('sawtooth.config.vote.authorized_keys'),
        _key_to_address('sawtooth.config.vote.approval_threshold'),
        _key_to_address(key)
    ]


def _config_outputs(key):
    """Creates the list of outputs for a sawtooth_config transaction, for a
    given setting key.
    """
    return [
        _key_to_address('sawtooth.config.vote.proposals'),
        _key_to_address(key)
    ]


def _key_to_address(key):
    """Creates the state address for a given setting key.
    """
    return CONFIG_NAMESPACE + hashlib.sha256(key.encode()).hexdigest()
