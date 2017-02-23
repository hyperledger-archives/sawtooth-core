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

import argparse
import logging
import time

from sawtooth_sdk.client.exceptions import ValidatorConnectionError
from sawtooth_sdk.client.stream import Stream

import sawtooth_sdk.protobuf.batch_pb2 as batch_pb2
from sawtooth_sdk.protobuf.validator_pb2 import Message


LOGGER = logging.getLogger(__file__)


def _split_batch_list(batch_list):
    new_list = []
    for batch in batch_list.batches:
        new_list.append(batch)
        if len(new_list) == 100:
            yield batch_pb2.BatchList(batches=new_list)
            new_list = []
    if len(new_list) > 0:
        yield batch_pb2.BatchList(batches=new_list)


def do_load(args):
    with open(args.filename, mode='rb') as fd:
        batches = batch_pb2.BatchList()
        batches.ParseFromString(fd.read())

    stream = Stream(args.url)
    futures = []
    start = time.time()

    for batch_list in _split_batch_list(batches):
        future = stream.send(
            message_type=Message.CLIENT_BATCH_SUBMIT_REQUEST,
            content=batch_list.SerializeToString())
        futures.append(future)

    for future in futures:
        result = future.result()
        try:
            assert result.message_type == Message.CLIENT_BATCH_SUBMIT_RESPONSE
        except ValidatorConnectionError as vce:
            LOGGER.warning("the future resolved to %s", vce)

    stop = time.time()
    print("batches: {} batch/sec: {}".format(
        str(len(batches.batches)),
        len(batches.batches) / (stop - start)))

    stream.close()


def add_load_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'load',
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        '-f', '--filename',
        type=str,
        help='location of input file',
        default='batches.intkey')

    parser.add_argument(
        '-U', '--url',
        type=str,
        help='connection URL for validator',
        default='tcp://localhost:40000')
