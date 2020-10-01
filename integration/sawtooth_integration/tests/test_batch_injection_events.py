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


def get_family_from(batch, tx_index=0):
    return batch['transactions'][tx_index]['header']['family_name']


def get_payload_from(batch, tx_index=0):
    return batch['transactions'][tx_index]['payload']


def decode(payload):
    return cbor.loads(base64.b64decode(payload))


def get_state(address):
    response = query_rest_api('/state/%s' % address)
    return base64.b64decode(response['data'])


def post_batch(batch_list):
    headers = {'Content-Type': 'application/octet-stream'}
    response = query_rest_api(
        '/batches', data=batch_list, headers=headers)
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

    return Batch(
        header=header,
        transactions=transactions,
        header_signature=signature)


def create_batch_list(batches):
    batch_list = BatchList(batches=batches)

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


class TestBatchInjectionEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wait_for_rest_apis(['rest-api:8008'])

    def setUp(self) -> None:
        context = create_context('secp256k1')
        self.signer = CryptoFactory(context).new_signer(
            context.new_random_private_key())

    def test_before_batch_injection(self):
        """Test that a 'intkey' transaction is injected before each intkey
        transaction with the Name 'inject' and confirming that there will be
        the same number of injected batches as intkey batches
        """
        intkey_batch1 = create_batch(self.signer, [('set', 'abcd', 0)])
        intkey_batch2 = create_batch(self.signer, [('inc', 'abcd', 10)])
        intkey_batch3 = create_batch(self.signer, [('inc', 'abcd', 20)])
        batches = create_batch_list(
            [intkey_batch1, intkey_batch2, intkey_batch3])

        post_batch(batches)

        # Assert injected batches are before each intkey transaction
        # get last committed block (first from the list)
        last_block = get_blocks()[0]

        family_name = get_family_from(last_block['batches'][0])
        self.assertEqual(family_name, 'intkey')
        payload = decode(get_payload_from(last_block['batches'][0]))
        self.assertEqual(payload.get('Name'), 'inject')
        family_name = get_family_from(last_block['batches'][1])
        self.assertEqual(family_name, 'intkey')
        payload = decode(get_payload_from(last_block['batches'][1]))
        self.assertEqual(payload.get('Name'), 'abcd')

        family_name = get_family_from(last_block['batches'][2])
        self.assertEqual(family_name, 'intkey')
        payload = decode(get_payload_from(last_block['batches'][2]))
        self.assertEqual(payload.get('Name'), 'inject')
        family_name = get_family_from(last_block['batches'][3])
        self.assertEqual(family_name, 'intkey')
        payload = decode(get_payload_from(last_block['batches'][3]))
        self.assertEqual(payload.get('Name'), 'abcd')

        family_name = get_family_from(last_block['batches'][4])
        self.assertEqual(family_name, 'intkey')
        payload = decode(get_payload_from(last_block['batches'][4]))
        self.assertEqual(payload.get('Name'), 'inject')
        family_name = get_family_from(last_block['batches'][5])
        self.assertEqual(family_name, 'intkey')
        payload = decode(get_payload_from(last_block['batches'][5]))
        self.assertEqual(payload.get('Name'), 'abcd')

    def test_after_batch_injection(self):
        """Test that a 'intkey' transaction is injected after each intkey
        transaction with the Name 'inject' and confirming that there will be
        the same number of injected batches as intkey batches
        """
        intkey_batch1 = create_batch(self.signer, [('inc', 'abcd', 30)])
        intkey_batch2 = create_batch(self.signer, [('inc', 'abcd', 40)])
        intkey_batch3 = create_batch(self.signer, [('inc', 'abcd', 50)])
        batches = create_batch_list(
            [intkey_batch1, intkey_batch2, intkey_batch3])

        post_batch(batches)

        # Assert injected batches are after each intkey transaction
        # get last committed block (first from the list)
        last_block = get_blocks()[0]

        family_name = get_family_from(last_block['batches'][0])
        self.assertEqual(family_name, 'intkey')
        payload = decode(get_payload_from(last_block['batches'][0]))
        self.assertEqual(payload.get('Name'), 'abcd')
        family_name = get_family_from(last_block['batches'][1])
        self.assertEqual(family_name, 'intkey')
        payload = decode(get_payload_from(last_block['batches'][1]))
        self.assertEqual(payload.get('Name'), 'inject')

        family_name = get_family_from(last_block['batches'][2])
        self.assertEqual(family_name, 'intkey')
        payload = decode(get_payload_from(last_block['batches'][2]))
        self.assertEqual(payload.get('Name'), 'abcd')
        family_name = get_family_from(last_block['batches'][3])
        self.assertEqual(family_name, 'intkey')
        payload = decode(get_payload_from(last_block['batches'][3]))
        self.assertEqual(payload.get('Name'), 'inject')

        family_name = get_family_from(last_block['batches'][4])
        self.assertEqual(family_name, 'intkey')
        payload = decode(get_payload_from(last_block['batches'][4]))
        self.assertEqual(payload.get('Name'), 'abcd')
        family_name = get_family_from(last_block['batches'][5])
        self.assertEqual(family_name, 'intkey')
        payload = decode(get_payload_from(last_block['batches'][5]))
        self.assertEqual(payload.get('Name'), 'inject')

    def test_block_end_injection(self):
        """Test that a 'block_info' transaction is injected at the end of
        the block and confirming that all other batches only contains
        intkey transactions
        """
        intkey_batch1 = create_batch(self.signer, [('inc', 'abcd', 60)])
        intkey_batch2 = create_batch(self.signer, [('inc', 'abcd', 70)])
        intkey_batch3 = create_batch(self.signer, [('inc', 'abcd', 80)])
        batches = create_batch_list(
            [intkey_batch1, intkey_batch2, intkey_batch3])

        post_batch(batches)

        # Assert injected batch is at the end of the block
        # get last committed block (first from the list)
        last_block = get_blocks()[0]

        family_name = get_family_from(last_block['batches'][0])
        self.assertEqual(family_name, 'intkey')
        family_name = get_family_from(last_block['batches'][1])
        self.assertEqual(family_name, 'intkey')
        family_name = get_family_from(last_block['batches'][2])
        self.assertEqual(family_name, 'intkey')
        family_name = get_family_from(last_block['batches'][3])
        self.assertEqual(family_name, 'block_info')
