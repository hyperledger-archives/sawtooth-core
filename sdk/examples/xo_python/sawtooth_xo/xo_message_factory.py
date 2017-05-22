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


class XoMessageFactory:
    def __init__(self, private=None, public=None):
        self._factory = MessageFactory(
            encoding="csv-utf8",
            family_name=FAMILY_NAME,
            family_version="1.0",
            namespace=XO_NAMESPACE,
            private=private,
            public=public)

        self.public_key = self._factory.get_public_key()

    def create_tp_register(self):
        return self._factory.create_tp_register()

    def create_tp_response(self, status):
        return self._factory.create_tp_response(status)

    def _create_txn(self, txn_function, action, game, space=None):
        payload = encode_txn_payload(action, game, space)

        addresses = [make_xo_address(game)]

        return txn_function(payload, addresses, addresses, [])

    def create_tp_process_request(self, action, game, space=None):
        txn_function = self._factory.create_tp_process_request
        return self._create_txn(txn_function, action, game, space)

    def create_transaction(self, game, action, space=None):
        txn_function = self._factory.create_transaction
        return self._create_txn(txn_function, action, game, space)

    def create_get_request(self, game):
        addresses = [make_xo_address(game)]
        return self._factory.create_get_request(addresses)

    def create_get_response(
        self, game, board="---------", state="P1-NEXT", player1="", player2=""
    ):
        address = make_xo_address(game)

        data = None
        if board is not None:
            data = ",".join([board, state, player1, player2, game]).encode()
        else:
            data = None

        return self._factory.create_get_response({address: data})

    def create_set_request(
        self, game, board="---------", state="P1-NEXT", player1="", player2=""
    ):
        address = make_xo_address(game)

        data = None
        if state is not None:
            data = ",".join([board, state, player1, player2, game]).encode()
        else:
            data = None

        return self._factory.create_get_response({address: data})

    def create_set_response(self, game):
        addresses = [make_xo_address(game)]
        return self._factory.create_set_response(addresses)
