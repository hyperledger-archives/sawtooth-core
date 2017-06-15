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
from sawtooth_cli.protobuf.transaction_pb2 import TransactionHeader


def add_genesis_parser(subparsers, parent_parser):
    """Creates the arg parsers needed for the genesis command.
    """
    parser = subparsers.add_parser('genesis', parents=[parent_parser])

    parser.add_argument(
        '-o', '--output',
        type=str,
        help='the name of the file to ouput the GenesisData')

    parser.add_argument(
        'input_file',
        nargs='*',
        type=str,
        help='input files of batches to add to the resulting GenesisData')


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
                unsatisfied_deps = [id for id in txn_header.dependencies
                                    if id not in transaction_ids]
                if unsatisfied_deps:
                    raise CliException(
                        'Unsatisfied dependency in given transactions:'
                        ' {}'.format(unsatisfied_deps))

            transaction_ids.add(txn.header_signature)
