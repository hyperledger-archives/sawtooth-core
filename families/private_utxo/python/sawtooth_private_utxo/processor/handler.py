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

from sawtooth_sdk.processor.state import StateEntry
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_private_utxo.common.addressing import Addressing

from sawtooth_private_utxo.protobuf.asset_type_pb2 import AssetType
from sawtooth_private_utxo.protobuf.holding_pb2 import HoldingContainer
from sawtooth_private_utxo.protobuf.payload_pb2 import PrivateUtxoPayload
from sawtooth_private_utxo.protobuf.utxo_document_pb2 import UtxoDocument


LOGGER = logging.getLogger(__name__)

PRIVATE_UTXO_VERSION = '1.0'
PRIVATE_UTXO_FAMILY_NAME = 'sawtooth_private_utxo'


class PrivateUtxoHandler(object):
    def __init__(self):
        pass

    @property
    def family_name(self):
        return PRIVATE_UTXO_FAMILY_NAME

    @property
    def family_versions(self):
        return [PRIVATE_UTXO_VERSION]

    @property
    def encodings(self):
        return ['application/protobuf']

    @property
    def namespaces(self):
        return [Addressing.asset_type_namespace(),
                Addressing.holdings_namespace(),
                Addressing.utxo_namespace()]

    def apply(self, transaction, state):
        try:
            txn_header = TransactionHeader()
            txn_header.ParseFromString(transaction.header)
            originator = txn_header.signer_pubkey
            payload = PrivateUtxoPayload()
            payload.ParseFromString(transaction.payload)

            LOGGER.debug("PrivateUtxoHandler.apply action: %s %s",
                         PrivateUtxoPayload.Action.Name(payload.action),
                         payload)

            if payload.action == PrivateUtxoPayload.ISSUE_ASSET:
                self._issue_asset(state, originator, payload.issue_asset)
            elif payload.action == PrivateUtxoPayload.TRANSFER_ASSET:
                self._transfer_assert(
                    state, originator, payload.transfer_asset)
            elif payload.action == PrivateUtxoPayload.CONVERT_TO_UTXO:
                self._convert_to_utxo(
                    state, originator, payload.convert_to_utxo)
            elif payload.action == PrivateUtxoPayload.CONVERT_FROM_UTXO:
                self._convert_from_utxo(
                    state, originator, payload.convert_from_utxo)
            elif payload.action == PrivateUtxoPayload.TRANSFER_UTXO:
                self._utxo_transfer(state, originator, payload.transfer_utxo)
            else:
                raise InvalidTransaction('Unknown Action')
        except Exception:
            LOGGER.exception("Unexpected error applying transaction")
            raise

    def _issue_asset(self, state, originator, txn_data):
        LOGGER.debug("txn_data: %s", txn_data)

        name = txn_data.name
        amount = txn_data.amount
        nonce = txn_data.nonce
        asset_type_addr = Addressing.asset_type_address(
            originator, name, nonce)
        holdings_addr = Addressing.holdings_address(originator)

        state_values = self._get(state, [holdings_addr, asset_type_addr])
        asset_type = state_values.get(asset_type_addr, None)
        holdings = state_values.get(holdings_addr,
                                    HoldingContainer())
        holding = self._find_holding(holdings, originator, asset_type_addr)

        if asset_type is None:
            asset_type = AssetType(name=name,
                                   issuer=originator,
                                   nonce=nonce,
                                   amount=amount)
        else:
            if asset_type.issuer != originator or\
                    asset_type.name != name or\
                    asset_type.nonce != nonce:
                asset_type.amount += amount
            else:
                raise InvalidTransaction("AssetType collision.")

        holding.amount += amount

        # send back the updated agents list
        self._set(state,
                  [(asset_type_addr, asset_type),
                   (holdings_addr, holdings)])

    def _transfer_assert(self, state, originator, txn_data):
        LOGGER.debug("txn_data: %s", txn_data)
        recipient = txn_data.recipient
        asset_type_addr = txn_data.asset_type
        amount = txn_data.amount

        originator_addr = Addressing.holdings_address(originator)
        recipient_addr = Addressing.holdings_address(recipient)

        state_items = self._get(
            state, [originator_addr, recipient_addr, asset_type_addr])

        asset_type = state_items.get(asset_type_addr, None)
        if asset_type is None:
            raise InvalidTransaction("Invalid asset type.")

        orginator_holdings = state_items.get(
            originator_addr, HoldingContainer())
        recipient_holdings = state_items.get(
            recipient_addr, HoldingContainer())

        orginator_holding = self._find_holding(orginator_holdings,
                                               originator,
                                               asset_type_addr)

        recipient_holding = self._find_holding(recipient_holdings,
                                               recipient,
                                               asset_type_addr)
        if orginator_holding.amount < amount:
            raise InvalidTransaction("Insufficient amount.")

        orginator_holding.amount -= amount
        recipient_holding.amount += amount

        # send back the updated agents list
        self._set(state,
                  [(originator_addr, orginator_holdings),
                   (recipient_addr, recipient_holdings)])

    def _convert_to_utxo(self, state, originator, txn_data):
        LOGGER.debug("txn_data: %s", txn_data)

        asset_type = txn_data.asset_type
        amount = txn_data.amount
        nonce = txn_data.nonce
        output_utxo = txn_data.output_utxo

        # Calculate the addresses of the state values we need.
        originator_addr = Addressing.holdings_address(originator)

        # fetch the state values
        state_items = self._get(state, [originator_addr, output_utxo,
                                        asset_type])

        orginator_holdings = state_items.get(
            originator_addr, HoldingContainer())
        orginator_holding = self._find_holding(orginator_holdings,
                                               originator,
                                               asset_type)

        if orginator_holding.amount < amount:
            raise InvalidTransaction("Insufficient amount.")

        utxo_doc = UtxoDocument(
            owner=originator,
            asset_type=asset_type,
            amount=amount,
            nonce=nonce)
        utxo_addr = Addressing.utxo_address(utxo_doc.SerializeToString())

        if output_utxo != utxo_addr:
            raise InvalidTransaction("Output UTXO Mismatch. {} != {}"
                                     .format(output_utxo, utxo_addr))

        orginator_holding.amount -= amount

        # Update state
        self._set(state, [(originator_addr, orginator_holdings),
                          (output_utxo, output_utxo)])

    def _convert_from_utxo(self, state, originator, txn_data):
        LOGGER.debug("txn_data: %s", txn_data)

        utxo_doc = txn_data.document

        # Calculate the addresses of the state values we need.
        originator_addr = Addressing.holdings_address(originator)
        utxo = Addressing.utxo_address(utxo_doc.SerializeToString())

        # fetch the state values
        state_items = self._get(state, [utxo_doc.asset_type, utxo,
                                        originator_addr])

        originator_holdings = state_items.get(
            originator_addr, HoldingContainer())

        originator_holding = self._find_holding(originator_holdings,
                                                originator,
                                                utxo_doc.asset_type)

        if state_items.get(utxo, None) is None:
            raise InvalidTransaction("UTXO does not exist.")

        originator_holding.amount += utxo_doc.amount

        # Update state
        self._set(state, [(originator_addr, originator_holdings)])
        state.delete([utxo])

    def _utxo_transfer(self, state, originator, txn_data):
        LOGGER.debug("txn_data: %s", txn_data)
        # fetch the state values
        state_items = self._get(
            state, list(txn_data.inputs) + list(txn_data.outputs))

        for input_utxo in txn_data.inputs:
            if state_items.get(input_utxo, None) is None:
                raise InvalidTransaction(
                    "Input UTXO does not exist: {}".format(input_utxo))

        for output_utxo in txn_data.outputs:
            if state_items.get(output_utxo, None) is not None:
                raise InvalidTransaction(
                    "Output UTXO exists: {}".format(output_utxo))

        # Update state
        self._set(state, [(u, u) for u in txn_data.outputs])
        state.delete(txn_data.inputs)

    @staticmethod
    def _find_asset_holding(holding, asset_type):
        if holding is not None:
            for asset_holding in holding.asset_holdings:
                if asset_holding.asset_type == asset_type:
                    return asset_holding

            asset_holding = holding.asset_holdings.add()
            asset_holding.asset_type = asset_type
            asset_holding.amount = 0
            return asset_holding
        return None

    @staticmethod
    def _find_holding(holdings, identifier, asset_type):
        if holdings is not None:
            for holding in holdings.entries:
                if holding.identifier == identifier:
                    return PrivateUtxoHandler._find_asset_holding(
                        holding, asset_type)
            holding = holdings.entries.add()
            holding.identifier = identifier
            return PrivateUtxoHandler._find_asset_holding(
                holding, asset_type)
        return None

    @staticmethod
    def _get(state, addresses):
        entries = state.get(addresses)
        if entries:
            out = {}
            for e in entries:
                addr = e.address
                if e.data:
                    if addr.startswith(Addressing.asset_type_namespace()):
                        container = AssetType()
                        container.ParseFromString(e.data)
                    elif addr.startswith(Addressing.holdings_namespace()):
                        container = HoldingContainer()
                        container.ParseFromString(e.data)
                    elif addr.startswith(Addressing.utxo_namespace()):
                        container = e.data
                    else:
                        raise InvalidTransaction("Unknown namespaces.")
                else:
                    container = None

                out[addr] = container
            return out
        return {}

    @staticmethod
    def _set(state, items):
        entries = []
        for (addr, container) in items:
            if addr.startswith(Addressing.utxo_namespace()):
                entries.append(StateEntry(address=addr,
                                          data=container.encode()))
            else:
                entries.append(StateEntry(address=addr,
                                          data=container.SerializeToString()))
        LOGGER.debug("_set: %s", entries)
        result_addresses = state.set(entries)
        if result_addresses:
            for (addr, _) in items:
                if addr not in result_addresses:
                    raise InternalError("Error setting state, " +
                                        "address %s not set.", addr)
        else:
            raise InternalError("Error setting state nothing updated?")
