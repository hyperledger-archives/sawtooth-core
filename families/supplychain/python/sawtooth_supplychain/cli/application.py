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
import argparse

from sawtooth_supplychain.cli.common import create_client
from sawtooth_supplychain.common.exceptions import SupplyChainException
from sawtooth_supplychain.protobuf.application_pb2 import Application


def add_application_accept_parser(subparsers, parent_parser):
    subparsers.add_parser(
        'accept', parents=[parent_parser],
        help='Accept an open Application')


def add_application_cancel_parser(subparsers, parent_parser):
    subparsers.add_parser(
        'cancel', parents=[parent_parser],
        help='Cancel an Application that you opened.')


def add_application_create_parser(subparsers, parent_parser):
    subparsers.add_parser(
        'create', parents=[parent_parser],
        help='Open an new Application')


def add_application_list_parser(subparsers, parent_parser):
    subparsers.add_parser(
        'list', parents=[parent_parser],
        help='List all the applications')


def add_application_reject_parser(subparsers, parent_parser):
    subparsers.add_parser(
        'reject', parents=[parent_parser],
        help='Reject an open Application')


def add_application_show_parser(subparsers, parent_parser):
    subparsers.add_parser(
        'show', parents=[parent_parser],
        help='Show an open application ')


def create_txn_parent_parser(parent_parser):
    txn_parent_parser = argparse.ArgumentParser(
        add_help=False,
        parents=[parent_parser])
    txn_parent_parser.add_argument(
        'record',
        type=str,
        help='The record identifer for the application.')
    txn_parent_parser.add_argument(
        '--type',
        type=str,
        required=True,
        help='The application type: {}'.format(repr(Application.Type.keys())))
    return txn_parent_parser


def create_txn_parent_parser_with_applicant(parent_parser):
    txn_parent_parser = argparse.ArgumentParser(
        add_help=False,
        parents=[parent_parser])
    txn_parent_parser.add_argument(
        '--applicant',
        type=str,
        required=True,
        help='The applicant of the application.')
    return txn_parent_parser


def add_application_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('application')
    application_subparsers = parser.add_subparsers(
        title='subcommands', dest='application_command')

    txn_parent_parser = create_txn_parent_parser(parent_parser)
    txn_parent_parser_app = create_txn_parent_parser_with_applicant(
        txn_parent_parser)

    add_application_accept_parser(application_subparsers,
                                  txn_parent_parser_app)
    add_application_cancel_parser(application_subparsers, txn_parent_parser)
    add_application_create_parser(application_subparsers, txn_parent_parser)
    add_application_list_parser(application_subparsers, parent_parser)
    add_application_reject_parser(application_subparsers,
                                  txn_parent_parser_app)
    add_application_show_parser(application_subparsers, txn_parent_parser_app)


def do_application(args, config):
    if args.application_command == 'create':
        do_application_create(args, config)
    elif args.application_command == 'accept':
        do_application_accept(args, config)
    elif args.application_command == 'reject':
        do_application_reject(args, config)
    elif args.application_command == 'cancel':
        do_application_cancel(args, config)
    elif args.application_command == 'list':
        do_application_list(args, config)
    elif args.application_command == 'show':
        do_application_show(args, config)
    else:
        raise SupplyChainException('invalid command: {}'.format(args.command))


def do_application_create(args, config):
    record = args.record
    application_type = Application.Type.Value(args.type)

    client = create_client(config)
    response = client.application_create(record, application_type)
    print('Response: {}'.format(response))


def do_application_accept(args, config):
    record = args.record
    applicant = args.applicant
    application_type = Application.Type.Value(args.type)

    client = create_client(config)
    response = client.application_accept(record, applicant, application_type)
    print('Response: {}'.format(response))


def do_application_cancel(args, config):
    record = args.record
    application_type = Application.Type.Value(args.type)

    client = create_client(config)

    response = client.application_cancel(record, application_type)
    print('Response: {}'.format(response))


def do_application_reject(args, config):
    record = args.record
    applicant = args.applicant
    application_type = Application.Type.Value(args.type)

    client = create_client(config)
    response = client.application_reject(record, applicant, application_type)
    print('Response: {}'.format(response))


def do_application_list(args, config):
    client = create_client(config)

    applications = client.application_list()

    if applications is not None:
        fmt = '{:20}{:64} {:10}{:10}{:10}{}'
        print('APPLICATIONS')
        print(fmt.format('RECORD', 'APPLICANT',
                         'CREATED', 'TYPE', 'STATUS', 'TERMS'))
        for application in applications:
            print(fmt.format(application.record_identifier,
                             application.applicant,
                             application.creation_time,
                             Application.Type.Name(application.type),
                             Application.Status.Name(application.status),
                             application.terms))
    else:
        print('No Applications Found.')


def do_application_show(args, config):
    record = args.record
    applicant = args.applicant
    application_type = Application.Type.Value(args.type)

    client = create_client(config)
    application = client.application_get(record, applicant, application_type)

    if application is not None:
        fmt = '{:15}: {}'
        print('APPLICATION')
        print(fmt.format('RECORD', application.record_identifier))
        print(fmt.format('APPLICANT', application.applicant))
        print(fmt.format('CREATED', application.creation_time))
        print(fmt.format('TYPE', Application.Type.Name(application.type)))
        print(fmt.format('STATUS',
                         Application.Status.Name(application.status)))
        print(fmt.format('TERMS', application.terms))
    else:
        print('Application not found: {} {} {}'.format(
            record,
            applicant,
            Application.Status.Name(application_type)))
