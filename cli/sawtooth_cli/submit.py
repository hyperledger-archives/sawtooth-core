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

import logging
import time

from sawtooth_cli.exceptions import CliException
from sawtooth_cli.rest_client import RestClient
import sawtooth_cli.protobuf.batch_pb2 as batch_pb2

LOGGER = logging.getLogger(__file__)


def _split_batch_list(args, batch_list):
    new_list = []
    for batch in batch_list.batches:
        new_list.append(batch)
        if len(new_list) == args.batch_size_limit:
            yield batch_pb2.BatchList(batches=new_list)
            new_list = []
    if len(new_list) > 0:
        yield batch_pb2.BatchList(batches=new_list)


def do_submit(args):

    try:
        with open(args.filename, mode='rb') as fd:
            batches = batch_pb2.BatchList()
            batches.ParseFromString(fd.read())
    except IOError as e:
        raise CliException(e)

    rest_client = RestClient(args.url)

    start = time.time()

    for batch_list in _split_batch_list(args, batches):
        rest_client.send_batches(batch_list)

    stop = time.time()

    print("batches: {} batch/sec: {}".format(
        str(len(batches.batches)),
        len(batches.batches) / (stop - start)))


def add_submit_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'submit',
        parents=[parent_parser])

    parser.add_argument(
        '-f', '--filename',
        type=str,
        help='location of input file',
        default='batches.intkey')

    parser.add_argument(
        '-U', '--url',
        type=str,
        help='connection URL for validator',
        default='http://localhost:8080')

    parser.add_argument(
        '--batch-size-limit',
        type=int,
        help='batches are split for processing if they exceed this size',
        default=100
    )
