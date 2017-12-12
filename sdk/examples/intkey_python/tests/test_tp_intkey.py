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

import cbor

from sawtooth_processor_test.transaction_processor_test_case \
    import TransactionProcessorTestCase
from sawtooth_intkey.intkey_message_factory import IntkeyMessageFactory
from sawtooth_sdk.protobuf.validator_pb2 import Message


VALID_VERBS = 'set', 'inc', 'dec'

MIN_VALUE = 0
MAX_VALUE = 4294967295
MAX_NAME_LENGTH = 20


class TestIntkey(TransactionProcessorTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.validator.register_comparator(
            Message.TP_STATE_SET_REQUEST,
            compare_set_request)

        cls.factory = IntkeyMessageFactory()

    # inputs

    def test_bad_verb(self):
        self.send_transaction('what', 'huh', 5)

        self.expect_invalid()

    def test_int_verb(self):
        self.send_transaction(7, 'number_verb', 5)

        self.expect_invalid()

    def test_name_too_long(self):
        self.try_transaction_with_all_verbs(
            'x' * (MAX_NAME_LENGTH + 1),
            MAX_NAME_LENGTH)

    def test_string_value(self):
        self.try_transaction_with_all_verbs('name', 'value')

    def test_float_value(self):
        self.try_transaction_with_all_verbs('float', 4.2)

    def test_value_too_low(self):
        self.try_transaction_with_all_verbs('too_low', MIN_VALUE - 1)

    def test_value_too_high(self):
        self.try_transaction_with_all_verbs('too_high', MAX_VALUE + 1)

    # set

    def test_set_valid(self):
        self.send_transaction('set', 'match', 5)

        self.send_get_response('match', None)

        self.expect_set_request('match', 5)

    def test_set_already_set(self):
        self.send_transaction('set', 'already_set', 5)

        self.send_get_response('already_set', 6)

        self.expect_invalid()

    # inc

    def test_inc_valid(self):
        self.send_transaction('inc', 'ink', 2)

        self.send_get_response('ink', 12)

        self.expect_set_request('ink', 14)

    def test_inc_too_high(self):
        current = MAX_VALUE - 12

        self.send_transaction('inc', 'to_get_over', 13)

        self.send_get_response('to_get_over', current)

        self.expect_invalid()

    def test_inc_not_set(self):
        self.send_transaction('inc', 'missing', 4)

        self.send_get_response('missing', None)

        self.expect_invalid()

    # dec

    def test_dec_valid(self):
        self.send_transaction('dec', 'deck', 3)

        self.send_get_response('deck', 24)

        self.expect_set_request('deck', 21)

    def test_dec_too_low(self):
        current = MIN_VALUE + 7

        self.send_transaction('dec', 'to_get_under', 8)

        self.send_get_response('to_get_under', current)

        self.expect_invalid()

    def test_dec_not_set(self):
        self.send_transaction('dec', 'missing', 4)

        self.send_get_response('missing', None)

        self.expect_invalid()

    # permissible, but perhaps not desired

    def test_wacky_name(self):
        wacky_name = '¿¡Ⴜæ¢§¶¥!?'

        self.send_transaction('set', wacky_name, 8)

        self.send_get_response(wacky_name, None)

        self.expect_set_request(wacky_name, 8)

    # helpers (named from the perspective of the validator)

    def send_transaction(self, verb, name, value):
        self.validator.send(
            self.factory.create_tp_process_request(
                verb, name, value))

    def try_transaction_with_all_verbs(self, name, value):
        for verb in VALID_VERBS:
            self.send_transaction(verb, name, value)

            self.expect_invalid()

    def send_get_response(self, name, value):
        received = self.validator.expect(
            self.factory.create_get_request(
                name))

        self.validator.respond(
            self.factory.create_get_response(
                name, value),
            received)

    def expect_set_request(self, name, value):
        received = self.validator.expect(
            self.factory.create_set_request(
                name, value))

        self.validator.respond(
            self.factory.create_set_response(
                name),
            received)

        self.expect_ok()

    def expect_ok(self):
        self.expect_tp_response('OK')

    def expect_invalid(self):
        self.expect_tp_response('INVALID_TRANSACTION')

    def expect_tp_response(self, response):
        self.validator.expect(
            self.factory.create_tp_response(
                response))


def compare_set_request(req1, req2):
    if len(req1.entries) != len(req2.entries):
        return False

    entries1 = [(e.address, cbor.loads(e.data)) for e in req1.entries]
    entries2 = [(e.address, cbor.loads(e.data)) for e in req2.entries]

    return entries1 == entries2
