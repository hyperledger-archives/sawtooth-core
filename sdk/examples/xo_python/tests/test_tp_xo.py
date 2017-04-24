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

from sawtooth_processor_test.transaction_processor_test_case \
    import TransactionProcessorTestCase
from sawtooth_xo.xo_message_factory import XoMessageFactory


class TestXo(TransactionProcessorTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = XoMessageFactory()

    def test_create_game(self):
        self.validator_sends_tp_process_request(
            action='create',
            game='game000')

        get_message = self.validator_expects_get_request('game000')

        self.validator_responds_to_get_request(
            get_message,
            game='game000', board=None,
            state=None, player1=None, player2=None)

        set_message = self.validator_expects_set_request(
            game='game000', board='---------',
            state='P1-NEXT', player1='', player2='')

        self.validator_responds_to_set_request(set_message, 'game000')

        self.validator_expects_tp_response('OK')

    def test_take_space(self):
        player1 = self.factory.get_public_key()

        self.validator_sends_tp_process_request(
            action='take',
            game='game000',
            space=3)

        get_message = self.validator_expects_get_request('game000')

        self.validator_responds_to_get_request(
            get_message,
            game='game000', board='---------',
            state='P1-NEXT', player1='', player2='')

        set_message = self.validator_expects_set_request(
            game='game000', board='--X------',
            state='P2-NEXT', player1=player1, player2='')

        self.validator_responds_to_set_request(set_message, 'game000')

        self.validator_expects_tp_response('OK')

    # helper functions

    def validator_sends_tp_process_request(self, *args, **kwargs):
        self.validator.send(
            self.factory.create_tp_process_request(*args, **kwargs))

    def validator_expects_get_request(self, key):
        return self.validator.expect(
            self.factory.create_get_request(key))

    def validator_responds_to_get_request(self, message, *args, **kwargs):
        self.validator.respond(
            self.factory.create_get_response(*args, **kwargs),
            message)

    def validator_expects_set_request(self, *args, **kwargs):
        return self.validator.expect(
            self.factory.create_set_request(*args, **kwargs))

    def validator_responds_to_set_request(self, message, *args, **kwargs):
        self.validator.respond(
            self.factory.create_set_response(*args, **kwargs),
            message)

    def validator_expects_tp_response(self, status):
        return self.validator.expect(
            self.factory.create_tp_response(status))
