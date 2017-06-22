# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the 'License');
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
import time

from sys import maxsize

from sawtooth_cli import format_utils as fmt
from sawtooth_cli.rest_client import RestClient
from sawtooth_cli.exceptions import CliException
from sawtooth_cli.parent_parsers import base_http_parser
from sawtooth_cli.parent_parsers import base_list_parser
from sawtooth_cli.parent_parsers import base_show_parser
import sawtooth_cli.protobuf.batch_pb2 as batch_pb2


def add_batch_parser(subparsers, parent_parser):
    """Adds arguments parsers for the batch list, batch show and batch status
    commands

        Args:
            subparsers: Add parsers to this subparser object
            parent_parser: The parent argparse.ArgumentParser object
    """
    parser = subparsers.add_parser('batch')

    grand_parsers = parser.add_subparsers(title='grandchildcommands',
                                          dest='subcommand')
    grand_parsers.required = True
    add_batch_list_parser(grand_parsers, parent_parser)
    add_batch_show_parser(grand_parsers, parent_parser)
    add_batch_status_parser(grand_parsers, parent_parser)
    add_batch_submit_parser(grand_parsers, parent_parser)


def add_batch_list_parser(subparsers, parent_parser):
    epilog = '''details:
        Lists committed batches from newest to oldest, including their id (i.e.
    header signature), transaction count, and their signer's public key.
    '''
    subparsers.add_parser(
        'list', epilog=epilog,
        parents=[base_http_parser(), base_list_parser()],
        formatter_class=argparse.RawDescriptionHelpFormatter)


def add_batch_show_parser(subparsers, parent_parser):
    epilog = '''details:
        Shows the data for a single batch, or for a particular property within
    that batch or its header. Displays data in YAML (default), or JSON formats.
    '''
    show_parser = subparsers.add_parser(
        'show', epilog=epilog,
        parents=[base_http_parser(), base_show_parser()],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    show_parser.add_argument(
        'batch_id',
        type=str,
        help='the id (i.e. header_signature) of the batch')


def add_batch_status_parser(subparsers, parent_parser):
    epilog = '''details:
        Fetches the statuses for a set of batches.
    '''
    status_parser = subparsers.add_parser(
        'status', epilog=epilog,
        parents=[base_http_parser()])

    status_parser.add_argument(
        '--wait',
        nargs='?',
        const=maxsize,
        type=int,
        help='a time in seconds to wait for commit')

    status_parser.add_argument(
        'batch_ids',
        type=str,
        help='a comma-separated list of batch ids')

    status_parser.add_argument(
        '-F', '--format',
        action='store',
        default='yaml',
        choices=['yaml', 'json'],
        help='the format to use for printing the output (defaults to yaml)')


def add_batch_submit_parser(subparsers, parent_parser):
    submit_parser = subparsers.add_parser(
        'submit',
        parents=[base_http_parser(), parent_parser])

    submit_parser.add_argument(
        '--wait',
        nargs='?',
        const=maxsize,
        type=int,
        help='wait for batches to commit, set an integer to specify a timeout')

    submit_parser.add_argument(
        '-f', '--filename',
        type=str,
        help='location of input file',
        default='batches.intkey')

    submit_parser.add_argument(
        '--batch-size-limit',
        type=int,
        help='batches are split for processing if they exceed this size',
        default=100
    )


def do_batch(args):
    """Runs the batch list, batch show or batch status command, printing output
    to the console

        Args:
            args: The parsed arguments sent to the command at runtime
    """
    if args.subcommand == 'list':
        do_batch_list(args)

    if args.subcommand == 'show':
        do_batch_show(args)

    if args.subcommand == 'status':
        do_batch_status(args)

    if args.subcommand == 'submit':
        do_batch_submit(args)


def do_batch_list(args):
    rest_client = RestClient(args.url, args.user)
    batches = rest_client.list_batches()
    keys = ('batch_id', 'txns', 'signer')
    headers = tuple(k.upper() for k in keys)

    def parse_batch_row(batch):
        return (
            batch['header_signature'],
            len(batch.get('transactions', [])),
            batch['header']['signer_pubkey'])

    if args.format == 'default':
        fmt.print_terminal_table(headers, batches, parse_batch_row)

    elif args.format == 'csv':
        fmt.print_csv(headers, batches, parse_batch_row)

    elif args.format == 'json' or args.format == 'yaml':
        data = [{k: d for k, d in zip(keys, parse_batch_row(b))}
                for b in batches]

        if args.format == 'yaml':
            fmt.print_yaml(data)
        elif args.format == 'json':
            fmt.print_json(data)
        else:
            raise AssertionError('Missing handler: {}'.format(args.format))

    else:
        raise AssertionError('Missing handler: {}'.format(args.format))


def do_batch_show(args):
    rest_client = RestClient(args.url, args.user)
    output = rest_client.get_batch(args.batch_id)

    if args.key:
        if args.key in output:
            output = output[args.key]
        elif args.key in output['header']:
            output = output['header'][args.key]
        else:
            raise CliException(
                'key "{}" not found in batch or header'.format(args.key))

    if args.format == 'yaml':
        fmt.print_yaml(output)
    elif args.format == 'json':
        fmt.print_json(output)
    else:
        raise AssertionError('Missing handler: {}'.format(args.format))


def do_batch_status(args):
    """Runs the batch-status command, printing output to the console

        Args:
            args: The parsed arguments sent to the command at runtime
    """
    rest_client = RestClient(args.url, args.user)
    batch_ids = args.batch_ids.split(',')

    if args.wait and args.wait > 0:
        statuses = rest_client.get_statuses(batch_ids, args.wait)
    else:
        statuses = rest_client.get_statuses(batch_ids)

    if args.format == 'yaml':
        fmt.print_yaml(statuses)
    elif args.format == 'json':
        fmt.print_json(statuses)
    else:
        raise AssertionError('Missing handler: {}'.format(args.format))


def _split_batch_list(args, batch_list):
    new_list = []
    for batch in batch_list.batches:
        new_list.append(batch)
        if len(new_list) == args.batch_size_limit:
            yield batch_pb2.BatchList(batches=new_list)
            new_list = []
    if new_list:
        yield batch_pb2.BatchList(batches=new_list)


def do_batch_submit(args):

    try:
        with open(args.filename, mode='rb') as fd:
            batches = batch_pb2.BatchList()
            batches.ParseFromString(fd.read())
    except IOError as e:
        raise CliException(e)

    rest_client = RestClient(args.url, args.user)

    start = time.time()

    for batch_list in _split_batch_list(args, batches):
        rest_client.send_batches(batch_list)

    stop = time.time()

    print('batches: {},  batch/sec: {}'.format(
        str(len(batches.batches)),
        len(batches.batches) / (stop - start)))

    if args.wait and args.wait > 0:
        batch_ids = [b.header_signature for b in batches.batches]
        wait_time = 0
        start_time = time.time()

        while wait_time < args.wait:
            statuses = rest_client.get_statuses(
                batch_ids,
                args.wait - int(wait_time))
            wait_time = time.time() - start_time

            if all(s.status == 'COMMITTED' for s in statuses):
                print('All batches committed in {:.6} sec'.format(wait_time))
                return

            # Wait a moment so as not to hammer the Rest Api
            time.sleep(0.2)

        print('Wait timed out! Some batches have not yet been committed...')
        for batch_id, status in statuses.items():
            print('{:128.128}  {:10.10}'.format(batch_id, status))
        exit(1)
