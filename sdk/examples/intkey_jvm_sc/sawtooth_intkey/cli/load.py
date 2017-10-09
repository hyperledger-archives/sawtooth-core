#
# Copyright 2016, 2017 Intel Corporation
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
import json
import logging
import concurrent.futures
from concurrent.futures import wait
import urllib.request as urllib
from urllib.error import URLError, HTTPError
import requests
from http.client import RemoteDisconnected

LOGGER = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__)))), 'python'))


def post_batches(url, batches):
    data = batches.SerializeToString()
    headers = {'Content-Type': 'application/octet-stream'}
    headers['Content-Length'] = str(len(data))

    try:
        result = requests.post(url + "/batches", data, headers=headers)
        result.raise_for_status()
        code, json_result = (result.status_code, result.json())
        if not (code == 200 or code == 201 or code == 202):
            LOGGER.warning("(%s): %s", code, json_result)
        return(code, json_result)
    except requests.exceptions.HTTPError as e:
        LOGGER.warning("(%s): %s", e.response.status_code, e.response.reason)
        return (e.response.status_code, e.response.reason)
    except RemoteDisconnected as e:
        LOGGER.warning(e)
    except requests.exceptions.ConnectionError as e:
        LOGGER.warning(
            'Unable to connect to "{}": make sure URL is correct'.format(url)
        )


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
    print("Do load")
    with open(args.filename, mode='rb') as fd:
        batches = batch_pb2.BatchList()
        batches.ParseFromString(fd.read())

    start = time.time()
    futures = []
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    for batch_list in _split_batch_list(batches):
        fut = executor.submit(post_batches, args.url, batch_list)
        futures.append(fut)

    # Wait until all futures are complete
    wait(futures)

    stop = time.time()

    print("batches: {} batch/sec: {}".format(
        str(len(batches.batches)),
        len(batches.batches) / (stop - start)))


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
        help='url for the Rest API',
        default='http://localhost:8080')
