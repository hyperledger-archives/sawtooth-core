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

import logging
import json
from base64 import b64encode, b64decode
import hashlib
import time
import random
import yaml
import requests

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_signing import ParseError
from sawtooth_signing.secp256k1 import Secp256k1PrivateKey

from sawtooth_battleship.battleship_exceptions import BattleshipException
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_sdk.protobuf.transaction_pb2 import Transaction

from sawtooth_sdk.protobuf.batch_pb2 import BatchList
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader
from sawtooth_sdk.protobuf.batch_pb2 import Batch

# from sawtooth.client import SawtoothClient


LOGGER = logging.getLogger(__name__)


class BattleshipClient:

    def __init__(self, base_url, keyfile, wait=None):
        """
        Member variables:
            _base_url
            _private_key
            _public_key
            _transaction_family
            _family_version
            _wait
        """
        self._base_url = base_url

        try:
            with open(keyfile) as fd:
                private_key_str = fd.read().strip()
        except OSError as err:
            raise IOError("Failed to read keys: {}.".format(str(err)))

        try:
            private_key = Secp256k1PrivateKey.from_hex(private_key_str)
        except ParseError as e:
            raise BattleshipException(
                'Unable to load private key: {}'.format(str(e)))

        self._signer = CryptoFactory(
            create_context('secp256k1')).new_signer(private_key)

        self._transaction_family = "battleship"
        self._family_version = "1.0"
        self._wait = wait

    def _send_battleship_txn(self, update):
        """The client needs to have the same
            defaults as the Transaction subclass
            before it is signed inside sendtxn
        """
        if 'Name' not in update:
            raise BattleshipException('Game name required')
        if 'Action' not in update:
            update['Action'] = None
        if 'Ships' not in update:
            update['Ships'] = None
        if update['Action'] == 'JOIN':
            if 'Board' not in update:
                update['Board'] = None
        if update['Action'] == 'FIRE':
            if 'Column' not in update:
                update['Column'] = None
            if 'Row' not in update:
                update['Row'] = None

        payload = json.dumps(update).encode()
        address = self._get_address(update['Name'])

        header = TransactionHeader(
            signer_public_key=self._signer.get_public_key().as_hex(),
            family_name=self._transaction_family,
            family_version=self._family_version,
            inputs=[address],
            outputs=[address],
            dependencies=[],
            payload_sha512=self._sha512(payload),
            batcher_public_key=self.signer.get_public_key().as_hex(),
            nonce=hex(random.randint(0, 2**64))
        ).SerializeToString()

        signature = self._signer.sign(header)

        transaction = Transaction(
            header=header,
            payload=payload,
            header_signature=signature
        )

        batch_list = self._create_batch_list([transaction])
        batch_id = batch_list.batches[0].header_signature

        if self._wait and self._wait > 0:
            wait_time = 0
            start_time = time.time()
            response = self._send_request(
                "batches", batch_list.SerializeToString(),
                'application/octet-stream'
            )
            while wait_time < self._wait:
                status = self._get_status(
                    batch_id,
                    self._wait - int(wait_time)
                )
                wait_time = time.time() - start_time

                if status != 'PENDING':
                    return response

            return response

        return self._send_request(
            "batches", batch_list.SerializeToString(),
            'application/octet-stream')

    def create(self, name, ships):
        """ Create battleship game
        """
        update = {
            'Action': 'CREATE',
            'Name': name,
            'Ships': ships
        }

        return self._send_battleship_txn(update)

    def join(self, name, board):
        """ User joins battleship game
        """
        update = {
            'Action': 'JOIN',
            'Name': name,
            'Board': board
        }

        return self._send_battleship_txn(update)

    def fire(self, name, column, row, reveal_space, reveal_nonce):
        """ Fire at (column, row)
        """
        update = {
            'Action': 'FIRE',
            'Name': name,
            'Column': column,
            'Row': row
        }

        if reveal_space is not None:
            update['RevealSpace'] = reveal_space

        if reveal_nonce is not None:
            update['RevealNonce'] = reveal_nonce

        return self._send_battleship_txn(update)

    def list_games(self, auth_user=None, auth_password=None):
        prefix = self._get_prefix()

        result = self._send_request(
            "state?address={}".format(prefix),
            auth_user=auth_user,
            auth_password=auth_password
        )

        try:
            encoded_entries = yaml.safe_load(result)["data"]

            ret = {}
            for entry in encoded_entries:
                d = json.loads(b64decode(entry["data"]).decode())
                for k, v in d.items():
                    ret[k] = v

            return ret

        except BaseException:
            return None

    def _sha512(self, data):
        return hashlib.sha512(data).hexdigest()

    def _get_prefix(self):
        return self._sha512(self._transaction_family.encode('utf-8'))[0:6]

    def _get_address(self, name):
        prefix = self._get_prefix()
        game_address = self._sha512(name.encode('utf-8'))[0:64]
        return prefix + game_address

    def _create_batch_list(self, transactions):
        transaction_signatures = [t.header_signature for t in transactions]

        header = BatchHeader(
            signer_public_key=self._signer.get_public_key().as_hex(),
            transaction_ids=transaction_signatures
        ).SerializeToString()

        signature = self._signer.sign(header)

        batch = Batch(
            header=header,
            transactions=transactions,
            header_signature=signature
        )
        return BatchList(batches=[batch])

    def _get_status(self, batch_id, wait):
        try:
            result = self._send_request(
                'batch_statuses?id={}&wait={}'.format(batch_id, wait))
            return yaml.safe_load(result)['data'][0]['status']
        except BaseException as err:
            raise BattleshipException(err)

    def _send_request(
            self, suffix, data=None,
            content_type=None, name=None, auth_user=None, auth_password=None):
        if self._base_url.startswith("http://"):
            url = "{}/{}".format(self._base_url, suffix)
        else:
            url = "http://{}/{}".format(self._base_url, suffix)

        headers = {}
        if auth_user is not None:
            auth_string = "{}:{}".format(auth_user, auth_password)
            b64_string = b64encode(auth_string.encode()).decode()
            auth_header = 'Basic {}'.format(b64_string)
            headers['Authorization'] = auth_header

        if content_type is not None:
            headers['Content-Type'] = content_type

        try:
            if data is not None:
                result = requests.post(url, headers=headers, data=data)
            else:
                result = requests.get(url, headers=headers)

            if result.status_code == 404:
                raise BattleshipException("No such game: {}".format(name))

            elif not result.ok:
                raise BattleshipException("Error {}: {}".format(
                    result.status_code, result.reason))

        except BaseException as err:
            raise BattleshipException(err)

        return result.text
