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


class IntkeyMessageFactory:

    def __init__(self, private=None, public=None):
        self._factory = MessageFactory(
            encoding="application/cbor",
            family_name="intkey",
            family_version="1.0",
            namespace="",
            private=private,
            public=public
        )
        self._factory.namespace = self._factory.sha512(
            "intkey".encode("utf-8"))[0:6]

    def _dumps(self, obj):
        return cbor.dumps(obj, sort_keys=True)

    def _loads(self, data):
        return cbor.loads(data)

    def _key_to_address(self, key):
        return self._factory.namespace + \
            self._factory.sha512(key.encode("utf-8"))

    def create_tp_register(self):
        return self._factory.create_tp_register()

    def create_tp_response(self, status):
        return self._factory.create_tp_response(status)

    def create_transaction(self, verb, name, value):
        payload = self._dumps({"Verb": verb, "Name": name, "Value": value})

        addresses = [self._key_to_address(name)]

        return self._factory.create_transaction(
            payload, addresses, addresses, []
        )

    def create_get_request(self, name):
        addresses = [self._key_to_address(name)]
        return self._factory.create_get_request(addresses)

    def create_get_response(self, name, value):
        address = self._key_to_address(name)

        if value is not None:
            data = self._dumps({name: value})
        else:
            data = None

        return self._factory.create_get_response({address: data})

    def create_set_request(self, name, value):
        address = self._key_to_address(name)

        if value is not None:
            data = self._dumps({name: value})
        else:
            data = None

        return self._factory.create_set_request({address: data})

    def create_set_response(self, name):
        addresses = [self._key_to_address(name)]
        return self._factory.create_set_response(addresses)
