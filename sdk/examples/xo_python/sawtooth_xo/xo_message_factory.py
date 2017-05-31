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

import hashlib

from sawtooth_processor_test.message_factory import MessageFactory


# namespace
def _hash_name(name):
    return hashlib.sha512(name.encode('utf-8')).hexdigest()

FAMILY_NAME = 'xo'
XO_NAMESPACE = _hash_name(FAMILY_NAME)[:6]


def make_xo_address(name):
    return XO_NAMESPACE + _hash_name(name)[-64:]


# encodings
def encode_txn_payload(action, name, space):
    return ','.join([action, name, str(space)]).encode()


def encode_state_data(state_data_dict, name, board, state, player_1, player_2):
    state_data_dict[name] = [board, state, player_1, player_2]

    game_list = [
        [name] + data
        for name, data in state_data_dict.items()
    ]

    return '|'.join(sorted([
        ','.join(game)
        for game in game_list
    ])).encode()


class XoMessageFactory:
    def __init__(self, private=None, public=None):
        self._factory = MessageFactory(
            encoding='csv-utf8',
            family_name=FAMILY_NAME,
            family_version='1.0',
            namespace=XO_NAMESPACE,
            private=private,
            public=public)

        self.public_key = self._factory.get_public_key()

    # transactions

    def _create_txn(self, txn_function, action, name, space=None):
        payload = encode_txn_payload(action, name, space)

        addresses = [make_xo_address(name)]

        return txn_function(payload, addresses, addresses, [])

    def create_tp_process_request(self, action, name, space=None):
        txn_function = self._factory.create_tp_process_request
        return self._create_txn(txn_function, action, name, space)

    def create_transaction(self, game, action, space=None):
        txn_function = self._factory.create_transaction
        return self._create_txn(txn_function, action, game, space)

    # state messages
    def _create_state_message(self, msg_function,
                              name, board='---------',
                              state='P1-NEXT', player_1='', player_2=''):
        address = make_xo_address(name)

        data = None if board is None else encode_state_data(
            {}, name, board, state, player_1, player_2)

        return msg_function({address: data})

    def create_get_response(self, name, board='---------',
                            state='P1-NEXT', player_1='', player_2=''):

        msg_function = self._factory.create_get_response

        return self._create_state_message(
            msg_function, name, board, state, player_1, player_2)

    def create_set_request(self, name, board='---------',
                           state='P1-NEXT', player_1='', player_2=''):

        msg_function = self._factory.create_get_response

        return self._create_state_message(
            msg_function, name, board, state, player_1, player_2)

    def create_get_request(self, name):
        addresses = [make_xo_address(name)]
        return self._factory.create_get_request(addresses)

    def create_set_response(self, name):
        addresses = [make_xo_address(name)]
        return self._factory.create_set_response(addresses)

    # registering

    def create_tp_register(self):
        return self._factory.create_tp_register()

    def create_tp_response(self, status):
        return self._factory.create_tp_response(status)
