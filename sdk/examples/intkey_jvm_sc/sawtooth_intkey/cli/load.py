#!/usr/bin/env python
#
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

import os
import sys
import time
import argparse
import cbor
import sawtooth_sdk.protobuf.batch_pb2 as batch_pb2
from sawtooth_sdk.client.stream import Stream

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__)))), 'python'))


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
    print "Do load"
    with open(args.filename) as fd:
        batches = batch_pb2.BatchList()
        batches.ParseFromString(fd.read())

    stream = Stream(args.url)
    stream.connect()

    futures = []
    start = time.time()

    for batch_list in _split_batch_list(batches):
        future = stream.send(
            message_type='system/load',
            content=batch_list.SerializeToString())
        futures.append(future)

    for future in futures:
        result = future.result()
        assert(result.message_type == 'system/load-response')

    stop = time.time()
    print "batches: {} batch/sec: {}".format(
        str(len(batches.batches)),
        len(batches.batches) / (stop - start))

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
        default='batches_jvm.intkey')

    parser.add_argument(
        '-U', '--url',
        type=str,
        help='connection URL for validator',
        default='localhost:40000')
