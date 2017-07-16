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

import logging

from sawtooth_sdk.protobuf.validator_pb2 import Message

from sawtooth_processor_test.transaction_processor_test_case \
    import TransactionProcessorTestCase

from private_utxo_message_factory import PrivateUtxoMessageFactory
from sawtooth_private_utxo.common.addressing import Addressing

LOGGER = logging.getLogger(__name__)


class TestPrivateUtxo(TransactionProcessorTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestPrivateUtxo, cls).setUpClass()
        cls.validator.register_comparator(
            Message.TP_STATE_SET_REQUEST,
            compare_set_request)
        cls.factory = PrivateUtxoMessageFactory()

    def test_issue_asset(self):
        """
        Test if the private utxo processor can issue assets.
        """
        try:
            validator = self.validator
            factory = self.factory

            originator = factory.public_key
            holdings_addr = Addressing.holding_address(originator)

            amount = 1
            asset_name = "asset"
            asset_nonce = "nonce"

            asset_type_addr =\
                Addressing.asset_type_address(originator, asset_name,
                                              asset_nonce)

            # 1. -> Send a set transaction
            #    <- Expect a state get request
            validator.send(factory.issue_asset_tp_process_request(
                asset_name, amount, asset_nonce))

            # Expect test for asset_type and holdings existance
            received = self.expect_get([holdings_addr, asset_type_addr])
            self.respond_get(received, [(holdings_addr, None),
                                        (asset_type_addr, None)])

            # Expect create agent
            asset_type = factory.create_asset_type(originator, asset_name,
                                                   amount, asset_nonce)
            holdings = factory.create_holding(
                originator, asset_type_addr, amount)
            LOGGER.info("test_issue_asset %s", holdings)
            received = self.expect_set([(asset_type_addr, asset_type),
                                        (holdings_addr, holdings)])
            self.respond_set(received, [holdings_addr, asset_type_addr])

            self.expect_ok()
        except Exception:
            LOGGER.exception("test_issue_asset exception")
            raise

    def test_convert_to_utxo(self):
        """
        Test if the private utxo processor can convert to utxo.
        """
        try:
            validator = self.validator
            factory = self.factory

            originator = factory.public_key
            originator_addr = Addressing.holding_address(originator)

            amount = 1
            asset_name = "asset"
            asset_nonce = "nonce"
            asset_type_addr =\
                Addressing.asset_type_address(originator, asset_name,
                                              asset_nonce)

            utxo_nonce = "nonce"
            utxo_doc = factory.create_utxo_document(
                originator, asset_type_addr, amount, utxo_nonce)
            utxo = Addressing.utxo_address(utxo_doc.SerializeToString())

            # 1. -> Send a set transaction
            #    <- Expect a state get request
            validator.send(factory.convert_to_utxo_tp_process_request(
                asset_type_addr, amount, utxo_nonce, utxo))

            # Expect read of holdings and utxo
            holdings = factory.create_holding(
                originator, asset_type_addr, amount)
            received = self.expect_get(
                [originator_addr, utxo, asset_type_addr])
            self.respond_get(received, [(originator_addr, holdings),
                                        (utxo, None)])

            # Expect holdings update
            holdings = factory.create_holding(originator, asset_type_addr, 0)
            received = self.expect_set([(originator_addr, holdings),
                                        (utxo, utxo)])
            self.respond_set(received, [utxo, originator_addr])

            self.expect_ok()
        except Exception:
            LOGGER.exception("test_convert_to_utxo exception")
            raise

    def test_convert_from_utxo(self):
        """
        Test if the private utxo processor can convert from utxo.
        """
        try:
            validator = self.validator
            factory = self.factory

            originator = factory.public_key
            originator_addr = Addressing.holding_address(originator)

            amount = 1
            asset_name = "asset"
            asset_nonce = "nonce"
            asset_type_addr =\
                Addressing.asset_type_address(originator, asset_name,
                                              asset_nonce)

            utxo_nonce = "nonce"
            utxo_doc = factory.create_utxo_document(
                originator, asset_type_addr, amount, utxo_nonce)
            LOGGER.info(
                "utxo_doc: '%s' '%s' '%s' '%s'",
                utxo_doc.owner,
                utxo_doc.asset_type,
                utxo_doc.amount,
                utxo_doc.nonce)
            utxo = Addressing.utxo_address(utxo_doc.SerializeToString())

            # 1. -> Send a set transaction
            #    <- Expect a state get request
            validator.send(factory.convert_from_utxo_tp_process_request(
                utxo_doc))

            # Expect test for asset_type and holdings existance
            asset_type = factory.create_asset_type(originator, asset_name,
                                                   amount, asset_nonce)
            holdings = factory.create_holding(
                originator, asset_type_addr, 0)
            received = self.expect_get(
                [asset_type_addr, utxo, originator_addr])
            self.respond_get(received, [(asset_type_addr, asset_type),
                                        (originator_addr, holdings),
                                        (utxo, "True")])

            # Expect create agent
            holdings = factory.create_holding(
                originator, asset_type_addr, amount)
            received = self.expect_set([(originator_addr, holdings)])
            self.respond_set(received, [originator_addr])

            received = self.expect_delete([utxo])
            self.respond_delete(received, [utxo])

            self.expect_ok()
        except Exception:
            LOGGER.exception("test_convert_from_utxo exception")
            raise

    def test_utxo_transfer(self):
        """
        Test if the private utxo processor can transfer utxo.
        """
        try:
            validator = self.validator
            factory = self.factory

            attestation = ""
            inputs = [Addressing.utxo_address(addr)
                      for addr in ["a", "b", "c"]]
            outputs = [Addressing.utxo_address(addr)
                       for addr in ["d", "e", "f"]]

            # 1. -> Send a set transaction
            #    <- Expect a state get request
            validator.send(factory.transfer_utxo_tp_process_request(
                inputs, outputs, attestation))

            # Expect test for utxo existance
            received = self.expect_get(inputs + outputs)
            self.respond_get(
                received,
                [(u, u) for u in inputs] + [(u, None) for u in outputs])

            received = self.expect_set([(u, u) for u in outputs])
            self.respond_set(received, outputs)

            received = self.expect_delete(inputs)
            self.respond_delete(received, inputs)

            self.expect_ok()
        except Exception:
            LOGGER.exception("test_utxo_transfer exception")
            raise

    def expect_delete(self, addrs):
        return self.validator.expect(
            self.factory.create_delete_request(addrs))

    def respond_delete(self, received, values):
        self.validator.respond(
            self.factory.create_delete_response(values),
            received)

    def expect_get(self, addrs):
        return self.validator.expect(
            self.factory.create_get_request(addrs))

    def respond_get(self, received, values):
        self.validator.respond(
            self.factory.create_get_response(values),
            received)

    def expect_set(self, values):
        return self.validator.expect(
            self.factory.create_set_request(values))

    def respond_set(self, received, addrs):
        return self.validator.respond(
            self.factory.create_set_response(addrs), received)

    def expect_ok(self):
        self.expect_tp_response('OK')

    def expect_invalid(self):
        self.expect_tp_response('INVALID_TRANSACTION')

    def expect_tp_response(self, response):
        self.validator.expect(
            self.factory.create_tp_response(response))


def compare_set_request(req1, req2):
    if len(req1.entries) != len(req2.entries):
        return False

    entries1 = [(e.address, e.data) for e in req1.entries]
    entries2 = [(e.address, e.data) for e in req2.entries]

    return entries1 == entries2
