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

import cbor

from sawtooth_processor_test.message_factory import MessageFactory
from sawtooth_intkey.processor.handler import INTKEY_ADDRESS_PREFIX
from sawtooth_intkey.processor.handler import make_intkey_address


class IntkeyMessageFactory:
    def __init__(self, signer=None):
        self._factory = MessageFactory(
            family_name='intkey',
            family_version='1.0',
            namespace=INTKEY_ADDRESS_PREFIX,
            signer=signer)

    def _dumps(self, obj):
        return cbor.dumps(obj, sort_keys=True)

    def _loads(self, data):
        return cbor.loads(data)

    def create_tp_register(self):
        return self._factory.create_tp_register()

    def create_tp_response(self, status):
        return self._factory.create_tp_response(status)

    def _create_txn(self, txn_function, verb, name, value):
        payload = self._dumps({'Verb': verb, 'Name': name, 'Value': value})

        addresses = [make_intkey_address(name)]

        return txn_function(payload, addresses, addresses, [])

    def create_tp_process_request(self, verb, name, value,):
        txn_function = self._factory.create_tp_process_request
        return self._create_txn(txn_function, verb, name, value)

    def create_transaction(self, verb, name, value,):
        txn_function = self._factory.create_transaction
        return self._create_txn(txn_function, verb, name, value)

    def create_batch(self, triples):
        txns = [
            self.create_transaction(verb, name, value)
            for verb, name, value in triples
        ]

        return self._factory.create_batch(txns)

    def create_get_request(self, name):
        addresses = [make_intkey_address(name)]
        return self._factory.create_get_request(addresses)

    def create_get_response(self, name, value):
        address = make_intkey_address(name)

        if value is not None:
            data = self._dumps({name: value})
        else:
            data = None

        return self._factory.create_get_response({address: data})

    def create_set_request(self, name, value):
        address = make_intkey_address(name)

        if value is not None:
            data = self._dumps({name: value})
        else:
            data = None

        return self._factory.create_set_request({address: data})

    def create_set_response(self, name):
        addresses = [make_intkey_address(name)]
        return self._factory.create_set_response(addresses)
