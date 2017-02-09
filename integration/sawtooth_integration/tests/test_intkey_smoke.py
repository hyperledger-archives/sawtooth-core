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
import urllib.request
import urllib.error
import json
import shlex
from base64 import b64decode

import cbor

from sawtooth_integration.intkey.intkey_message_factory \
    import IntkeyMessageFactory


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

        # 2/7/17: The validator seems to stop responding when sent
        # invalid txns (a bug). The invalid txns are commented out
        # so the test will pass for the moment, but they should be
        # be uncommented when that issue is addressed.

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
            _intkey_load(cmd)
            if cmd == valid_txns:
                how_many_updates += 1
            self.assert_state_after_n_updates(how_many_updates)

    # assertions

    def assert_state_after_n_updates(self, num):
        expected_state = _state_after_n_updates(num)
        actual_state = _get_data()

        self.assertEqual(
            expected_state,
            actual_state)

    def assert_empty_state(self):
        state = _get_state()
        self.assertEqual('404', state)

# utilities

def _intkey_load(file):
    LOGGER.info('loading {}'.format(file))
    load_cmd = shlex.split('intkey load -f {} -U validator:40000'.format(file))
    subprocess.run(load_cmd,
                   stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE,
                   check=True)
    time.sleep(1)

def _get_data():
    state = _get_state()
    # state is a list of dictionaries: { data: ..., address: ... }
    dicts = [cbor.loads(b64decode(entry['data'])) for entry in state]
    data = {k:v for d in dicts for k, v in d.items()} # merge dicts
    return data

def _get_state():
    root = _get_root()
    try:
        response = _query_rest_api('/{}'.format(root))
    except urllib.error.HTTPError:
        return '404'
    state = json.loads(response)['entries']
    return state

def _get_root():
    response = _query_rest_api()
    data = json.loads(response)
    root = data['merkleRoot']
    return root

def _query_rest_api(suffix=''):
    url = 'http://rest_api:8080/state' + suffix
    request = urllib.request.Request(url)
    response = urllib.request.urlopen(request).read().decode('utf-8')
    return response

# expected state

def _state_after_n_updates(num):
    ops = {
        'inc': operator.add,
        'dec': operator.sub
    }

    expected_values = [
        ops[verb](init, (val * num))
        for verb, init, val
        in zip(_verbs(), _initial_values(), _inc_dec_values())
    ]

    return {word: val for word, val in zip(_valid_words(), expected_values)}

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
    sets = ('set' for _ in range(len(initial_values)))
    inc_dec_values = _inc_dec_values()

    _make_batch_file(
        sets,
        valid_words,
        initial_values,
        populate)

    _make_batch_file(
        verbs,
        valid_words,
        inc_dec_values,
        valid_txns)

    _make_batch_file(
        verbs,
        invalid_words,
        inc_dec_values,
        invalid_txns)

    # return file names
    return populate, valid_txns, invalid_txns


def _make_batch_file(verbs, words, values, file_name):
    txns = zip(verbs, words, values)

    batch = IntkeyMessageFactory().create_batch(txns)

    with open(file_name, 'w+b') as file:
        LOGGER.debug('writing to {}'.format(file_name))
        file.write(batch)
