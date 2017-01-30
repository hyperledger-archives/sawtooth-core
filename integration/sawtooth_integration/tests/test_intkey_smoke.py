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
import subprocess
import time
import logging
import operator

import urllib.request, urllib.error
import json
import cbor
import shlex
from base64 import b64decode

import tempfile
import bitcoin
import hashlib
import sawtooth_protobuf.batch_pb2 as batch_pb2
import sawtooth_protobuf.transaction_pb2 as transaction_pb2


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class TestIntkeySmoke(unittest.TestCase):
    def test_intkey_smoke(self):
        '''
        After starting up a validator, intkey processor, and rest api, 
        generate three batches of transactions: a batch of 'set' transactions 
        (the "populate" batch), a batch of valid 'inc'/'dec' transactions,
        and a batch of invalid of invalid 'inc'/'dec' transactions (invalid
        because they target words not set by the populate batch).

        First, verify that the state is initially empty. Next, load the
        batches in the following order, verifying that the state is
        as it should be after each load:

        1. Send the batch of 'set' transactions, populating the state.
        2. Send the batch of valid transactions, altering the state.
        3. Send the batch of invalid transactions, leaving the state the same.
        4. Send the batch of valid transactions, again altering the state.
        5. Send the same batch of 'set' transactions from before.
           Because the state has already been populated, these transactions
           are invalid, and shouldn't affect the state.
        6. Send the batch of valid transactions, again altering the state.
        '''

        # batch file names (strings)
        populate, valid_txns, invalid_txns = _make_txn_files()

        self.assert_empty_state()

        cmds = (
            populate,
            valid_txns,
            # invalid_txns,
            valid_txns,
            # populate,
            valid_txns
        )

        how_many_updates = 0

        for cmd in cmds:
            self.intkey_load(cmd)
            if cmd == valid_txns:
                how_many_updates += 1
            self.assert_state_after_n_updates(how_many_updates)

    # assertions

    def assert_state_after_n_updates(self, n):
        expected_state = self._state_after_n_updates(n)
        actual_state = self._get_data()

        self.assertEqual(
            expected_state,
            actual_state)

    def assert_empty_state(self):
        state = self._get_state()
        self.assertEqual('404', state)

    # expected state

    def _state_after_n_updates(self, n):
        ops = {
            'inc': operator.add,
            'dec': operator.sub
        }

        expected_values = [
            ops[verb](init, (val * n))
            for verb, init, val 
            in zip(_verbs(), _initial_values(), _inc_dec_values())
        ]

        return {word: val for word, val in zip(_valid_words(), expected_values)}

    # utilities

    def _display(self, msg):
        LOGGER.info(msg)

    def intkey_load(self, file):
        self._display('loading {}'.format(file))
        load_cmd = shlex.split('intkey load -f {} -U validator:40000'.format(file))
        subprocess.run(load_cmd,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE,
                       check=True)
        time.sleep(1)

    def _get_data(self):
        state = self._get_state()
        # state is a list of dictionaries: { data: ..., address: ... }
        dicts = [cbor.loads(b64decode(entry['data'])) for entry in state]
        data = {k:v for d in dicts for k,v in d.items()} # merge dicts
        return data

    def _get_state(self):
        root = self._get_root()
        try:
            response = self._query_rest_api('/{}'.format(root))
        except urllib.error.HTTPError:
            return '404'
        state = json.loads(response)['entries']
        return state

    def _get_root(self):
        response = self._query_rest_api()
        data = json.loads(response)
        root = data['merkleRoot']
        return root

    def _query_rest_api(self, suffix=''):
        url = 'http://rest_api:8080/state' + suffix
        request = urllib.request.Request(url)
        response = urllib.request.urlopen(request).read().decode('utf-8')
        return response


# transaction constants

def _valid_words():
    return 'cow', 'pig', 'sheep', 'goat', 'horse'

def _invalid_words():
    return 'lark', 'thrush', 'jay', 'wren', 'finch'

