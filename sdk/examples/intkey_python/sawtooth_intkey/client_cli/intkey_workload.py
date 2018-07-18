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
import logging
import random
import threading
from collections import namedtuple
from datetime import datetime
from http.client import RemoteDisconnected
import getpass
from base64 import b64encode

import requests
from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_signing import ParseError
from sawtooth_signing.secp256k1 import Secp256k1PrivateKey
from sawtooth_intkey.client_cli.workload.workload_generator import \
    WorkloadGenerator
from sawtooth_intkey.client_cli.workload.sawtooth_workload import Workload
from sawtooth_intkey.client_cli.create_batch import create_intkey_transaction
from sawtooth_intkey.client_cli.create_batch import create_batch
from sawtooth_intkey.client_cli.exceptions import IntKeyCliException
from sawtooth_sdk.protobuf import batch_pb2

LOGGER = logging.getLogger(__name__)

IntKeyState = namedtuple('IntKeyState', ['name', 'url', 'value'])


def post_batches(url, batches, auth_info=None):
    data = batches.SerializeToString()
    headers = {'Content-Type': 'application/octet-stream'}
    headers['Content-Length'] = str(len(data))
    if auth_info:
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
            'Unable to connect to "%s": make sure URL is correct', url
        )


class IntKeyWorkload(Workload):
    """
    This workload is for the Sawtooth Integer Key transaction family.  In
    order to guarantee that batches of transactions are submitted at a
    relatively constant rate, when the transaction callbacks occur the
    following actions occur:

    1.  If there are no pending batches (on_all_batches_committed),
        a new key is created.
    2.  If a batch is committed, the corresponding key is > 1000000
        either an increment is made (if < 10000000) or a new
        key is created (if >= 10000000).
    3.  If a batch's status has been checked and it has not been
        committed, create a key (to get a new batch) and let
        the simulator know that the old transaction should be put back in
        the queue to be checked again if it is pending.
    """

    def __init__(self, delegate, args):
        super(IntKeyWorkload, self).__init__(delegate, args)
        self._auth_info = args.auth_info
        self._urls = []
        self._pending_batches = {}
        self._lock = threading.Lock()
        self._delegate = delegate
        self._deps = {}
        context = create_context('secp256k1')
        crypto_factory = CryptoFactory(context=context)
        if args.key_file is not None:
            try:
                with open(args.key_file, 'r') as infile:
                    signing_key = infile.read().strip()
                private_key = Secp256k1PrivateKey.from_hex(signing_key)

                self._signer = crypto_factory.new_signer(
                    private_key=private_key)
            except ParseError as pe:
                raise IntKeyCliException(str(pe))
            except IOError as ioe:
                raise IntKeyCliException(str(ioe))
        else:
            self._signer = crypto_factory.new_signer(
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
                self._pending_batches = \
                    {t: g for t, g in self._pending_batches.items()
                     if g.url != url}

    def on_all_batches_committed(self):
        self._create_new_key()

    def on_batch_committed(self, batch_id):
        with self._lock:
            key = self._pending_batches.pop(batch_id, None)

        if key is not None:
            if key.value < 1000000:
                txn = create_intkey_transaction(
                    verb="inc",
                    name=key.name,
                    value=1,
                    deps=[self._deps[key.name]],
                    signer=self._signer)

                batch = create_batch(
                    transactions=[txn],
                    signer=self._signer)

                batch_id = batch.header_signature

                batch_list = batch_pb2.BatchList(batches=[batch])

                (code, _) = post_batches(key.url, batch_list,
                                         auth_info=self._auth_info)

                if code == 202:
                    with self._lock:
                        self._pending_batches[batch.header_signature] = \
                            IntKeyState(
                            name=key.name,
                            url=key.url,
                            value=key.value + 1)
                    self.delegate.on_new_batch(batch_id, key.url)

        else:
            LOGGER.debug('Key %s completed', key.name)
            self._create_new_key()

    def on_batch_not_yet_committed(self):
        self._create_new_key()

    def _create_new_key(self):
        with self._lock:
            url = random.choice(self._urls) if self._urls else None

        batch_id = None
        if url is not None:
            name = datetime.now().isoformat()[-20:]
            txn = create_intkey_transaction(
                verb="set",
                name=name,
                value=0,
                deps=[],
                signer=self._signer)

            batch = create_batch(
                transactions=[txn],
                signer=self._signer)

            self._deps[name] = txn.header_signature
            batch_id = batch.header_signature

            batch_list = batch_pb2.BatchList(batches=[batch])
            (code, _) = post_batches(url, batch_list,
                                     auth_info=self._auth_info)

            if code == 202:
                with self._lock:
                    self._pending_batches[batch_id] = \
                        IntKeyState(name=name, url=url, value=0)

                self.delegate.on_new_batch(batch_id, url)


def do_workload(args):
    """
    Create WorkloadGenerator and IntKeyWorkload. Set IntKey workload in
    generator and run.
    """
    try:
        args.auth_info = _get_auth_info(args.auth_user, args.auth_password)
        generator = WorkloadGenerator(args)
        workload = IntKeyWorkload(generator, args)
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

    parser.add_argument('--key-file',
                        '-k',
                        type=str,
                        help="A file containing a private key "
                             "to sign transactions and batches.")
