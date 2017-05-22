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

import hashlib
import base64
import time
import requests
import yaml

import sawtooth_signing.secp256k1_signer as signing

from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_sdk.protobuf.transaction_pb2 import Transaction
from sawtooth_sdk.protobuf.batch_pb2 import BatchList
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader
from sawtooth_sdk.protobuf.batch_pb2 import Batch

from sawtooth_xo.xo_exceptions import XoException


# encodings
def encode_txn_payload(action, name, space):
    return ','.join([action, name, space]).encode()


def _sha512(data):
    return hashlib.sha512(data).hexdigest()


class XoClient:
    def __init__(self, base_url, keyfile):

        self._base_url = base_url

        try:
            with open(keyfile) as fd:
                self._private_key = fd.read().strip()
                fd.close()
        except:
            raise IOError("Failed to read keys.")

        self._public_key = signing.generate_pubkey(self._private_key)

    def create(self, name):
        return self._send_xo_txn("create", name)

    def take(self, name, space):
        return self._send_xo_txn("take", name, space)

    def list(self):
        xo_prefix = self._get_prefix()

        result = self._send_request("state?address={}".format(xo_prefix))

        try:
            encoded_entries = yaml.safe_load(result)["data"]

            return [
                base64.b64decode(entry["data"]) for entry in encoded_entries
            ]

        except BaseException:
            return None

    def show(self, name):
        address = self._get_address(name)

        result = self._send_request("state/{}".format(address))

        try:
            return base64.b64decode(yaml.safe_load(result)["data"])

        except BaseException:
            return None

    def _get_prefix(self):
        return _sha512('xo'.encode('utf-8'))[0:6]

    def _get_address(self, name):
        xo_prefix = self._get_prefix()
        game_address = _sha512(name.encode('utf-8'))
        return xo_prefix + game_address

    def _send_request(self, suffix, data=None, content_type=None):
        url = "http://{}/{}".format(self._base_url, suffix)

        headers = None
        if content_type is not None:
            headers = {'Content-Type': content_type}

        try:
            if data is not None:
                result = requests.post(url, headers=headers, data=data)
            else:
                result = requests.get(url)

            if not result.ok:
                raise XoException("Error {}: {}".format(
                    result.status_code, result.reason))

        except BaseException as err:
            raise XoException(err)

        return result.text

    def _send_xo_txn(self, action, name, space=""):

        # Serialization is just a delimited utf-8 encoded string
        payload = encode_txn_payload(action, name, str(space))

        # Construct the address
        address = self._get_address(name)

        header = TransactionHeader(
            signer_pubkey=self._public_key,
            family_name="xo",
            family_version="1.0",
            inputs=[address],
            outputs=[address],
            dependencies=[],
            payload_encoding="csv-utf8",
            payload_sha512=_sha512(payload),
            batcher_pubkey=self._public_key,
            nonce=time.time().hex().encode()
        ).SerializeToString()

        signature = signing.sign(header, self._private_key)

        transaction = Transaction(
            header=header,
            payload=payload,
            header_signature=signature
        )

        batch_list = self._create_batch_list([transaction])

        result = self._send_request(
            "batches", batch_list.SerializeToString(),
            'application/octet-stream'
        )

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
