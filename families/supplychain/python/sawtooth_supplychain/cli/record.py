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
from sawtooth_supplychain.cli.common import create_client
from sawtooth_supplychain.common.exceptions import SupplyChainException


def add_record_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('record', parents=[parent_parser])
    record_subparsers = parser.add_subparsers(
        title='subcommands', dest='record_command')
    add_record_create_parser(record_subparsers)
    add_record_list_parser(record_subparsers)
    add_record_show_parser(record_subparsers)


def add_record_create_parser(subparsers):
    parser = subparsers.add_parser(
        'create',
        help='Create an new Record')

    parser.add_argument(
        'identifier',
        type=str,
        help='The identifier for the record')


def add_record_list_parser(subparsers):
    subparsers.add_parser(
        'list',
        help='Show a list of all the Records')


def add_record_show_parser(subparsers):
    parser = subparsers.add_parser(
        'show',
        help='Show a Record')

    parser.add_argument(
        'name',
        type=str,
        help='The identifier for the Record to show')


def do_record(args, config):
    if args.record_command == 'create':
        do_record_create(args, config)
    elif args.record_command == 'list':
        do_record_list(args, config)
    elif args.record_command == 'show':
        do_record_show(args, config)
    else:
        raise SupplyChainException('invalid command: {}'.format(args.command))


def do_record_create(args, config):
    identifier = args.identifier

    client = create_client(config)
    response = client.record_create(identifier)
    print('Response: {}'.format(response))


def do_record_list(args, config):
    client = create_client(config)
    records = client.record_list()

    if records is not None:
        fmt = '{:20}{:10}{:64}{:64}{}'
        print('RECORDS')
        print(fmt.format('NAME', 'CREATED', 'OWNER', 'CUSTODIAN', 'FINAL'))
        for record in records:
            print(fmt.format(
                record.identifier,
                record.creation_time,
                record.owners[-1].agent_identifier,
                record.custodians[-1].agent_identifier,
                bool(record.final)))
    else:
        print('No Records Found.')


def do_record_show(args, config):
    name = args.name

    client = create_client(config)
    record = client.record_get(name)

    if record is not None:
        fmt = '{}: {}'
        print('RECORD')
        print(fmt.format('IDENTIFIER', record.identifier))
        print(fmt.format('CREATED', record.creation_time))
        print(fmt.format('OWNER', record.owners[-1].agent_identifier))
        print(fmt.format('CUSTODIAN', record.custodians[-1].agent_identifier))
        print(fmt.format('FINAL', bool(record.final)))
    else:
        print('Record not found: {}'.format(name))