def _initial_values():
    return 415, 325, 538, 437, 651

def _inc_dec_values():
    return 1, 2, 3, 5, 8

def _verbs():
    return 'inc', 'inc', 'dec', 'inc', 'dec'

# intkey batch creation

def _make_txn_files():
    # file names
    prefix = '/tmp/intkey_smoke_test_'
    populate = prefix + 'populate'
    valid_txns = prefix + 'valid'
    invalid_txns = prefix + 'invalid'

    valid_words = _valid_words()
    invalid_words = _invalid_words()
    initial_values = _initial_values()
    verbs = _verbs()
    inc_dec_values = _inc_dec_values()

    _make_populate_file(
        valid_words,
        initial_values,
        populate)

    _make_inc_dec_file(
        verbs,
        valid_words,
        inc_dec_values,
        valid_txns)

    _make_inc_dec_file(
        verbs,
        invalid_words,
        inc_dec_values,
        invalid_txns)

    # return file names
    return populate, valid_txns, invalid_txns


def _make_batch_file(batch_list, file_name):
    with open(file_name, 'w+b') as file:
        LOGGER.debug('writing to {}'.format(file_name))
        file.write(batch_list.SerializeToString())


def _make_populate_file(words, values, file_name):
    private_key, public_key = _make_key_pair()

    txns = [
        _create_intkey_transaction(
            verb='set',
            name=word,
            value=val,
            private_key=private_key,
            public_key=public_key)
        for word, val in zip(words, values)
    ]

    batch = _create_batch(
        transactions=txns,
        private_key=private_key,
        public_key=public_key)

    batch_list = batch_pb2.BatchList(batches=[batch])

    _make_batch_file(batch_list, file_name)


def _make_inc_dec_file(verbs, words, values, file_name):
    private_key, public_key = _make_key_pair()

    txns = [
        _create_intkey_transaction(
            verb=verb,
            name=word,
            value=value,
            private_key=private_key,
            public_key=public_key)
        for verb, word, value in zip(verbs, words, values)
    ]

    batch = _create_batch(
        transactions=txns,
        private_key=private_key,
        public_key=public_key)

    batch_list = batch_pb2.BatchList(batches=[batch])

    _make_batch_file(batch_list, file_name)


def _make_key_pair():
    private_key = bitcoin.random_key()
    public_key = bitcoin.encode_pubkey(
        bitcoin.privkey_to_pubkey(private_key), "hex")
    return private_key, public_key


def _create_batch(transactions, private_key, public_key):
    transaction_signatures = [t.header_signature for t in transactions]

    header = batch_pb2.BatchHeader(
        signer_pubkey=public_key,
        transaction_ids=transaction_signatures)

    header_bytes = header.SerializeToString()

    signature = bitcoin.ecdsa_sign(
        header_bytes,
        private_key)

    batch = batch_pb2.Batch(
        header=header_bytes,
        transactions=transactions,
        header_signature=signature)

    return batch


def _create_intkey_transaction(verb, name, value, private_key, public_key):
    payload = _IntKeyPayload(
        verb=verb, name=name, value=value)

    # The prefix should eventually be looked up from the
    # validator's namespace registry.
    intkey_prefix = hashlib.sha512('intkey'.encode('utf-8')).hexdigest()[0:6]

    addr = intkey_prefix + hashlib.sha512(name.encode('utf-8')).hexdigest()

    header = transaction_pb2.TransactionHeader(
        signer_pubkey=public_key,
        family_name='intkey',
        family_version='1.0',
        inputs=[addr],
        outputs=[addr],
        dependencies=[],
        payload_encoding='application/cbor',
        payload_sha512=payload.sha512(),
        batcher_pubkey=public_key)

    header_bytes = header.SerializeToString()

    signature = bitcoin.ecdsa_sign(
        header_bytes,
        private_key)

    transaction = transaction_pb2.Transaction(
        header=header_bytes,
        payload=payload.to_cbor(),
        header_signature=signature)

    return transaction


class _IntKeyPayload(object):
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
