#!/usr/bin/python
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

# pylint: disable=consider-using-enumerate

import argparse
import hashlib
import os
import logging
import random
import string

import cbor

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory

from sawtooth_sdk.protobuf import batch_pb2
from sawtooth_sdk.protobuf import transaction_pb2

from sawtooth_intkey.processor.handler import make_intkey_address


LOGGER = logging.getLogger(__name__)


class IntKeyPayload:
    def __init__(self, verb, name, value):
        self._verb = verb
        self._name = name
        self._value = value

        self._cbor = None
        self._sha512 = None

    def to_hash(self):
        return {
            'Verb': self._verb,
            'Name': self._name,
            'Value': self._value
        }

    def to_cbor(self):
        if self._cbor is None:
            self._cbor = cbor.dumps(self.to_hash(), sort_keys=True)
        return self._cbor

    def sha512(self):
        if self._sha512 is None:
            self._sha512 = hashlib.sha512(self.to_cbor()).hexdigest()
        return self._sha512


def create_intkey_transaction(verb, name, value, signer):
    payload = IntKeyPayload(
        verb=verb, name=name, value=value)

    # The prefix should eventually be looked up from the
    # validator's namespace registry.
    addr = make_intkey_address(name)

    header = transaction_pb2.TransactionHeader(
        signer_public_key=signer.get_public_key().as_hex(),
        family_name='intkey',
        family_version='1.0',
        inputs=[addr],
        outputs=[addr],
        dependencies=[],
        payload_sha512=payload.sha512(),
        batcher_public_key=signer.get_public_key().as_hex(),
        nonce=hex(random.randint(0, 2**64)))

    header_bytes = header.SerializeToString()

    signature = signer.sign(header_bytes)

    transaction = transaction_pb2.Transaction(
        header=header_bytes,
        payload=payload.to_cbor(),
        header_signature=signature)

    return transaction


def create_batch(transactions, signer):
    transaction_ids = [t.header_signature for t in transactions]

    header = batch_pb2.BatchHeader(
        signer_public_key=signer.get_public_key().as_hex(),
        transaction_ids=transaction_ids)

    header_bytes = header.SerializeToString()

    signature = signer.sign(header_bytes)

    batch = batch_pb2.Batch(
        header=header_bytes,
        transactions=transactions,
        header_signature=signature)

    return batch


def generate_word():
    return ''.join([random.choice(string.ascii_letters) for _ in range(0, 6)])


def generate_word_list(count):
    if os.path.isfile('/usr/share/dict/words'):
        with open('/usr/share/dict/words', 'r') as fd:
            return [x.strip() for x in fd.readlines()[0:count]]
    else:
        return [generate_word() for _ in range(0, count)]


def do_populate(args):
    context = create_context('secp256k1')
    signer = CryptoFactory(context).new_signer(
        context.new_random_private_key())

    words = generate_word_list(args.pool_size)

    batches = []
    total_txn_count = 0
    txns = []
    for i in range(0, len(words)):
        txn = create_intkey_transaction(
            verb='set',
            name=words[i],
            value=random.randint(9000, 100000),
            signer=signer)
        total_txn_count += 1
        txns.append(txn)

    batch = create_batch(
        transactions=txns,
        signer=signer)

    batches.append(batch)

    batch_list = batch_pb2.BatchList(batches=batches)

    print("Writing to {}...".format(args.output))
    with open(args.output, "wb") as fd:
        fd.write(batch_list.SerializeToString())


def add_populate_parser(subparsers, parent_parser):

    epilog = '''
    deprecated:
     use create_batch, which combines
     the populate and generate commands.
    '''

    parser = subparsers.add_parser(
        'populate',
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog)

    parser.add_argument(
        '-o', '--output',
        type=str,
        help='location of output file',
        default='batches.intkey')

    parser.add_argument(
        '-P', '--pool-size',
        type=int,
        help='size of the word pool',
        default=100)
