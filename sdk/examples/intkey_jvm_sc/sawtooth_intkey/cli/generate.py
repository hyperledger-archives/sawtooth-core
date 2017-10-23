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

import hashlib
import os
import random
import sys
import time
import string
import argparse

import sawtooth_signing as signing
import sawtooth_sdk.protobuf.transaction_pb2 as transaction_pb2
import sawtooth_sdk.protobuf.batch_pb2 as batch_pb2
from sawtooth_sdk.protobuf import jvm_sc_pb2

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__)))), 'python'))


class JVM_SC_Payload(object):
    def __init__(self, verb, bytecode=None, methods=None, byte_addr=None,
                 method=None, parameters=None):
        self._payload = jvm_sc_pb2.JVMPayload(
            verb=verb, bytecode=bytecode, methods=methods, byte_addr=byte_addr,
            method=method, parameters=parameters)
        self.payload_bytes = self._payload.SerializeToString()
        self._sha512 = None

    def to_hash(self):
        return self.payload_bytes

    def sha512(self):
        # need to hash protobuff bytestring.
        if self._sha512 is None:
            self._sha512 = hashlib.sha512(self.to_hash()).hexdigest()
        return self._sha512


def create_jvm_sc_transaction(verb, private_key, public_key,
                              bytecode=None, methods=None, byte_addr=None,
                              method=None, parameters=None, addresses=None):

    payload = JVM_SC_Payload(verb=verb, bytecode=bytecode,
                             methods=methods, byte_addr=byte_addr,
                             method=method, parameters=parameters)

    if addresses is None:
        addresses = []

    # The prefix should eventually be looked up from the
    # validator's namespace registry.
    if byte_addr is not None:
        addr = byte_addr
    elif bytecode is not None:
        addr = get_address('jvm_sc', bytecode)
    else:
        raise Exception

    addresses.append(addr)
    header = transaction_pb2.TransactionHeader(
        signer_public_key=public_key,
        family_name='jvm_sc',
        family_version='1.0',
        inputs=addresses,
        outputs=addresses,
        dependencies=[],
        payload_sha512=payload.sha512(),
        batcher_public_key=public_key,
        nonce=str(time.time()))
    header_bytes = header.SerializeToString()

    signature = signing.sign(header_bytes, private_key)

    transaction = transaction_pb2.Transaction(
        header=header_bytes,
        payload=payload.payload_bytes,
        header_signature=signature)

    return transaction


def create_batch(transactions, private_key, public_key):
    transaction_signatures = [t.header_signature for t in transactions]

    header = batch_pb2.BatchHeader(
        signer_public_key=public_key,
        transaction_ids=transaction_signatures)

    header_bytes = header.SerializeToString()

    signature = signing.sign(header_bytes, private_key)

    batch = batch_pb2.Batch(
        header=header_bytes,
        transactions=transactions,
        header_signature=signature)

    return batch


def get_address(namespace, data):
    jvm_sc_prefix = hashlib.sha512(namespace.encode()).hexdigest()[0:6]
    try:
        addr = jvm_sc_prefix + hashlib.sha512(data).hexdigest()
    except TypeError:
        addr = jvm_sc_prefix + hashlib.sha512(data.encode()).hexdigest()
    return addr

def generate_word():
    return ''.join([random.choice(string.ascii_letters) for _ in range(0, 6)])

def generate_word_list(count):
    if os.path.isfile('/usr/share/dict/words'):
        with open('/usr/share/dict/words', 'r') as fd:
            return [x.strip() for x in fd.readlines()[0:count]]
    else:
        return [generate_word() for _ in range(0, count)]


def do_generate(args):
    private_key = signing.generate_privkey()
    public_key = signing.generate_public_key(private_key)

    words = generate_word_list(args.pool_size)

    txns = []
    batches = []
    bytecode = b''
    with open(args.contract, "rb") as fd:
        byte = fd.readline()
        while byte != b'':
            bytecode += byte
            byte = fd.readline()

    byte_addr = get_address("jvm_sc", bytecode)

    txn = create_jvm_sc_transaction(
        verb='store',
        private_key=private_key,
        public_key=public_key,
        bytecode=bytecode,
        methods=["set", "inc", "dec"])
    txns.append(txn)

    keys = []
    addresses = []
    for i in range(20):
        if len(txns) < 10:
            key = random.choice(words)
            keys.append(key)
            value = str(random.randint(500, 1000))
            key_addr = get_address("intkey", key)
            addresses.append(key_addr)
            txn = create_jvm_sc_transaction(
                verb='run',
                private_key=private_key,
                public_key=public_key,
                byte_addr=byte_addr,
                method="set",
                parameters=["key," + key, "value," + value,
                            "&check," + key_addr],
                addresses=addresses)
            txns.append(txn)
            addresses = []
        else:
            batch = create_batch(txns, private_key, public_key)
            batches.append(batch)
            txns = []

    for i in range(20):
        if len(txns) < 10:
            key = random.choice(keys)
            key_addr = get_address("intkey", key)
            addresses.append(key_addr)
            txn = create_jvm_sc_transaction(
                verb='run',
                private_key=private_key,
                public_key=public_key,
                byte_addr=byte_addr,
                method=random.choice(["inc", "dec"]),
                parameters=["key," + key, "&value," + key_addr, "diff,2"],
                addresses=addresses)
            txns.append(txn)
            addresses = []
        else:
            batch = create_batch(txns, private_key, public_key)
            batches.append(batch)
            txns = []

    batch_list = batch_pb2.BatchList(batches=batches)
    print("Writing to {}...".format(args.output))
    with open(args.output, "wb") as fd:
        fd.write(batch_list.SerializeToString())


def add_generate_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'generate',
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        '-o', '--output',
        type=str,
        help='location of output file',
        default='batches_jvm.intkey')

    parser.add_argument(
        '-c', '--contract',
        type=str,
        help='location of class file',
        default="sdk/examples/intkey_jvm_sc/sawtooth_intkey/Intkey.class")

    parser.add_argument(
        '-P', '--pool-size',
        type=int,
        help='size of the word pool',
        default=100)
