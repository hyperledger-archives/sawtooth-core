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

import base64
import hashlib
import json
import logging
import time
import requests

import sawtooth_signing.secp256k1_signer as signing

from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_sdk.protobuf.transaction_pb2 import Transaction
from sawtooth_sdk.protobuf.batch_pb2 import BatchList
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader
from sawtooth_sdk.protobuf.batch_pb2 import Batch

from sawtooth_private_utxo.common.addressing import Addressing
from sawtooth_private_utxo.common.exceptions import PrivateUtxoException

from sawtooth_private_utxo.protobuf.asset_type_pb2 import AssetType
from sawtooth_private_utxo.protobuf.holding_pb2 import HoldingContainer
from sawtooth_private_utxo.protobuf.payload_pb2 import PrivateUtxoPayload


LOGGER = logging.getLogger(__name__)


def _sha512(data):
    return hashlib.sha512(data).hexdigest()


def _b64_dec(data):
    return base64.b64decode(data)


def _pb_dumps(obj):
    return obj.SerializeToString()


def _pb_loads(obj, encoded):
    obj.ParseFromString(encoded)
    return obj


def _decode_asset_type(encoded):
    return _pb_loads(AssetType(), encoded)


def _decode_holding_container(encoded):
    return _pb_loads(HoldingContainer(), encoded)


