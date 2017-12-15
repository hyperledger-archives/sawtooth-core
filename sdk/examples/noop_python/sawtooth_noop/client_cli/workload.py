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
import getpass
import logging
import random
import threading
from base64 import b64encode
from http.client import RemoteDisconnected

import requests
from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_sdk.workload.workload_generator import WorkloadGenerator
from sawtooth_sdk.workload.sawtooth_workload import Workload
from sawtooth_sdk.protobuf import batch_pb2
from sawtooth_noop.client_cli.create_batch import create_noop_transaction
from sawtooth_noop.client_cli.create_batch import create_batch

LOGGER = logging.getLogger(__name__)


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
        return (code, json_result)
    except requests.exceptions.HTTPError as e:
        LOGGER.warning("(%s): %s", e.response.status_code, e.response.reason)
        return (e.response.status_code, e.response.reason)
    except RemoteDisconnected as e:
        LOGGER.warning(e)
    except requests.exceptions.ConnectionError as e:
        LOGGER.warning(
            'Unable to connect to "%s": make sure URL is correct', url
        )


class NoopWorkload(Workload):
    """
    This workload is for the Sawtooth Noop transaction family.
    """

    def __init__(self, delegate, args):
        super(NoopWorkload, self).__init__(delegate, args)
        self._urls = []
        self._lock = threading.Lock()
        self._delegate = delegate
        context = create_context('secp256k1')
        self._signer = CryptoFactory(context).new_signer(
            context.new_random_private_key())

    def on_will_start(self):
        pass

    def on_will_stop(self):
        pass

    def on_validator_discovered(self, url):
        self._urls.append(url)

    def on_validator_removed(self, url):
        with self._lock:
            if url in self._urls:
                self._urls.remove(url)

    def on_all_batches_committed(self):
        self._send_batch()

    def on_batch_committed(self, batch_id):
        self._send_batch()

    def on_batch_not_yet_committed(self):
        self._send_batch()

    def _send_batch(self):
        with self._lock:
            url = random.choice(self._urls) if \
                len(self._urls) > 0 else None

        batch_id = None
        if url is not None:
            txns = []
            for _ in range(0, 1):
                txns.append(create_noop_transaction(self._signer))

            batch = create_batch(
                transactions=txns,
                signer=self._signer)

            batch_id = batch.header_signature

            batch_list = batch_pb2.BatchList(batches=[batch])
            post_batches(url, batch_list)

            self.delegate.on_new_batch(batch_id, url)


def do_workload(args):
    """
    Create WorkloadGenerator and IntKeyWorkload. Set IntKey workload in
    generator and run.
    """
    try:
        args.auth_info = _get_auth_info(args.auth_user, args.auth_password)
        generator = WorkloadGenerator(args)
        workload = NoopWorkload(generator, args)
        generator.set_workload(workload)
        generator.run()
    except KeyboardInterrupt:
        generator.stop()


def _get_auth_info(auth_user, auth_password):
    if auth_user is not None:
        if auth_password is None:
            auth_password = getpass.getpass(prompt="Auth Password: ")
        auth_string = "{}:{}".format(auth_user, auth_password)
        b64_string = b64encode(auth_string.encode()).decode()
        return b64_string
    else:
        return None


def add_workload_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'workload',
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('--rate',
                        type=int,
                        help='Batch rate in batches per second. '
                             'Should be greater then 0.',
                        default=1)
    parser.add_argument('-d', '--display-frequency',
                        type=int,
                        help='time in seconds between display of batches '
                             'rate updates.',
                        default=30)
    parser.add_argument('-u', '--urls',
                        help='comma separated urls of the REST API to connect '
                        'to.',
                        default="http://127.0.0.1:8008")
    parser.add_argument('--auth-user',
                        type=str,
                        help='username for authentication '
                             'if REST API is using Basic Auth')

    parser.add_argument('--auth-password',
                        type=str,
                        help='password for authentication '
                             'if REST API is using Basic Auth')
