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

import json

from sawtooth_processor_test.message_factory import MessageFactory
from sawtooth_supplychain.processor.handler import SUPPLYCHAIN_NAMESPACE


class SupplychainMessageFactory(object):
    def __init__(self, private=None, public=None):
        self._factory = MessageFactory(
            encoding='application/json',
            family_name='sawtooth_supplychain',
            family_version='1.0',
            namespace=SUPPLYCHAIN_NAMESPACE,
            private=private,
            public=public
        )

    @property
    def public_key(self):
        return self._factory.get_public_key()

    def _dumps(self, obj):
        return json.dumps(obj, sort_keys=True).encode()

    def _loads(self, data):
        return json.loads(data)

    def create_tp_register(self):
        return self._factory.create_tp_register()

    def create_tp_response(self, status):
        return self._factory.create_tp_response(status)

    def _create_txn(self, txn_function, txn, inputs=None, outputs=None):
        payload = self._dumps(txn)
        return txn_function(payload, inputs, outputs, [])

    def create_batch(self, triples):
        txns = [self.create_transaction(verb, name, value)
                for verb, name, value in triples]

        return self._factory.create_batch(txns)

    def create_tp_process_request(self, txn_data, inputs=None, outputs=None):
        txn_function = self._factory.create_tp_process_request
        return self._create_txn(txn_function, txn_data)

    def create_get_request(self, address):
        return self._factory.create_get_request([address])

    def create_get_response(self, address, value):
        if value is not None:
            data = self._dumps(value)
        else:
            data = None

        return self._factory.create_get_response({address: data})

    def create_set_request(self, address, value):
        if value is not None:
            data = self._dumps(value)
        else:
            data = None

        return self._factory.create_set_request({address: data})

    def create_set_response(self, address):
        return self._factory.create_set_response([address])
