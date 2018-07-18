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

import argparse
import logging
import time
import getpass
from base64 import b64encode

from http.client import RemoteDisconnected
import concurrent.futures
from concurrent.futures import wait
import requests
from sawtooth_sdk.protobuf import batch_pb2

LOGGER = logging.getLogger(__file__)


def post_batches(url, auth_info, batches):
    data = batches.SerializeToString()
    headers = {'Content-Type': 'application/octet-stream'}
    headers['Content-Length'] = str(len(data))
    if auth_info is not None:
        headers['Authorization'] = 'Basic {}'.format(auth_info)

    try:
        result = requests.post(url + "/batches", data, headers=headers)
        result.raise_for_status()
        code, json_result = (result.status_code, result.json())
        if code not in (200, 201, 202):
            LOGGER.warning("(%s): %s", code, json_result)
        return (code, json_result)
    except requests.exceptions.HTTPError as e:
        LOGGER.warning("(%s): %s", e.response.status_code, e.response.reason)
        return (e.response.status_code, e.response.reason)
    except RemoteDisconnected as e:
        LOGGER.warning(e)
    except requests.exceptions.ConnectionError as e:
        LOGGER.warning(
            'Unable to connect to "%s": make sure URL is correct', url,
        )


def _split_batch_list(batch_list):
    new_list = []
    for batch in batch_list.batches:
        new_list.append(batch)
        if len(new_list) == 100:
            yield batch_pb2.BatchList(batches=new_list)
            new_list = []
    if new_list:
        yield batch_pb2.BatchList(batches=new_list)


def do_load(args):
    auth_info = _get_auth_info(args.auth_user, args.auth_password)
    with open(args.filename, mode='rb') as fd:
        batches = batch_pb2.BatchList()
        batches.ParseFromString(fd.read())

    start = time.time()
    futures = []
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    for batch_list in _split_batch_list(batches):
        fut = executor.submit(post_batches, args.url, auth_info, batch_list)
        futures.append(fut)

    # Wait until all futures are complete
    wait(futures)

    stop = time.time()

    print("batches: {} batch/sec: {}".format(
        str(len(batches.batches)),
        len(batches.batches) / (stop - start)))


def _get_auth_info(auth_user, auth_password):
    if auth_user is not None:
        if auth_password is None:
            auth_password = getpass.getpass(prompt="Auth Password: ")
        auth_string = "{}:{}".format(auth_user, auth_password)
        b64_string = b64encode(auth_string.encode()).decode()
        return b64_string

    return None


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
        help='url for the REST API',
        default='http://localhost:8008')

    parser.add_argument(
        '--auth-user',
        type=str,
        help='username for authentication if REST API is using Basic Auth')

    parser.add_argument(
        '--auth-password',
        type=str,
        help='password for authentication if REST API is using Basic Auth')
