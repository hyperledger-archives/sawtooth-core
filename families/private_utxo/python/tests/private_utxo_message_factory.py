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

from collections import OrderedDict
import logging

from google.protobuf.message import Message

from sawtooth_processor_test.message_factory import MessageFactory

from sawtooth_private_utxo.processor.handler import PRIVATE_UTXO_VERSION
from sawtooth_private_utxo.processor.handler import PRIVATE_UTXO_FAMILY_NAME

from sawtooth_private_utxo.common.addressing import Addressing

from sawtooth_private_utxo.protobuf.payload_pb2 import PrivateUtxoPayload

from sawtooth_private_utxo.protobuf.asset_type_pb2 import AssetType

from sawtooth_private_utxo.protobuf.holding_pb2 import HoldingContainer
from sawtooth_private_utxo.protobuf.holding_pb2 import Holdings

from sawtooth_private_utxo.protobuf.utxo_document_pb2 import UtxoDocument

LOGGER = logging.getLogger(__name__)


class PrivateUtxoMessageFactory(object):
    def __init__(self, private=None, public=None):
        self._factory = MessageFactory(
            encoding='application/protobuf',
            family_name=PRIVATE_UTXO_FAMILY_NAME,
            family_version=PRIVATE_UTXO_VERSION,
            namespace=[Addressing.asset_type_namespace(),
                       Addressing.holding_namespace(),
                       Addressing.utxo_namespace()],
            private=private,
            public=public
        )

    @property
    def public_key(self):
        return self._factory.get_public_key()

    def _dumps(self, obj):
        if obj is not None:
            if isinstance(obj, Message):
                return obj.SerializeToString()
            elif isinstance(obj, str):
                return obj.encode()
        return obj

    def create_tp_register(self):
        return self._factory.create_tp_register()

    def create_tp_response(self, status):
        return self._factory.create_tp_response(status)

    def _create_txn(self, txn_function, txn, inputs=None, outputs=None):
        payload = self._dumps(txn)
        return txn_function(payload, inputs, outputs, [])

    def create_tp_process_request(
            self, action, issue_asset=None, transfer_asset=None,
            convert_to_utxo=None, convert_from_utxo=None, transfer_utxo=None,
            inputs=None, outputs=None):
        payload = PrivateUtxoPayload(
            action=action,
            issue_asset=issue_asset,
            transfer_asset=transfer_asset,
            convert_to_utxo=convert_to_utxo,
            convert_from_utxo=convert_from_utxo,
            transfer_utxo=transfer_utxo)
        LOGGER.info("create_tp_process_request %s", payload)
        txn_function = self._factory.create_tp_process_request
        return self._create_txn(txn_function, payload, inputs, outputs)

    def create_delete_request(self, addresses):
        return self._factory.create_delete_request(addresses)

    def create_delete_response(self, addresses):
        return self._factory.create_delete_response(addresses)

    def create_get_request(self, addresses):
        return self._factory.create_get_request(addresses)

    def create_get_response(self, items):
        response = OrderedDict()
        for (addr, value) in items:
            data = None
            if value is not None:
                data = self._dumps(self._containerize(value))
            response[addr] = data
        return self._factory.create_get_response(response)

    def create_set_request(self, items):
        response = OrderedDict()
        for (addr, value) in items:
            data = None
            if value is not None:
                data = self._dumps(self._containerize(value))
            response[addr] = data
        return self._factory.create_set_request(response)

    def create_set_response(self, addresses):
        return self._factory.create_set_response(addresses)

    @staticmethod
    def _containerize(value):
        if isinstance(value, Holdings):
            return HoldingContainer(entries=[value])
        return value

    def issue_asset_tp_process_request(self, name, amount, nonce):
        originator = self.public_key
        originator_addr = Addressing.holding_address(originator)

        asset_type_addr =\
            Addressing.asset_type_address(originator, name, nonce)
        inputs = [originator_addr, asset_type_addr]
        outputs = [originator_addr, asset_type_addr]

        return self.create_tp_process_request(
            PrivateUtxoPayload.ISSUE_ASSET,
            issue_asset=PrivateUtxoPayload.IssueAssetPayload(
                name=name, amount=amount, nonce=nonce),
            inputs=inputs, outputs=outputs)

    def transfer_asset_tp_process_request(self, recipient, asset_type, amount):
        originator = self.public_key
        originator_addr = Addressing.holding_address(originator)
        recipient_addr = Addressing.holding_address(recipient)
        inputs = [asset_type, originator_addr, recipient_addr]
        outputs = [originator_addr, recipient_addr]

        return self.create_tp_process_request(
            PrivateUtxoPayload.TRANSFER_ASSET,
            transfer_asset=PrivateUtxoPayload.TransferAssetPayload(
                recipient=recipient, asset_type=asset_type, amount=amount),
            inputs=inputs, outputs=outputs)

    def convert_to_utxo_tp_process_request(self, asset_type,
                                           amount, nonce, output_utxo):
        originator = self.public_key
        originator_addr = Addressing.holding_address(originator)

        inputs = [originator_addr, output_utxo]
        outputs = [originator_addr, output_utxo]

        return self.create_tp_process_request(
            PrivateUtxoPayload.CONVERT_TO_UTXO,
            convert_to_utxo=PrivateUtxoPayload.ConvertToUtxoPayload(
                asset_type=asset_type,
                amount=amount,
                nonce=nonce,
                output_utxo=output_utxo),
            inputs=inputs, outputs=outputs)

    def convert_from_utxo_tp_process_request(self, document):
        originator = self.public_key
        originator_addr = Addressing.holding_address(originator)

        utxo = Addressing.utxo_address(document.SerializeToString())

        inputs = [originator_addr, utxo]
        outputs = [originator_addr, utxo]

        LOGGER.info(
            "utxo_doc: '%s' '%s' '%s' '%s'",
            document.owner,
            document.asset_type,
            document.amount,
            document.nonce
            )

        return self.create_tp_process_request(
            PrivateUtxoPayload.CONVERT_FROM_UTXO,
            convert_from_utxo=PrivateUtxoPayload.ConvertFromUtxoPayload(
                document=document),
            inputs=inputs, outputs=outputs)

    def transfer_utxo_tp_process_request(self, input_utxos,
                                         output_utxos,
                                         attestation):
        inputs = input_utxos + output_utxos
        outputs = inputs
        return self.create_tp_process_request(
            PrivateUtxoPayload.TRANSFER_UTXO,
            transfer_utxo=PrivateUtxoPayload.TransferUtxoPayload(
                inputs=input_utxos,
                outputs=output_utxos,
                attestation=attestation),
            inputs=inputs, outputs=outputs)

    def create_asset_type(self, identifier, name="", amount=0, nonce=0):
        out = AssetType(issuer=identifier, name=name,
                        amount=amount, nonce=nonce)
        return out

    def create_asset_holding(self, holdings, asset_type="", amount=0):
        asset_holdings = holdings.asset_holdings.add()
        asset_holdings.asset_type = asset_type
        asset_holdings.amount = amount

    def create_holding(self, identifier, asset_type="", amount=0):
        holdings = Holdings(identifier=identifier)
        self.create_asset_holding(holdings, asset_type, amount)
        return HoldingContainer(entries=[holdings])

    def create_utxo_document(self, owner, asset_type, amount=0, nonce=0):
        out = UtxoDocument(owner=owner, asset_type=asset_type,
                           amount=amount, nonce=nonce)
        return out