class PrivateUtxoClient(object):
    def __init__(self, base_url, keyfile):
        self._base_url = base_url
        try:
            with open(keyfile) as fd:
                self._private_key = fd.read().strip()
        except:
            raise IOError("Failed to read keys.")

        self._public_key = signing.generate_pubkey(self._private_key)

    @property
    def public_key(self):
        return self._public_key

    @property
    def private_key(self):
        return self._private_key

    def issue_asset(self, name, amount, nonce, wait):
        inputs = [
            Addressing.asset_type_address(self._public_key, name, nonce),
            Addressing.holdings_address(self._public_key)]
        outputs = inputs
        return self._send_txn(
            PrivateUtxoPayload.ISSUE_ASSET,
            issue_asset=PrivateUtxoPayload.IssueAssetPayload(
                name=name, amount=amount, nonce=nonce),
            inputs=inputs, outputs=outputs, wait=wait)

    def asset_type_list(self):
        result = self._send_get("state?address={}".format(
            Addressing.asset_type_namespace()))
        try:
            data = self._get_result_list(result)
            out = []
            for state_obj in data:
                container = _decode_asset_type(
                    _b64_dec(state_obj['data']))
                out.extend(container.entries)
            return out
        except BaseException:
            return None

    def asset_type_get(self, asset_type_addr):
        result = self._send_get("state/{}".format(asset_type_addr))
        try:
            data = self._get_result_data(result)
            asset_type = _decode_asset_type(data)
            return asset_type
        except BaseException:
            return None

    def get_asset_holdings(self, public_key, asset_type):
        holdings = self.get_holdings(public_key)
        if holdings is not None:
            for asset_holdings in holdings.asset_holdings:
                if asset_holdings.asset_type == asset_type:
                    return asset_holdings
        return None

    def get_holdings(self, public_key):
        addr = Addressing.holdings_address(public_key)
        result = self._send_get("state/{}".format(addr))
        try:
            data = self._get_result_data(result)
            holdings_container = _decode_holding_container(data)
            for holdings in holdings_container.entries:
                if holdings.identifier == public_key:
                    return holdings
            return None
        except BaseException:
            return None

    def transfer_asset(self, recipient, asset_type, amount, wait):
        inputs = [Addressing.holdings_address(self.public_key),
                  Addressing.holdings_address(recipient),
                  asset_type]
        outputs = [Addressing.holdings_address(self.public_key),
                   Addressing.holdings_address(recipient)]
        return self._send_txn(
            PrivateUtxoPayload.TRANSFER_ASSET,
            transfer_asset=PrivateUtxoPayload.TransferAssetPayload(
                asset_type=asset_type,
                amount=amount,
                recipient=recipient),
            inputs=inputs, outputs=outputs, wait=wait)

    def convert_to_utxo(self, asset_type, amount,
                        nonce, output_utxo, wait):
        inputs = [Addressing.holdings_address(self.public_key),
                  output_utxo, asset_type]
        outputs = [Addressing.holdings_address(self.public_key),
                   output_utxo]
        return self._send_txn(
            PrivateUtxoPayload.CONVERT_TO_UTXO,
            convert_to_utxo=PrivateUtxoPayload.ConvertToUtxoPayload(
                asset_type=asset_type,
                amount=amount, nonce=nonce,
                output_utxo=output_utxo),
            inputs=inputs, outputs=outputs, wait=wait)

    def convert_from_utxo(self, document, wait):
        encoded_document = document.SerializeToString()

        inputs = [Addressing.holdings_address(self.public_key),
                  document.asset_type,
                  Addressing.utxo_address(encoded_document)]
        outputs = [Addressing.holdings_address(self.public_key),
                   Addressing.utxo_address(encoded_document)]
        return self._send_txn(
            PrivateUtxoPayload.CONVERT_FROM_UTXO,
            convert_from_utxo=PrivateUtxoPayload.ConvertFromUtxoPayload(
                document=document),
            inputs=inputs, outputs=outputs, wait=wait)

    def transfer_utxo(self, input_utxos, output_utxos, attestation, wait):
        inputs = input_utxos + output_utxos
        outputs = inputs
        return self._send_txn(
            PrivateUtxoPayload.TRANSFER_UTXO,
            transfer_utxo=PrivateUtxoPayload.TransferUtxoPayload(
                inputs=input_utxos,
                outputs=output_utxos,
                attestation=attestation),
            inputs=inputs, outputs=outputs, wait=wait)

    @staticmethod
    def _get_result_data(result_json):
        result = json.loads(result_json)
        return _b64_dec(result['data'])

    @staticmethod
    def _get_result_list(result_json):
        result = json.loads(result_json)
        return result['data']

    def _send_post(self, suffix, data, content_type=None, wait=None):
        wait_param = '?wait={}'.format(wait) if wait and wait > 0 else ''
        url = "http://{}/{}{}".format(self._base_url, suffix, wait_param)
        LOGGER.info(url)
        headers = None
        if content_type is not None:
            headers = {'Content-Type': content_type}

        try:
            result = requests.post(url, headers=headers, data=data)
            if not result.ok:
                raise PrivateUtxoException("Error {}: {}".format(
                    result.status_code, result.reason))

        except BaseException as err:
            raise PrivateUtxoException(err)

        return result.text

    def _send_get(self, suffix):
        url = "http://{}/{}".format(self._base_url, suffix)
        LOGGER.info(url)
        try:
            result = requests.get(url)
            if not result.ok:
                raise PrivateUtxoException("Error {}: {}".format(
                    result.status_code, result.reason))

        except BaseException as err:
            raise PrivateUtxoException(err)

        return result.text

    def _send_txn(self, action, issue_asset=None, transfer_asset=None,
                  convert_to_utxo=None, convert_from_utxo=None,
                  transfer_utxo=None, inputs=None, outputs=None,
                  wait=None):

        payload = PrivateUtxoPayload(
            action=action,
            issue_asset=issue_asset,
            transfer_asset=transfer_asset,
            convert_to_utxo=convert_to_utxo,
            convert_from_utxo=convert_from_utxo,
            transfer_utxo=transfer_utxo)
        payload_str = _pb_dumps(payload)

        header = TransactionHeader(
            signer_pubkey=self._public_key,
            family_name="sawtooth_private_utxo",
            family_version="1.0",
            inputs=inputs or [],
            outputs=outputs or [],
            dependencies=[],
            payload_encoding='application/protobuf',
            payload_sha512=_sha512(payload_str),
            batcher_pubkey=self._public_key,
            nonce=time.time().hex().encode()
        )
        header_str = header.SerializeToString()

        signature = signing.sign(header_str, self._private_key)

        transaction = Transaction(
            header=header_str,
            payload=payload_str,
            header_signature=signature
        )
        LOGGER.info("header: %s payload: %s", header, payload)
        LOGGER.info("inputs: %s, outputs: %s", inputs, outputs)

        batch_list = self._create_batch_list([transaction])

        result = self._send_post(
            "batches", batch_list.SerializeToString(),
            'application/octet-stream',
            wait=wait)

        return result

    def _create_batch_list(self, transactions):
        transaction_signatures = [t.header_signature for t in transactions]

        header = BatchHeader(
            signer_pubkey=self._public_key,
            transaction_ids=transaction_signatures
        ).SerializeToString()

        signature = signing.sign(header, self._private_key)

        batch = Batch(
            header=header,
            transactions=transactions,
            header_signature=signature
        )
        return BatchList(batches=[batch])
