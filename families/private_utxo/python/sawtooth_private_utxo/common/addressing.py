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


PRIVATE_UTXO_ASSET_TYPE_NAMESPACE = \
    hashlib.sha512('private_utxo.asset_type'.encode()).hexdigest()[0:6]
PRIVATE_UTXO_HOLDINGS_NAMESPACE = \
    hashlib.sha512('private_utxo.holdings'.encode()).hexdigest()[0:6]
PRIVATE_UTXO_UTXO_NAMESPACE = \
    hashlib.sha512('private_utxo.utxo'.encode()).hexdigest()[0:6]


class Addressing(object):
    @classmethod
    def asset_type_namespace(cls):
        return PRIVATE_UTXO_ASSET_TYPE_NAMESPACE

    @classmethod
    def asset_type_address(cls, issuer, asset_name, asset_nonce):
        hasher = hashlib.sha512()
        hasher.update(issuer.encode())
        hasher.update(asset_name.encode())
        hasher.update(asset_nonce.encode())
        address = hasher.hexdigest()[0:64]
        return cls.asset_type_namespace() + address

    @classmethod
    def holdings_namespace(cls):
        return PRIVATE_UTXO_HOLDINGS_NAMESPACE

    @classmethod
    def holdings_address(cls, public_key):
        address = hashlib.sha512(public_key.encode()).hexdigest()[0:64]
        return cls.holdings_namespace() + address

    @classmethod
    def utxo_namespace(cls):
        return PRIVATE_UTXO_UTXO_NAMESPACE

    @classmethod
    def utxo_address(cls, document):
        if isinstance(document, bytes):
            encoded_document = document
        else:
            encoded_document = document.encode()
        address = hashlib.sha512(encoded_document).hexdigest()[0:64]
        return cls.utxo_namespace() + address
