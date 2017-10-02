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

import unittest

from rpc_client import RpcClient
from mock_validator import MockValidator

from sawtooth_sdk.protobuf.validator_pb2 import Message
from sawtooth_sdk.protobuf.client_pb2 import ClientBlockListRequest
from sawtooth_sdk.protobuf.client_pb2 import ClientBlockListResponse
from sawtooth_sdk.protobuf.client_pb2 import ClientBlockGetRequest
from sawtooth_sdk.protobuf.client_pb2 import ClientBlockGetResponse
from sawtooth_sdk.protobuf.client_pb2 import ClientStateGetRequest
from sawtooth_sdk.protobuf.client_pb2 import ClientStateGetResponse
from sawtooth_sdk.protobuf.client_pb2 import ClientTransactionGetRequest
from sawtooth_sdk.protobuf.client_pb2 import ClientTransactionGetResponse
from sawtooth_sdk.protobuf.block_pb2 import Block
from sawtooth_sdk.protobuf.block_pb2 import BlockHeader
from sawtooth_sdk.protobuf.batch_pb2 import Batch
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader
from sawtooth_sdk.protobuf.transaction_pb2 import Transaction
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_sdk.protobuf.txn_receipt_pb2 import ClientReceiptGetRequest
from sawtooth_sdk.protobuf.txn_receipt_pb2 import ClientReceiptGetResponse
from sawtooth_sdk.protobuf.txn_receipt_pb2 import TransactionReceipt
from protobuf.seth_pb2 import SethTransactionReceipt
from protobuf.seth_pb2 import EvmEntry
from protobuf.seth_pb2 import EvmStateAccount
from protobuf.seth_pb2 import EvmStorage
from protobuf.seth_pb2 import SethTransaction
from protobuf.seth_pb2 import CreateExternalAccountTxn
from protobuf.seth_pb2 import CreateContractAccountTxn
from protobuf.seth_pb2 import MessageCallTxn
from protobuf.seth_pb2 import SetPermissionsTxn


class SethRpcTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = MockValidator()
        cls.validator.listen("tcp://eth0:4004")
        cls.url = 'http://seth-rpc:3030/'
        cls.rpc = RpcClient(cls.url)
        cls.rpc.wait_for_service()
        # block values
        cls.block_id = "f" * 128
        cls.block_num = 123
        cls.prev_block_id = "e" * 128
        cls.state_root = "d" * 64
        cls.txn_id = "c" * 64
        cls.gas = 456
        # account values
        cls.account_address = "f" * 20 * 2
        cls.balance = 123
        cls.nonce = 456
        cls.code_b = bytes([0xab, 0xcd, 0xef])
        cls.code_s = "abcdef"
        cls.position_b = bytes([0x01, 0x23, 0x45])
        cls.position_s = "012345"
        cls.stored_b = bytes([0x67, 0x89])
        cls.stored_s = "6789"

    # Network tests
    def test_net_version(self):
        """Test that the network id 19 is returned."""
        self.assertEqual("19", self.rpc.call("net_version"))

    def test_net_peerCount(self):
        """Test that 0 is returned as hex."""
        self.assertEqual("0x0", self.rpc.call("net_peerCount"))

    def test_net_listening(self):
        """Test that the True is returned."""
        self.assertEqual(True, self.rpc.call("net_listening"))

    # Block tests
    def test_block_number(self):
        """Test that the block number is extracted correctly and returned as
        hex."""
        self.rpc.acall("eth_blockNumber")
        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BLOCK_LIST_REQUEST)
        self.validator.respond(
            Message.CLIENT_BLOCK_LIST_RESPONSE,
            ClientBlockListResponse(
                status=ClientBlockListResponse.OK,
                blocks=[Block(
                    header=BlockHeader(block_num=15).SerializeToString(),
                )]),
            msg)
        self.assertEqual("0xf", self.rpc.get_result())

    def test_get_block_transaction_count_by_hash(self):
        """Test that a block transaction count is retrieved correctly, given a
        block id."""
        self.rpc.acall(
            "eth_getBlockTransactionCountByHash", ["0x" + self.block_id])
        msg, request = self._receive_block_request()
        self.assertEqual(request.block_id, self.block_id)

        self._send_block_back(msg)

        result = self.rpc.get_result()
        self.assertEqual(result, "0x1")

    def test_get_block_transaction_count_by_hash_wrong_input(self):
        """Test that the correct error message is returned if no input is given
           to eth_getBlockTransactionCountByHash.
        """
        self.rpc.acall(
            "eth_getBlockTransactionCountByHash", )
        result = self.rpc.get_result()
        self.assertEqual(result["error"]["message"],
                         "Takes [blockHash: DATA(64)]")

    def test_get_block_transaction_count_by_hash_no_block(self):
        """Test that None is returned if no block is found for
           eth_getBlockTransactionCountByHash.
        """
        bad_id = "1" * 128
        self.rpc.acall(
            "eth_getBlockTransactionCountByHash", ["0x" + bad_id])
        msg, request = self._receive_block_request()
        self.assertEqual(request.block_id, bad_id)

        self._send_block_no_resource(msg)

        result = self.rpc.get_result()
        self.assertIsNone(result)

    def test_get_block_transaction_count_by_number(self):
        """Test that a block transaction count is retrieved correctly, given a
        block number."""
        self.rpc.acall(
            "eth_getBlockTransactionCountByNumber", [hex(self.block_num)])
        msg, request = self._receive_block_request()
        self.assertEqual(request.block_num, self.block_num)

        self._send_block_back(msg)

        result = self.rpc.get_result()
        self.assertEqual(result, "0x1")

    def test_get_block_transaction_count_by_number_bad_input(self):
        """Test that the correct error message is returned if no input is given
           to eth_getBlockTransactionCountByNumber.
        """
        self.rpc.acall(
            "eth_getBlockTransactionCountByNumber", )

        result = self.rpc.get_result()
        self.assertEqual(result["error"]["message"],
                         "Takes [blockNum: QUANTITY]")

    def test_get_block_transaction_count_by_number_no_block(self):
        """Test that None is returned if no block is found for
           eth_getBlockTransactionCountByNumber.
        """
        bad_num = 2
        self.rpc.acall(
            "eth_getBlockTransactionCountByNumber", [hex(bad_num)])
        msg, request = self._receive_block_request()
        self.assertEqual(request.block_num, bad_num)

        self._send_block_no_resource(msg)

        result = self.rpc.get_result()
        self.assertIsNone(result)

    def test_get_block_by_hash(self):
        """Test that a block is retrieved correctly, given a block hash."""
        self.rpc.acall("eth_getBlockByHash", ["0x" + self.block_id, False])
        msg, request = self._receive_block_request()
        self.assertEqual(request.block_id, self.block_id)

        self._send_block_back(msg)
        msg, request = self._receive_receipt_request()
        self.assertEqual(request.transaction_ids[0], self.txn_id)

        self._send_receipts_back(msg)
        result = self.rpc.get_result()
        self.assertEqual(result["number"], hex(self.block_num))
        self.assertEqual(result["hash"], "0x" + self.block_id)
        self.assertEqual(result["parentHash"], "0x" + self.prev_block_id)
        self.assertEqual(result["stateRoot"], "0x" + self.state_root)
        self.assertEqual(result["gasUsed"], hex(self.gas))
        self.assertEqual(result["transactions"][0], "0x" + self.txn_id)

    def test_get_block_by_hash_bad_input(self):
        """Test that the correct error message is returned if no input is given
           to eth_getBlockByHash.
        """
        self.rpc.acall("eth_getBlockByHash", )
        result = self.rpc.get_result()
        self.assertEqual(result["error"]["message"],
                         "Takes [blockHash: DATA(64), full: BOOL]")

    def test_get_block_by_bad_hash(self):
        """Test that None is returned if no block is found for
           eth_getBlockByHash.
        """
        bad_id = "1" * 128
        self.rpc.acall("eth_getBlockByHash", ["0x" + bad_id, False])
        msg, request = self._receive_block_request()
        self.assertEqual(request.block_id, bad_id)

        self._send_block_no_resource(msg)
        result = self.rpc.get_result()
        self.assertIsNone(result)

    def test_get_block_by_number(self):
        """Test that a block is retrieved correctly, given a block number."""
        self.rpc.acall("eth_getBlockByNumber", [hex(self.block_num), False])
        msg, request = self._receive_block_request()
        self.assertEqual(request.block_num, self.block_num)

        self._send_block_back(msg)
        msg, request = self._receive_receipt_request()
        self.assertEqual(request.transaction_ids[0], self.txn_id)

        self._send_receipts_back(msg)
        result = self.rpc.get_result()
        self.assertEqual(result["number"], hex(self.block_num))
        self.assertEqual(result["hash"], "0x" + self.block_id)
        self.assertEqual(result["parentHash"], "0x" + self.prev_block_id)
        self.assertEqual(result["stateRoot"], "0x" + self.state_root)
        self.assertEqual(result["gasUsed"], hex(self.gas))
        self.assertEqual(result["transactions"][0], "0x" + self.txn_id)

    def test_get_block_by_number_bad_input(self):
        """Test that the correct error message is returned if no input is given
           to eth_getBlockByNumber.
        """
        self.rpc.acall("eth_getBlockByNumber", )
        result = self.rpc.get_result()
        self.assertEqual(result["error"]["message"],
                         "Takes [blockNum: QUANTITY, full: BOOL]")

    def test_get_block_by_bad_number(self):
        """Test that None is returned if no block is found for
           eth_getBlockByNumber.
        """
        bad_num = 2
        self.rpc.acall("eth_getBlockByNumber", [hex(bad_num), False])
        msg, request = self._receive_block_request()
        self.assertEqual(request.block_num, bad_num)

        self._send_block_no_resource(msg)
        result = self.rpc.get_result()
        self.assertIsNone(result)

    # Account tests
    def test_get_balance(self):
        """Test that an account balance is retrieved correctly."""
        # self._test_get_account("balance")
        self.rpc.acall(
            "eth_getBalance", ["0x" + self.account_address, "latest"])

        msg, request = self._receive_state_request()
        self.assertEqual(request.address,
            "a68b06" + self.account_address + "0" * 24)

        self._send_state_response(msg)
        result = self.rpc.get_result()
        self.assertEqual(hex(self.balance), result)

    def test_get_balance_bad_input(self):
        """Test that the correct error message is returned if no input is given
           to eth_getBalance
        """
        self.rpc.acall("eth_getBalance",)
        result = self.rpc.get_result()
        self.assertEqual(result["error"]["message"],
                         "Takes [address: DATA(20), block: QUANTITY|TAG]")

    def test_get_balance_no_block(self):
        """Test that None is returned if no block is found for
           eth_getBalance.
        """
        bad_account_address = "a" * 20 * 2
        self.rpc.acall(
            "eth_getBalance", ["0x" + bad_account_address, "latest"])

        msg, request = self._receive_state_request()
        self.assertEqual(request.address,
            "a68b06" + bad_account_address + "0" * 24)

        self._send_state_no_resource(msg)
        result = self.rpc.get_result()
        self.assertIsNone(result)

    def test_get_code(self):
        """Test that an account's code is retrieved correctly."""
        # self._test_get_account("balance")
        self.rpc.acall(
            "eth_getCode", ["0x" + self.account_address, "latest"])

        msg, request = self._receive_state_request()
        self.assertEqual(request.address,
            "a68b06" + self.account_address + "0" * 24)

        self._send_state_response(msg)
        result = self.rpc.get_result()
        self.assertEqual("0x" + self.code_s, result)

    def test_get_code_bad_input(self):
        """Test that the correct error message is returned if no input is given
           to eth_getCode.
        """
        self.rpc.acall("eth_getCode", )
        result = self.rpc.get_result()
        self.assertEqual(result["error"]["message"],
                         "Takes [address: DATA(20), block: QUANTITY|TAG]")

    def test_get_code_no_block(self):
        """Test that None is returned if no block is found for
          eth_getCode.
        """
        bad_account_address = "a" * 20 * 2
        self.rpc.acall(
            "eth_getCode", ["0x" + bad_account_address, "latest"])
        msg, request = self._receive_state_request()
        self.assertEqual(request.address,
            "a68b06" + bad_account_address + "0" * 24)

        self._send_state_no_resource(msg)
        result = self.rpc.get_result()
        self.assertIsNone(result)

    def test_get_storage_at(self):
        """Test that an account's storage is retrieved correctly."""
        # self._test_get_account("balance")
        self.rpc.acall(
            "eth_getStorageAt",
            ["0x" + self.account_address, "0x" + self.position_s, "latest"])

        msg, request = self._receive_state_request()
        self.assertEqual(request.address,
            "a68b06" + self.account_address + "0" * 24)

        self._send_state_response(msg)
        result = self.rpc.get_result()
        self.assertEqual("0x" + self.stored_s, result)

    def test_get_storage_at_bad_input(self):
        """Test that the correct error message is returned if no input is given
           to eth_getStorageAt.
        """
        self.rpc.acall("eth_getStorageAt",)
        result = self.rpc.get_result()
        self.assertEqual(
            result["error"]["message"],
            "Takes [address: DATA(20), position: QUANTITY, block: "
            "QUANTITY|TAG]")

    def test_get_storage_at_no_address(self):
        """Test that None is returned if no address is found for
           eth_getStorageAt.
        """
        bad_account_address = "a" * 20 * 2
        self.rpc.acall(
            "eth_getStorageAt",
            ["0x" + bad_account_address, "0x" + self.position_s, "latest"])

        msg, request = self._receive_state_request()
        self.assertEqual(request.address,
            "a68b06" + bad_account_address + "0" * 24)

        self._send_state_no_resource(msg)
        result = self.rpc.get_result()
        self.assertIsNone(result)

    def test_get_account_by_block_num(self):
        """Tests that account info is retrieved correctly when a block number
        is used as the block key.

        This requires an extra exchange with the validator to translate the
        block number into a block id, since it isn't possible to look up state
        based on a block number.
        """
        account_address = "f" * 20 * 2
        balance = 123
        block_num = 321
        block_id = "f" * 128

        self.rpc.acall(
            "eth_getBalance", ["0x" + account_address, hex(block_num)])

        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BLOCK_GET_REQUEST)
        request = ClientBlockGetRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.block_num, block_num)

        self.validator.respond(
            Message.CLIENT_BLOCK_GET_RESPONSE,
            ClientBlockGetResponse(
                status=ClientBlockGetResponse.OK,
                block=Block(header_signature=block_id)
            ),
            msg)

        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_STATE_GET_REQUEST)
        request = ClientStateGetRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.head_id, block_id)
        self.assertEqual(request.address,
            "a68b06" + account_address + "0" * 24)

        self.validator.respond(
            Message.CLIENT_STATE_GET_RESPONSE,
            ClientStateGetResponse(
                status=ClientStateGetResponse.OK,
                value=EvmEntry(
                    account=EvmStateAccount(balance=balance),
                ).SerializeToString()),
            msg)

        result = self.rpc.get_result()
        self.assertEqual(hex(balance), result)

    def test_get_account_by_block_num_bad_input(self):
        """Test that the correct error message is returned if no input is given
           to eth_getBalance.
        """
        self.rpc.acall("eth_getBalance",)
        result = self.rpc.get_result()
        self.assertEqual(result["error"]["message"],
                         "Takes [address: DATA(20), block: QUANTITY|TAG]")

    def test_accounts(self):
        """Tests that account list is retrieved correctly."""
        address = "434d46456b6973a678b77382fca0252629f4389f"
        self.assertEqual(["0x" + address], self.rpc.call("eth_accounts"))

    # Transaction calls
    def test_get_transaction_by_hash(self):
        """Tests that a transaction is retrieved correctly given its hash."""
        block_id = "a" * 128
        block_num = 678
        txn_ids = [
            "0" * 64,
            "1" * 64,
            "2" * 64,
            "3" * 64,
        ]
        txn_idx = 2
        nonce = 4
        pub_key = "035e1de3048a62f9f478440a22fd7655b" + \
                  "80f0aac997be963b119ac54b3bfdea3b7"
        addr = "b4d09ca3c0bc538340e904b689016bbb4248136c"

        gas = 100
        to_b = bytes([0xab, 0xcd, 0xef])
        to_s = "abcdef"
        data_b = bytes([0x67, 0x89])
        data_s = "6789"

        self.rpc.acall(
            "eth_getTransactionByHash",
            ["0x" + txn_ids[txn_idx]])

        msg = self.validator.receive()
        self.assertEqual(
            msg.message_type, Message.CLIENT_TRANSACTION_GET_REQUEST)
        request = ClientTransactionGetRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.transaction_id, txn_ids[txn_idx])

        block = self._make_multi_txn_block(
            txn_ids, nonce, block_num, block_id, pub_key, gas, to_b,
            data_b)

        self.validator.respond(
            Message.CLIENT_TRANSACTION_GET_RESPONSE,
            ClientTransactionGetResponse(
                status=ClientBlockGetResponse.OK,
                transaction=block.batches[1].transactions[1],
                block=block_id),
            msg)

        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BLOCK_GET_REQUEST)
        request = ClientBlockGetRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.block_id, block_id)

        self.validator.respond(
            Message.CLIENT_BLOCK_GET_RESPONSE,
            ClientBlockGetResponse(
                status=ClientBlockGetResponse.OK,
                block=block),
            msg)

        result = self.rpc.get_result()
        self.assertEqual(result["hash"], "0x" + txn_ids[txn_idx])
        self.assertEqual(result["nonce"], hex(nonce))
        self.assertEqual(result["blockHash"], "0x" + block_id)
        self.assertEqual(result["blockNumber"], hex(block_num))
        self.assertEqual(result["transactionIndex"], hex(txn_idx))
        self.assertEqual(result["from"], "0x" + addr)
        self.assertEqual(result["to"], "0x" + to_s)
        self.assertEqual(result["value"], "0x0")
        self.assertEqual(result["gasPrice"], "0x0")
        self.assertEqual(result["gas"], hex(gas))
        self.assertEqual(result["input"], "0x" + data_s)

    def test_get_transaction_by_hash_bad_input(self):
        """Test that the correct error message is returned if no input is given
           to eth_getTransactionByHash.
        """
        self.rpc.acall("eth_getTransactionByHash",)
        result = self.rpc.get_result()
        self.assertEqual(result["error"]["message"],
                         "Takes [txnHash: DATA(64)]")

    def test_get_transaction_by_block_hash_and_index(self):
        """Tests that a transaction is retrieved correctly given a block
        signature and transaction index."""
        block_id = "a" * 128
        block_num = 678
        txn_ids = [
            "0" * 64,
            "1" * 64,
            "2" * 64,
            "3" * 64,
        ]
        txn_idx = 2
        nonce = 4
        pub_key = "035e1de3048a62f9f478440a22fd7655b" + \
                  "80f0aac997be963b119ac54b3bfdea3b7"
        addr = "b4d09ca3c0bc538340e904b689016bbb4248136c"

        gas = 100
        to_b = bytes([0xab, 0xcd, 0xef])
        to_s = "abcdef"
        data_b = bytes([0x67, 0x89])
        data_s = "6789"
        # self._test_get_transaction_by_idx(by="hash")
        self.rpc.acall(
            "eth_getTransactionByBlockHashAndIndex",
            ["0x" + block_id, hex(txn_idx)])
        msg, request = self._receive_block_request()

        self.assertEqual(request.block_id, block_id)

        block = self._make_multi_txn_block(
            txn_ids, nonce, block_num, block_id, pub_key, gas, to_b,
            data_b)

        self._send_block_back(msg, block)

        result = self.rpc.get_result()
        self.assertEqual(result["hash"], "0x" + txn_ids[txn_idx])
        self.assertEqual(result["nonce"], hex(nonce))
        self.assertEqual(result["blockHash"], "0x" + block_id)
        self.assertEqual(result["blockNumber"], hex(block_num))
        self.assertEqual(result["transactionIndex"], hex(txn_idx))
        self.assertEqual(result["from"], "0x" + addr)
        self.assertEqual(result["to"], "0x" + to_s)
        self.assertEqual(result["value"], "0x0")
        self.assertEqual(result["gasPrice"], "0x0")
        self.assertEqual(result["gas"], hex(gas))
        self.assertEqual(result["input"], "0x" + data_s)

    def test_get_transaction_by_block_hash_and_index_bad_input(self):
        """Test that the correct error message is returned if no input is given
           to eth_getTransactionByBlockHashAndIndex.
        """
        self.rpc.acall("eth_getTransactionByBlockHashAndIndex",)
        result = self.rpc.get_result()
        self.assertEqual(result["error"]["message"],
                         "Takes [blockHash: DATA(64), index: QUANTITY]")

    def test_get_transaction_by_block_number_and_index(self):
        """Tests that a transaction is retrieved correctly given a block
        number and transaction index."""
        block_id = "a" * 128
        block_num = 678
        txn_ids = [
            "0" * 64,
            "1" * 64,
            "2" * 64,
            "3" * 64,
        ]
        txn_idx = 2
        nonce = 4
        pub_key = "035e1de3048a62f9f478440a22fd7655b" + \
                  "80f0aac997be963b119ac54b3bfdea3b7"
        addr = "b4d09ca3c0bc538340e904b689016bbb4248136c"

        gas = 100
        to_b = bytes([0xab, 0xcd, 0xef])
        to_s = "abcdef"
        data_b = bytes([0x67, 0x89])
        data_s = "6789"

        self.rpc.acall(
            "eth_getTransactionByBlockNumberAndIndex",
            [hex(block_num), hex(txn_idx)])

        msg, request = self._receive_block_request()

        self.assertEqual(request.block_num, block_num)

        block = self._make_multi_txn_block(
            txn_ids, nonce, block_num, block_id, pub_key, gas, to_b,
            data_b)

        self._send_block_back(msg, block)

        result = self.rpc.get_result()
        self.assertEqual(result["hash"], "0x" + txn_ids[txn_idx])
        self.assertEqual(result["nonce"], hex(nonce))
        self.assertEqual(result["blockHash"], "0x" + block_id)
        self.assertEqual(result["blockNumber"], hex(block_num))
        self.assertEqual(result["transactionIndex"], hex(txn_idx))
        self.assertEqual(result["from"], "0x" + addr)
        self.assertEqual(result["to"], "0x" + to_s)
        self.assertEqual(result["value"], "0x0")
        self.assertEqual(result["gasPrice"], "0x0")
        self.assertEqual(result["gas"], hex(gas))
        self.assertEqual(result["input"], "0x" + data_s)

    def test_get_transaction_by_block_number_and_index_bad_input(self):
        """Test that the correct error message is returned if no input is given
           to eth_getTransactionByBlockHashAndIndex.
        """
        self.rpc.acall("eth_getTransactionByBlockNumberAndIndex",)
        result = self.rpc.get_result()
        self.assertEqual(result["error"]["message"],
                         "Takes [blockNum: DATA(64), index: QUANTITY]")

    def test_get_transaction_no_block(self):
        block_id = "a" * 128
        block_num = 678
        txn_ids = [
            "0" * 64,
            "1" * 64,
            "2" * 64,
            "3" * 64,
        ]
        txn_idx = 2
        nonce = 4
        pub_key = "035e1de3048a62f9f478440a22fd7655b" + \
                  "80f0aac997be963b119ac54b3bfdea3b7"
        addr = "b4d09ca3c0bc538340e904b689016bbb4248136c"

        gas = 100
        to_b = bytes([0xab, 0xcd, 0xef])
        to_s = "abcdef"
        data_b = bytes([0x67, 0x89])
        data_s = "6789"

        self.rpc.acall(
            "eth_getTransactionByBlockNumberAndIndex",
            [hex(block_num), hex(txn_idx)])

        msg, request = self._receive_block_request()

        self.assertEqual(request.block_num, block_num)

        self._send_block_no_resource(msg)

        result = self.rpc.get_result()
        self.assertIsNone(result)

    def test_get_transaction_by_block_hash_and_index_no_block(self):
        """Tests that a transaction is retrieved correctly given a block
        signature and transaction index, where the block doesn't exist but the
        transaction does."""
        block_id = "a" * 128
        txn_idx = 2

        self.rpc.acall(
            "eth_getTransactionByBlockHashAndIndex",
            ["0x" + block_id, hex(txn_idx)])

        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BLOCK_GET_REQUEST)
        request = ClientBlockGetRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.block_id, block_id)

        self.validator.respond(
            Message.CLIENT_BLOCK_GET_RESPONSE,
            ClientBlockGetResponse(status=ClientBlockGetResponse.NO_RESOURCE),
            msg)

        result = self.rpc.get_result()
        self.assertEqual(result, None)

    def _send_block_back(self, msg, block=None):
        if block is None:
            block = Block(
                header=BlockHeader(
                    block_num=self.block_num,
                    previous_block_id=self.prev_block_id,
                    state_root_hash=self.state_root
                ).SerializeToString(),
                header_signature=self.block_id,
                batches=[Batch(transactions=[Transaction(
                    header=TransactionHeader(
                        family_name="seth",
                    ).SerializeToString(),
                    header_signature=self.txn_id,
                )])],
            )

        self.validator.respond(
            Message.CLIENT_BLOCK_GET_RESPONSE,
            ClientBlockGetResponse(
                status=ClientBlockGetResponse.OK,
                block=block
            ),
            msg)

    def _send_block_no_resource(self, msg):
        self.validator.respond(
            Message.CLIENT_BLOCK_GET_RESPONSE,
            ClientBlockGetResponse(
                status=ClientBlockGetResponse.NO_RESOURCE
            ),
            msg)

    def _send_state_no_resource(self, msg):
        self.validator.respond(
            Message.CLIENT_STATE_GET_RESPONSE,
            ClientStateGetResponse(
                status=ClientStateGetResponse.NO_RESOURCE,
                ),
            msg)

    def _send_receipts_back(self, msg):
        self.validator.respond(
            Message.CLIENT_RECEIPT_GET_RESPONSE,
            ClientReceiptGetResponse(
                status=ClientReceiptGetResponse.OK,
                receipts=[TransactionReceipt(
                    data=[TransactionReceipt.Data(
                        data_type="seth_receipt",
                        data=SethTransactionReceipt(
                            gas_used=self.gas,
                        ).SerializeToString(),
                    )],
                    transaction_id=self.txn_id,
                )]
            ),
            msg)

    def _send_state_response(self, msg):
        self.validator.respond(
            Message.CLIENT_STATE_GET_RESPONSE,
            ClientStateGetResponse(
                status=ClientStateGetResponse.OK,
                value=EvmEntry(
                    account=EvmStateAccount(
                        balance=self.balance,
                        nonce=self.nonce,
                        code=self.code_b),
                    storage=[EvmStorage(key=self.position_b,
                                        value=self.stored_b)],
                ).SerializeToString()),
            msg)

    def _receive_receipt_request(self):
        # Verify receipt get request
        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_RECEIPT_GET_REQUEST)
        request = ClientReceiptGetRequest()
        request.ParseFromString(msg.content)
        return msg, request


    def _receive_block_request(self):
        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BLOCK_GET_REQUEST)
        request = ClientBlockGetRequest()
        request.ParseFromString(msg.content)
        return msg, request

    def _receive_state_request(self):
        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_STATE_GET_REQUEST)
        request = ClientStateGetRequest()
        request.ParseFromString(msg.content)
        return msg, request

    def _make_multi_txn_block(self, txn_ids, nonce, block_num, block_id,
                              pub_key, gas, to, data):
        txns = [
            Transaction(
                header=TransactionHeader(
                    family_name="seth",
                    signer_pubkey=pub_key,
                ).SerializeToString(),
                header_signature=txn_ids[i],
                payload=txn.SerializeToString())
            for i, txn in enumerate([
                SethTransaction(
                    transaction_type=SethTransaction.SET_PERMISSIONS,
                    set_permissions=SetPermissionsTxn()),
                SethTransaction(
                    transaction_type=SethTransaction.CREATE_EXTERNAL_ACCOUNT,
                    create_external_account=CreateExternalAccountTxn()),
                SethTransaction(
                    transaction_type=SethTransaction.MESSAGE_CALL,
                    message_call=MessageCallTxn(
                        nonce=nonce,
                        gas_limit=gas,
                        to=to,
                        data=data,
                )),
                SethTransaction(
                    transaction_type=SethTransaction.CREATE_CONTRACT_ACCOUNT,
                    create_contract_account=CreateContractAccountTxn()),
            ])
        ]

        return Block(
            header=BlockHeader(
                block_num=block_num,
            ).SerializeToString(),
            header_signature=block_id,
            batches=[
                Batch(transactions=txns[0:1]),
                Batch(transactions=txns[1:3]),
                Batch(transactions=txns[3:4]),
            ])
