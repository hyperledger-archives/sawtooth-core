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

import unittest
import logging
import json
import urllib.request
import urllib.error
import base64
import hashlib
import random

import cbor

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory

from sawtooth_validator.journal.block_info_injector \
    import CONFIG_ADDRESS
from sawtooth_validator.journal.block_info_injector \
    import create_block_address
from sawtooth_validator.protobuf import block_info_pb2
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_validator.protobuf.batch_pb2 import Batch
from sawtooth_validator.protobuf.batch_pb2 import BatchList
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader

from sawtooth_integration.tests.integration_tools import wait_for_rest_apis


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
WAIT = 300

INTKEY_ADDRESS_PREFIX = hashlib.sha512(
    'intkey'.encode('utf-8')).hexdigest()[0:6]


def make_intkey_address(name):
    return INTKEY_ADDRESS_PREFIX + hashlib.sha512(
        name.encode('utf-8')).hexdigest()[-64:]


def get_blocks():
    response = query_rest_api('/blocks')
    return response['data']


def get_block_info_config():
    bic = block_info_pb2.BlockInfoConfig()
    bic.ParseFromString(get_state(CONFIG_ADDRESS))
    return bic


def get_block_info(block_num):
    bi = block_info_pb2.BlockInfo()
    bi.ParseFromString(get_state(create_block_address(block_num)))
    return bi


def get_state(address):
    response = query_rest_api('/state/%s' % address)
    return base64.b64decode(response['data'])


def post_batch(batch):
    headers = {'Content-Type': 'application/octet-stream'}
    response = query_rest_api(
        '/batches', data=batch, headers=headers)
    response = submit_request('{}&wait={}'.format(response['link'], WAIT))
    return response


def query_rest_api(suffix='', data=None, headers=None):
    if headers is None:
        headers = {}
    url = 'http://rest-api:8008' + suffix
    return submit_request(urllib.request.Request(url, data, headers))


def submit_request(request):
    response = urllib.request.urlopen(request).read().decode('utf-8')
    return json.loads(response)


def make_batches(signer, keys):
    return [create_batch(signer, [('set', k, 0)]) for k in keys]


def create_batch(signer, triples):
    transactions = [
        create_transaction(signer, verb, name, value)
        for verb, name, value in triples
    ]

    txn_signatures = [txn.header_signature for txn in transactions]

    header = BatchHeader(
        signer_public_key=signer.get_public_key().as_hex(),
        transaction_ids=txn_signatures
    ).SerializeToString()

    signature = signer.sign(header)

    batch = Batch(
        header=header,
        transactions=transactions,
        header_signature=signature)

    batch_list = BatchList(batches=[batch])

    return batch_list.SerializeToString()


def create_transaction(signer, verb, name, value):
    payload = cbor.dumps({'Verb': verb, 'Name': name, 'Value': value},
                         sort_keys=True)

    addresses = [make_intkey_address(name)]

    nonce = hex(random.randint(0, 2**64))

    txn_pub_key = signer.get_public_key().as_hex()
    header = TransactionHeader(
        signer_public_key=txn_pub_key,
        family_name="intkey",
        family_version="1.0",
        inputs=addresses,
        outputs=addresses,
        dependencies=[],
        payload_sha512=hashlib.sha512(payload).hexdigest(),
        batcher_public_key=signer.get_public_key().as_hex(),
        nonce=nonce
    )

    signature = signer.sign(header.SerializeToString())

    return Transaction(
        header=header.SerializeToString(),
        payload=payload,
        header_signature=signature)


class TestBlockInfoInjector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wait_for_rest_apis(['rest-api:8008'])

    def test_block_info_injector(self):
        """Tests that BlockInfo transactions are injected and committed for
        each block that is created by submitting intkey batches and then
        confirming that block info batches are in the final state.
        """
        context = create_context('secp256k1')
        signer = CryptoFactory(context).new_signer(
            context.new_random_private_key())

        batches = make_batches(signer, 'abcd')

        # Assert all block info transactions are committed
        for i, batch in enumerate(batches):
            post_batch(batch)
            block_info = get_block_info(i)
            self.assertEqual(block_info.block_num, i)

        # Assert config is set correctly
        config = get_block_info_config()
        self.assertEqual(config.latest_block, len(batches) - 1)
        self.assertEqual(config.oldest_block, 0)
        self.assertEqual(config.sync_tolerance, 300)
        self.assertEqual(config.target_count, 256)

        # Assert block info batches are first in the block
        for block in get_blocks()[:-1]:
            print(block['header']['block_num'])
            family_name = \
                block['batches'][0]['transactions'][0]['header']['family_name']
            self.assertEqual(family_name, 'block_info')
