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
import time

import sawtooth_signing.secp256k1_signer as signing

from sawtooth_private_utxo.common.exceptions import PrivateUtxoException
from sawtooth_private_utxo.protobuf.utxo_document_pb2 import UtxoDocument


def generate_utxo_document(owner, asset_type, amount, nonce):
    return UtxoDocument(
        owner=owner, asset_type=asset_type, amount=amount, nonce=nonce)


def transfer_utxo(input_docs, recipients):

    asset_type = None
    total_amount = 0
    for doc in input_docs:
        encoded_doc = doc['encoded_document']
        signature = doc['signature']

        utxo_doc = UtxoDocument()
        utxo_doc.ParseFromString(encoded_doc)

        # verify all docs are of the same type
        if asset_type is None:
            asset_type = utxo_doc.asset_type
        elif utxo_doc.asset_type != asset_type:
            raise PrivateUtxoException("Documents don't match asset_type")

        # verify the owner is authorizing the document to be spent
        if not signing.verify(encoded_doc, signature, utxo_doc.owner):
            raise PrivateUtxoException("Input not validly signed to be spent.")

        total_amount += utxo_doc.amount

    output_docs = []
    output_amount = 0
    for recipient in recipients:
        addr = recipient[0]
        amount = recipient[1]

        output_amount += amount
        if output_amount > total_amount:
            raise PrivateUtxoException("Transfer outputs exceed inputs")

        utxo_doc = UtxoDocument(
            owner=addr,
            asset_type=asset_type,
            amount=amount,
            nonce=str(time.time()))
        output_docs.append(utxo_doc)

    return (output_docs, None)
