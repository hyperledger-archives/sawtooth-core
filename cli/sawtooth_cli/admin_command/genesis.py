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
import os

from sawtooth_cli.admin_command.config import get_data_dir
from sawtooth_cli.exceptions import CliException

from sawtooth_cli.protobuf.batch_pb2 import BatchList
from sawtooth_cli.protobuf.genesis_pb2 import GenesisData
from sawtooth_cli.protobuf.settings_pb2 import SettingProposal
from sawtooth_cli.protobuf.settings_pb2 import SettingsPayload
from sawtooth_cli.protobuf.transaction_pb2 import TransactionHeader


REQUIRED_SETTINGS = [
    'sawtooth.consensus.algorithm.name',
    'sawtooth.consensus.algorithm.version']


def add_genesis_parser(subparsers, parent_parser):
    """Creates the arg parsers needed for the genesis command.
    """
    parser = subparsers.add_parser(
        'genesis',
        help='Creates the genesis.batch file for initializing the validator',
        description='Generates the genesis.batch file for '
        'initializing the validator.',
        epilog='This command generates a serialized GenesisData protobuf '
        'message and stores it in the genesis.batch file. One or more input '
        'files contain serialized BatchList protobuf messages to add to the '
        'GenesisData. The output shows the location of this file. By default, '
        'the genesis.batch file is stored in /var/lib/sawtooth. If '
        '$SAWTOOTH_HOME is set, the location is '
        '$SAWTOOTH_HOME/data/genesis.batch. Use the --output option to change '
        'the name of the file. The following settings must be present in the '
        'input batches:\n{}\n'.format(REQUIRED_SETTINGS),
        parents=[parent_parser])

    parser.add_argument(
        '-o', '--output',
        type=str,
        help='choose the output file for GenesisData')

    parser.add_argument(
        'input_file',
        nargs='*',
        type=str,
        help='file or files containing batches to add to the resulting '
        'GenesisData')

    parser.add_argument(
        '--ignore-required-settings',
        action='store_true',
        help='skip the check for settings that are required at genesis '
        '(necessary if using a settings transaction family other than '
        'sawtooth_settings)')


def do_genesis(args, data_dir=None):
    """Given the command args, take an series of input files containing
    GenesisData, combine all the batches into one GenesisData, and output the
    result into a new file.
    """

    if data_dir is None:
        data_dir = get_data_dir()

    if not os.path.exists(data_dir):
        raise CliException(
            "Data directory does not exist: {}".format(data_dir))

    genesis_batches = []
    for input_file in args.input_file:
        print('Processing {}...'.format(input_file))
        input_data = BatchList()
        try:
            with open(input_file, 'rb') as in_file:
                input_data.ParseFromString(in_file.read())
        except:
            raise CliException('Unable to read {}'.format(input_file))

        genesis_batches += input_data.batches

    _validate_depedencies(genesis_batches)
    if not args.ignore_required_settings:
        _check_required_settings(genesis_batches)

    if args.output:
        genesis_file = args.output
    else:
        genesis_file = os.path.join(data_dir, 'genesis.batch')

    print('Generating {}'.format(genesis_file))
    output_data = GenesisData(batches=genesis_batches)
    with open(genesis_file, 'wb') as out_file:
        out_file.write(output_data.SerializeToString())


def _validate_depedencies(batches):
    """Validates the transaction dependencies for the transactions contained
    within the sequence of batches. Given that all the batches are expected to
    to be executed for the genesis blocks, it is assumed that any dependent
    transaction will proceed the depending transaction.
    """
    transaction_ids = set()
    for batch in batches:
        for txn in batch.transactions:
            txn_header = TransactionHeader()
            txn_header.ParseFromString(txn.header)

            if txn_header.dependencies:
                unsatisfied_deps = [
                    id for id in txn_header.dependencies
                    if id not in transaction_ids
                ]
                if unsatisfied_deps:
                    raise CliException(
                        'Unsatisfied dependency in given transactions:'
                        ' {}'.format(unsatisfied_deps))

            transaction_ids.add(txn.header_signature)


def _check_required_settings(batches):
    """Ensure that all settings required at genesis are set."""
    required_settings = REQUIRED_SETTINGS.copy()
    for batch in batches:
        for txn in batch.transactions:
            txn_header = TransactionHeader()
            txn_header.ParseFromString(txn.header)
            if txn_header.family_name == 'sawtooth_settings':
                settings_payload = SettingsPayload()
                settings_payload.ParseFromString(txn.payload)
                if settings_payload.action == SettingsPayload.PROPOSE:
                    proposal = SettingProposal()
                    proposal.ParseFromString(settings_payload.data)
                    if proposal.setting in required_settings:
                        required_settings.remove(proposal.setting)

    if required_settings:
        raise CliException(
            'The following setting(s) are required at genesis, but were not '
            'included in the genesis batches: {}'.format(required_settings))
