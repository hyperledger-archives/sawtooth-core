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
from sawtooth_sdk.protobuf.client_block_pb2 import ClientBlockListRequest
from sawtooth_sdk.protobuf.client_block_pb2 import ClientBlockListResponse
from sawtooth_sdk.protobuf.client_block_pb2 import ClientBlockGetByIdRequest
from sawtooth_sdk.protobuf.client_block_pb2 import ClientBlockGetByNumRequest
from sawtooth_sdk.protobuf.client_block_pb2 import \
    ClientBlockGetByTransactionIdRequest
from sawtooth_sdk.protobuf.client_block_pb2 import ClientBlockGetResponse
from sawtooth_sdk.protobuf.client_state_pb2 import ClientStateGetRequest
from sawtooth_sdk.protobuf.client_state_pb2 import ClientStateGetResponse
from sawtooth_sdk.protobuf.client_transaction_pb2 import \
    ClientTransactionGetRequest
from sawtooth_sdk.protobuf.client_transaction_pb2 import \
    ClientTransactionGetResponse
from sawtooth_sdk.protobuf.client_batch_submit_pb2 import \
    ClientBatchSubmitRequest
from sawtooth_sdk.protobuf.client_batch_submit_pb2 import \
    ClientBatchSubmitResponse
from sawtooth_sdk.protobuf.block_pb2 import Block
from sawtooth_sdk.protobuf.block_pb2 import BlockHeader
from sawtooth_sdk.protobuf.batch_pb2 import Batch
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader
from sawtooth_sdk.protobuf.transaction_pb2 import Transaction
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_sdk.protobuf.client_receipt_pb2 import ClientReceiptGetRequest
from sawtooth_sdk.protobuf.client_receipt_pb2 import ClientReceiptGetResponse
from sawtooth_sdk.protobuf.transaction_receipt_pb2 import TransactionReceipt
from sawtooth_sdk.protobuf.events_pb2 import Event
from protobuf.seth_pb2 import SethTransactionReceipt
from protobuf.seth_pb2 import EvmEntry
from protobuf.seth_pb2 import EvmStateAccount
from protobuf.seth_pb2 import EvmStorage
from protobuf.seth_pb2 import SethTransaction
from protobuf.seth_pb2 import CreateExternalAccountTxn
from protobuf.seth_pb2 import CreateContractAccountTxn
from protobuf.seth_pb2 import MessageCallTxn
from protobuf.seth_pb2 import SetPermissionsTxn

import logging
LOGGER = logging.getLogger(__name__)


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
        cls.public_key = "036d7bb6ca0fd581eb037e91042320af97508003264f08545a9db134df215f373e"
        cls.account_address = "434d46456b6973a678b77382fca0252629f4389f"
        cls.contract_address = "f" * 20 * 2
        cls.contract_address_b = bytes([0xff] * 20)
        cls.contract_init_s = "0" * 60 * 2
        cls.contract_init_b = bytes([0x0] * 60)
        cls.contract_init_txn_id = "cfb0f4224ec4effa35092161c7e84021bccf3527ff5c042e9cccf94478cbb1223f548e3f38af881605b3cf412b35432f45db5a1301e0f4758a094ffbd9f9f0c8"
        cls.contract_call_s = "0" * 30 * 2
        cls.contract_call_b = bytes([0x0] * 30)
        cls.contract_call_txn_id = "5faa8f3ed941dc68f94678c5e28ed0a5997d461fd7f92fdcc00a17f7f7144c27743b43565bb913ac5ac33239220063f5c887246e0f3bbb22a7bd7f07d0ba8fe6"
        cls.balance = 123
        cls.nonce = 456
        cls.code_b = bytes([0xab, 0xcd, 0xef])
        cls.code_s = "abcdef"
        cls.position_b = bytes([0x01, 0x23, 0x45])
        cls.position_s = "012345"
        cls.stored_b = bytes([0x67, 0x89])
        cls.stored_s = "6789"
        cls.topic1_s = "ff" * 32
        cls.topic1_b = bytes([0xff] * 32)
        cls.topic2_s = "cc" * 32
        cls.topic2_b = bytes([0xcc] * 32)
        cls.log_data_s = "8888"
        cls.log_data_b = bytes([0x88, 0x88])
        cls.return_value_s = "2a"
        cls.return_value_b = bytes([0x2a])

    # -- Network tests -- #
    def test_net_version(self):
        """Test that the network id 19 is returned."""
        self.assertEqual("19", self.rpc.call("net_version"))

    def test_net_peerCount(self):
        """Test that 0 is returned as hex."""
        self.assertEqual("0x0", self.rpc.call("net_peerCount"))

    def test_net_listening(self):
        """Test that the True is returned."""
        self.assertEqual(True, self.rpc.call("net_listening"))

    # -- Block tests -- #
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
        msg, request = self._receive_block_request_id()
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
        msg, request = self._receive_block_request_id()
        self.assertEqual(request.block_id, bad_id)

        self._send_block_no_resource(msg)

        result = self.rpc.get_result()
        self.assertIsNone(result)

    def test_get_block_transaction_count_by_number(self):
        """Test that a block transaction count is retrieved correctly, given a
        block number."""
        self.rpc.acall(
            "eth_getBlockTransactionCountByNumber", [hex(self.block_num)])
        msg, request = self._receive_block_request_num()
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
        msg, request = self._receive_block_request_num()
        self.assertEqual(request.block_num, bad_num)

        self._send_block_no_resource(msg)

        result = self.rpc.get_result()
        self.assertIsNone(result)

    def test_get_block_by_hash(self):
        """Test that a block is retrieved correctly, given a block hash."""
        self.rpc.acall("eth_getBlockByHash", ["0x" + self.block_id, False])
        msg, request = self._receive_block_request_id()
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
        msg, request = self._receive_block_request_id()
        self.assertEqual(request.block_id, bad_id)

        self._send_block_no_resource(msg)
        result = self.rpc.get_result()
        self.assertIsNone(result)

    def test_get_block_by_number(self):
        """Test that a block is retrieved correctly, given a block number."""
        self.rpc.acall("eth_getBlockByNumber", [hex(self.block_num), False])
        msg, request = self._receive_block_request_num()
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
        msg, request = self._receive_block_request_num()
        self.assertEqual(request.block_num, bad_num)

        self._send_block_no_resource(msg)
        result = self.rpc.get_result()
        self.assertIsNone(result)

    # -- Account tests -- #
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
        state_root = "b" * 64

        self.rpc.acall(
            "eth_getBalance", ["0x" + account_address, hex(block_num)])

        msg = self.validator.receive()
        self.assertEqual(msg.message_type,
                         Message.CLIENT_BLOCK_GET_BY_NUM_REQUEST)
        request = ClientBlockGetByNumRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.block_num, block_num)

        self.validator.respond(
            Message.CLIENT_BLOCK_GET_RESPONSE,
            ClientBlockGetResponse(
                status=ClientBlockGetResponse.OK,
                block=Block(
                    header_signature=block_id,
                    header=BlockHeader(
                        state_root_hash=state_root,
                    ).SerializeToString(),
                )
            ),
            msg)

        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_STATE_GET_REQUEST)
        request = ClientStateGetRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.state_root, state_root)
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

    # -- Transaction tests -- #
    def test_get_transaction_by_hash(self):
        """Tests that a transaction is retrieved correctly given its hash."""
        txn_ids = [
            "0" * 64,
            "1" * 64,
            "2" * 64,
            "3" * 64,
        ]
        txn_idx = 2

        self.rpc.acall(
            "eth_getTransactionByHash",
            ["0x" + txn_ids[txn_idx]])

        msg, request = self._receive_transaction_request()
        self.assertEqual(request.transaction_id, txn_ids[txn_idx])

        block = self._make_multi_txn_block(txn_ids)

        self._send_transaction_response(msg, block.batches[1].transactions[1])

        msg, request = self._receive_block_request_transaction()

        self._send_block_back(msg, block)

        result = self.rpc.get_result()
        self.assertEqual(result["hash"], "0x" + txn_ids[txn_idx])
        self.assertEqual(result["nonce"], hex(self.nonce))
        self.assertEqual(result["blockHash"], "0x" + self.block_id)
        self.assertEqual(result["blockNumber"], hex(self.block_num))
        self.assertEqual(result["transactionIndex"], hex(txn_idx))
        self.assertEqual(result["from"], "0x" + self.account_address)
        self.assertEqual(result["to"], "0x" + self.contract_address)
        self.assertEqual(result["value"], "0x0")
        self.assertEqual(result["gasPrice"], "0x0")
        self.assertEqual(result["gas"], hex(self.gas))
        self.assertEqual(result["input"], "0x" + self.contract_call_s)

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
        txn_ids = [
            "0" * 64,
            "1" * 64,
            "2" * 64,
            "3" * 64,
        ]
        txn_idx = 2

        self.rpc.acall(
            "eth_getTransactionByBlockHashAndIndex",
            ["0x" + self.block_id, hex(txn_idx)])
        msg, request = self._receive_block_request_id()

        self.assertEqual(request.block_id, self.block_id)

        block = self._make_multi_txn_block(txn_ids)

        self._send_block_back(msg, block)

        result = self.rpc.get_result()
        self.assertEqual(result["hash"], "0x" + txn_ids[txn_idx])
        self.assertEqual(result["nonce"], hex(self.nonce))
        self.assertEqual(result["blockHash"], "0x" + self.block_id)
        self.assertEqual(result["blockNumber"], hex(self.block_num))
        self.assertEqual(result["transactionIndex"], hex(txn_idx))
        self.assertEqual(result["from"], "0x" + self.account_address)
        self.assertEqual(result["to"], "0x" + self.contract_address)
        self.assertEqual(result["value"], "0x0")
        self.assertEqual(result["gasPrice"], "0x0")
        self.assertEqual(result["gas"], hex(self.gas))
        self.assertEqual(result["input"], "0x" + self.contract_call_s)

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
        txn_ids = [
            "0" * 64,
            "1" * 64,
            "2" * 64,
            "3" * 64,
        ]
        txn_idx = 2

        self.rpc.acall(
            "eth_getTransactionByBlockNumberAndIndex",
            [hex(self.block_num), hex(txn_idx)])

        msg, request = self._receive_block_request_num()

        self.assertEqual(request.block_num, self.block_num)

        block = self._make_multi_txn_block(txn_ids)

        self._send_block_back(msg, block)

        result = self.rpc.get_result()
        self.assertEqual(result["hash"], "0x" + txn_ids[txn_idx])
        self.assertEqual(result["nonce"], hex(self.nonce))
        self.assertEqual(result["blockHash"], "0x" + self.block_id)
        self.assertEqual(result["blockNumber"], hex(self.block_num))
        self.assertEqual(result["transactionIndex"], hex(txn_idx))
        self.assertEqual(result["from"], "0x" + self.account_address)
        self.assertEqual(result["to"], "0x" + self.contract_address)
        self.assertEqual(result["value"], "0x0")
        self.assertEqual(result["gasPrice"], "0x0")
        self.assertEqual(result["gas"], hex(self.gas))
        self.assertEqual(result["input"], "0x" + self.contract_call_s)

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

        msg, request = self._receive_block_request_num()

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
        self.assertEqual(msg.message_type,
                         Message.CLIENT_BLOCK_GET_BY_ID_REQUEST)
        request = ClientBlockGetByIdRequest()
        request.ParseFromString(msg.content)
        self.assertEqual(request.block_id, block_id)

        self.validator.respond(
            Message.CLIENT_BLOCK_GET_RESPONSE,
            ClientBlockGetResponse(status=ClientBlockGetResponse.NO_RESOURCE),
            msg)

        result = self.rpc.get_result()
        self.assertEqual(result, None)

    def test_send_transaction_contract_creation(self):
        """Tests that a contract creation txn is submitted correctly."""
        self.rpc.acall(
            "eth_sendTransaction", [{
                "from": "0x" + self.account_address,
                "data": "0x" + self.contract_init_s
        }])

        msg, txn = self._receive_submit_request()

        seth_txn = SethTransaction()
        seth_txn.ParseFromString(txn.payload)
        self.assertEqual(
            seth_txn.transaction_type, SethTransaction.CREATE_CONTRACT_ACCOUNT)
        create = seth_txn.create_contract_account
        self.assertEqual(create.init, self.contract_init_b)
        self.assertEqual(create.gas_limit, 90000)
        self.assertEqual(create.gas_price, 10000000000000)
        self.assertEqual(create.value, 0)
        self.assertEqual(create.nonce, 0)

        self._send_submit_response(msg)
        self.assertEqual(
            "0x" + self.contract_init_txn_id, self.rpc.get_result())

    def test_send_transaction_message_call(self):
        """Tests that a message call txn is submitted correctly."""
        self.rpc.acall(
            "eth_sendTransaction", [{
                "from": "0x" + self.account_address,
                "data": "0x" + self.contract_call_s,
                "to": "0x" + self.contract_address,
        }])

        msg, txn = self._receive_submit_request()

        seth_txn = SethTransaction()
        seth_txn.ParseFromString(txn.payload)
        self.assertEqual(
            seth_txn.transaction_type, SethTransaction.MESSAGE_CALL)
        call = seth_txn.message_call
        self.assertEqual(call.data, self.contract_call_b)
        self.assertEqual(call.gas_limit, 90000)
        self.assertEqual(call.gas_price, 10000000000000)
        self.assertEqual(call.value, 0)
        self.assertEqual(call.nonce, 0)

        self._send_submit_response(msg)
        self.assertEqual(
            "0x" + self.contract_call_txn_id, self.rpc.get_result())

    def test_get_transaction_receipt(self):
        """Tests that a transaction receipt is retrieved correctly."""
        self.rpc.acall(
            "eth_getTransactionReceipt", ["0x" + self.txn_id])

        msg, request = self._receive_receipt_request()
        self.assertEqual(request.transaction_ids[0], self.txn_id)
        self._send_receipts_back(msg)

        msg, request = self._receive_transaction_request()
        self._send_transaction_response(msg)
        msg, request = self._receive_block_request_transaction()
        block = Block(
            header=BlockHeader(block_num=self.block_num).SerializeToString(),
            header_signature=self.block_id,
            batches=[Batch(transactions=[
                Transaction(header_signature=self.txn_id)])])
        self._send_block_back(msg, block)

        result = self.rpc.get_result()
        self.assertEqual(result["transactionHash"], "0x" + self.txn_id)
        self.assertEqual(result["transactionIndex"], hex(0))
        self.assertEqual(result["blockHash"], "0x" + self.block_id)
        self.assertEqual(result["blockNumber"], hex(self.block_num))
        self.assertEqual(result["cumulativeGasUsed"], hex(self.gas))
        self.assertEqual(result["gasUsed"], hex(self.gas))
        self.assertEqual(result["returnValue"], "0x" + self.return_value_s)
        self.assertEqual(
            result["contractAddress"], "0x" + self.contract_address)

        log = result["logs"][0]
        self.assertEqual(log["removed"], False)
        self.assertEqual(log["logIndex"], hex(0))
        self.assertEqual(log["transactionIndex"], hex(0))
        self.assertEqual(log["transactionHash"], "0x" + self.txn_id)
        self.assertEqual(log["blockHash"], "0x" + self.block_id)
        self.assertEqual(log["blockNumber"], hex(self.block_num))
        self.assertEqual(log["address"], "0x" + self.contract_address)
        self.assertEqual(log["data"], "0x" + self.log_data_s)

        topic1, topic2 = log["topics"]
        self.assertEqual(topic1, "0x" + self.topic1_s)
        self.assertEqual(topic2, "0x" + self.topic2_s)

    def test_gas_price(self):
        """Tests that the gas price is returned correctly."""
        self.assertEqual("0x0", self.rpc.call("eth_gasPrice"))

    def test_sign(self):
        """Tests that a payload is signed correctly."""
        msg = b"test"
        signature = self.rpc.call(
            "eth_sign", ["0x" + self.account_address, "0x" + msg.hex()])
        self.assertEqual(signature,
            "0x4bd3560fcabbe7c13d8829dcb82b381fe3882db14aeb6d22b8b0ea069e60" +\
            "28a02d85497c9b26203c31f028f31fa0ae9b944aa219ae6ecf7655b2e2428d" +\
            "d6904f")

    # -- Log tests -- #
    def test_new_filter(self):
        """Test that new log filters are created sequentially and that nothing
        breaks while creating them."""
        self.rpc.acall("eth_newFilter", [{
            "fromBlock": "0x1",
            "toBlock": "0x2",
            "address": "0x" + self.contract_address,
            "topics": [
                "0x000000000000000000000000a94f5374fce5edbc8e2a8697c15331677e6ebf0b",
                None,
                [
                    "0x000000000000000000000000a94f5374fce5edbc8e2a8697c15331677e6ebf0b",
                    "0x0000000000000000000000000aff3454fce5edbc8cca8697c15331677e6ebccc"
                ,]
            ]
        }])
        self._block_list_exchange()
        result = self.rpc.get_result()
        n = int(result, 16)
        self.rpc.acall("eth_newFilter", [{
            "address": [
                "0x" + self.contract_address,
                "0x" + self.account_address,
            ],
            "topics": [],
        }])
        self._block_list_exchange()
        result = self.rpc.get_result()
        n_plus_1 = int(result, 16)
        self.assertEqual(n + 1, n_plus_1)

    def test_new_block_filter(self):
        """Test that new block filters are created sequentially and that
        nothing breaks while creating them."""
        self.rpc.acall("eth_newBlockFilter")
        self._block_list_exchange()
        result = self.rpc.get_result()
        n = int(result, 16)
        self.rpc.acall("eth_newBlockFilter")
        self._block_list_exchange()
        result = self.rpc.get_result()
        n_plus_1 = int(result, 16)
        self.assertEqual(n + 1, n_plus_1)

    def test_new_transaction_filter(self):
        """Test that new transaction filters are created sequentially and that
        nothing breaks while creating them."""
        self.rpc.acall("eth_newPendingTransactionFilter")
        self._block_list_exchange()
        result = self.rpc.get_result()
        n = int(result, 16)
        self.rpc.acall("eth_newPendingTransactionFilter")
        self._block_list_exchange()
        result = self.rpc.get_result()
        n_plus_1 = int(result, 16)
        self.assertEqual(n + 1, n_plus_1)

    def test_uninstall_filter(self):
        """Test that uninstalling a filter works"""
        self.rpc.acall("eth_newBlockFilter")
        self._block_list_exchange()
        filter_id = self.rpc.get_result()
        self.assertEqual(
            True, self.rpc.call("eth_uninstallFilter", [filter_id]))

    def test_get_logs(self):
        """Test that getting logs works."""
        log_filter = {
            "fromBlock": hex(self.block_num),
            "address": "0x" + self.contract_address,
            "topics": [
                "0x" + self.topic1_s,
                ["0x" + self.topic1_s, "0x" + self.topic2_s]
            ],
        }

        self.rpc.acall("eth_getLogs", [log_filter])

        msg, request = self._receive_block_request_num()
        self.assertEqual(request.block_num, self.block_num)
        self._send_block_back(msg)

        msg, request = self._receive_receipt_request()
        self._send_receipts_back(msg)

        msg, request = self._receive_block_request_num()
        self.assertEqual(request.block_num, self.block_num + 1)
        self._send_block_no_resource(msg)

        result = self.rpc.get_result()
        log = result[0]
        self.assertEqual(log["removed"], False)
        self.assertEqual(log["logIndex"], hex(0))
        self.assertEqual(log["transactionIndex"], hex(0))
        self.assertEqual(log["transactionHash"], "0x" + self.txn_id)
        self.assertEqual(log["blockHash"], "0x" + self.block_id)
        self.assertEqual(log["blockNumber"], hex(self.block_num))
        self.assertEqual(log["address"], "0x" + self.contract_address)
        self.assertEqual(log["data"], "0x" + self.log_data_s)

        topic1, topic2 = log["topics"]
        self.assertEqual(topic1, "0x" + self.topic1_s)
        self.assertEqual(topic2, "0x" + self.topic2_s)

    def test_get_filter_logs(self):
        """Test that getting logs from a filter works."""
        log_filter = {
            "fromBlock": hex(self.block_num),
            "address": "0x" + self.contract_address,
            "topics": [
                "0x" + self.topic1_s,
                ["0x" + self.topic1_s, "0x" + self.topic2_s]
            ],
        }

        self.rpc.acall("eth_newFilter", [log_filter])
        self._block_list_exchange()
        filter_id = self.rpc.get_result()

        self.rpc.acall("eth_getFilterLogs", [filter_id])
        msg, request = self._receive_block_request_num()
        self.assertEqual(request.block_num, self.block_num)
        self._send_block_back(msg)

        msg, request = self._receive_receipt_request()
        self._send_receipts_back(msg)

        msg, request = self._receive_block_request_num()
        self.assertEqual(request.block_num, self.block_num + 1)
        self._send_block_no_resource(msg)

        result = self.rpc.get_result()
        log = result[0]
        self.assertEqual(log["removed"], False)
        self.assertEqual(log["logIndex"], hex(0))
        self.assertEqual(log["transactionIndex"], hex(0))
        self.assertEqual(log["transactionHash"], "0x" + self.txn_id)
        self.assertEqual(log["blockHash"], "0x" + self.block_id)
        self.assertEqual(log["blockNumber"], hex(self.block_num))
        self.assertEqual(log["address"], "0x" + self.contract_address)
        self.assertEqual(log["data"], "0x" + self.log_data_s)

        topic1, topic2 = log["topics"]
        self.assertEqual(topic1, "0x" + self.topic1_s)
        self.assertEqual(topic2, "0x" + self.topic2_s)

    def test_get_block_filter_changes(self):
        """Tests that getting block filter changes works."""
        self.rpc.acall("eth_newBlockFilter")
        self._block_list_exchange()
        filter_id = self.rpc.get_result()

        block_id_plus_1 = "e" * 128
        block_id_plus_2 = "d" * 128
        self.rpc.acall("eth_getFilterChanges", [filter_id])
        self._block_list_exchange(blocks=[Block(
            header=BlockHeader(
                block_num=self.block_num+2,
            ).SerializeToString(),
            header_signature=block_id_plus_2,
        )])
        self._block_get_exchange(block=Block(
            header=BlockHeader(
                block_num=self.block_num+1,
            ).SerializeToString(),
            header_signature=block_id_plus_1,
        ))
        result = self.rpc.get_result()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "0x" + block_id_plus_1)
        self.assertEqual(result[1], "0x" + block_id_plus_2)

    def test_get_transaction_filter_changes(self):
        """Tests that getting transaction filter changes works."""
        self.rpc.acall("eth_newPendingTransactionFilter")
        self._block_list_exchange()
        filter_id = self.rpc.get_result()

        txn_id_1 = "e" * 128
        txn_id_2 = "d" * 128
        self.rpc.acall("eth_getFilterChanges", [filter_id])
        self._block_list_exchange(blocks=[Block(
            header=BlockHeader(
                block_num=self.block_num+2,
            ).SerializeToString(),
            batches=[Batch(transactions=[Transaction(
                header=TransactionHeader(
                    family_name="seth",
                ).SerializeToString(),
                header_signature=txn_id_2,
            )])],
        )])
        self._block_get_exchange(block=Block(
            header=BlockHeader(
                block_num=self.block_num+1,
            ).SerializeToString(),
            batches=[Batch(transactions=[Transaction(
                header=TransactionHeader(
                    family_name="seth",
                ).SerializeToString(),
                header_signature=txn_id_1,
            )])],
        ))
        result = self.rpc.get_result()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "0x" + txn_id_1)
        self.assertEqual(result[1], "0x" + txn_id_2)

    def test_get_log_filter_changes(self):
        """Tests that getting log filter changes works."""
        txn_ids = [
            "d" * 128,
            "e" * 128,
        ]
        topics = [
            self.topic1_s,
            self.topic2_s,
        ]

        # Create the filter
        self.rpc.acall("eth_newFilter", [{
            "address": "0x" + self.contract_address,
            "topics": [
                ["0x" + t for t in topics],
            ]
        }])
        self._block_list_exchange()
        filter_id = self.rpc.get_result()

        # Request changes
        self.rpc.acall("eth_getFilterChanges", [filter_id])

        # Exchange blocks
        self._block_list_exchange(blocks=[Block(
            header=BlockHeader(
                block_num=self.block_num+2,
            ).SerializeToString(),
            header_signature=self.block_id,
            batches=[Batch(transactions=[Transaction(
                header=TransactionHeader(
                    family_name="seth",
                ).SerializeToString(),
                header_signature=txn_ids[1],
            )])],
        )])
        self._block_get_exchange(block=Block(
            header=BlockHeader(
                block_num=self.block_num+1,
            ).SerializeToString(),
            header_signature=self.block_id,
            batches=[Batch(transactions=[Transaction(
                header=TransactionHeader(
                    family_name="seth",
                ).SerializeToString(),
                header_signature=txn_ids[0],
            )])],
        ))

        receipts = [
            TransactionReceipt(
                data=[SethTransactionReceipt(
                    gas_used=self.gas,
                    return_value=self.return_value_b,
                    contract_address=self.contract_address_b,
                    ).SerializeToString(),
                ],
                events=[Event(
                    event_type="seth_log_event",
                    attributes=[
                        Event.Attribute(key="address", value=self.contract_address),
                        Event.Attribute(key="topic1", value=topics[0]),
                    ],
                    data=self.log_data_b,
                )],
                transaction_id=txn_ids[0],
            ),
            TransactionReceipt(
                data=[SethTransactionReceipt(
                    gas_used=self.gas,
                    return_value=self.return_value_b,
                    contract_address=self.contract_address_b,
                    ).SerializeToString(),
                ],
                events=[Event(
                    event_type="seth_log_event",
                    attributes=[
                        Event.Attribute(key="address", value=self.contract_address),
                        Event.Attribute(key="topic1", value=topics[1]),
                    ],
                    data=self.log_data_b,
                )],
                transaction_id=txn_ids[1],
            ),
        ]

        # Exchange receipts for block 1
        msg, request = self._receive_receipt_request()
        self.assertEqual(request.transaction_ids[0], txn_ids[0])
        self._send_receipts_back(msg, [receipts[0]])

        # Exchange receipts for block 2
        msg, request = self._receive_receipt_request()
        self.assertEqual(request.transaction_ids[0], txn_ids[1])
        self._send_receipts_back(msg, [receipts[1]])

        result = self.rpc.get_result()

        self.assertEqual(len(result), 2)
        for i, log in enumerate(result):
            self.assertEqual(log["removed"], False)
            self.assertEqual(log["logIndex"], hex(0))
            self.assertEqual(log["transactionIndex"], hex(0))
            self.assertEqual(log["transactionHash"], "0x" + txn_ids[i])
            self.assertEqual(log["blockHash"], "0x" + self.block_id)
            self.assertEqual(log["blockNumber"], hex(self.block_num + i + 1))
            self.assertEqual(log["address"], "0x" + self.contract_address)
            self.assertEqual(log["data"], "0x" + self.log_data_s)

            topic1 = log["topics"][0]
            self.assertEqual(topic1, "0x" + topics[i])

    # -- Utilities -- #
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

    def _send_block_list_back(self, msg, blocks=None):
        if blocks is None:
            blocks = [Block(
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
            )]

        self.validator.respond(
            Message.CLIENT_BLOCK_LIST_RESPONSE,
            ClientBlockListResponse(
                status=ClientBlockListResponse.OK,
                blocks=blocks,
            ),
            msg)

    def _send_state_no_resource(self, msg):
        self.validator.respond(
            Message.CLIENT_STATE_GET_RESPONSE,
            ClientStateGetResponse(
                status=ClientStateGetResponse.NO_RESOURCE,
                ),
            msg)

    def _send_receipts_back(self, msg, receipts=None):
        if receipts is None:
            receipts = [TransactionReceipt(
                data=[SethTransactionReceipt(
                    gas_used=self.gas,
                    return_value=self.return_value_b,
                    contract_address=self.contract_address_b,
                    ).SerializeToString(),
                ],
                events=[Event(
                    event_type="seth_log_event",
                    attributes=[
                        Event.Attribute(key="address", value=self.contract_address),
                        Event.Attribute(key="topic1", value=self.topic1_s),
                        Event.Attribute(key="topic2", value=self.topic2_s),
                    ],
                    data=self.log_data_b,
                )],
                transaction_id=self.txn_id,
            )]
        self.validator.respond(
            Message.CLIENT_RECEIPT_GET_RESPONSE,
            ClientReceiptGetResponse(
                status=ClientReceiptGetResponse.OK,
                receipts=receipts),
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

    def _send_transaction_response(self, msg, transaction=None):
        if transaction is None:
            transaction = Transaction(
                header=TransactionHeader(
                    family_name="seth",
                    signer_public_key=self.public_key,
                ).SerializeToString(),
                header_signature=self.txn_id,
                payload=SethTransaction(
                    transaction_type=SethTransaction.MESSAGE_CALL
                ).SerializeToString())
        self.validator.respond(
            Message.CLIENT_TRANSACTION_GET_RESPONSE,
            ClientTransactionGetResponse(
                status=ClientBlockGetResponse.OK,
                transaction=transaction),
            msg)


    def _send_submit_response(self, msg):
        self.validator.respond(
            Message.CLIENT_BATCH_SUBMIT_RESPONSE,
            ClientBatchSubmitResponse(status=ClientBatchSubmitResponse.OK),
            msg)

    def _receive_receipt_request(self):
        # Verify receipt get request
        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_RECEIPT_GET_REQUEST)
        request = ClientReceiptGetRequest()
        request.ParseFromString(msg.content)
        return msg, request

    def _receive_block_request_transaction(self):
        msg = self.validator.receive()
        self.assertEqual(msg.message_type,
                         Message.CLIENT_BLOCK_GET_BY_TRANSACTION_ID_REQUEST)
        request = ClientBlockGetByTransactionIdRequest()
        request.ParseFromString(msg.content)
        return msg, request

    def _receive_block_request_id(self):
        msg = self.validator.receive()
        self.assertEqual(msg.message_type,
                         Message.CLIENT_BLOCK_GET_BY_ID_REQUEST)
        request = ClientBlockGetByIdRequest()
        request.ParseFromString(msg.content)
        return msg, request

    def _receive_block_request_num(self):
        msg = self.validator.receive()
        self.assertEqual(msg.message_type,
                         Message.CLIENT_BLOCK_GET_BY_NUM_REQUEST)
        request = ClientBlockGetByNumRequest()
        request.ParseFromString(msg.content)
        return msg, request

    def _receive_block_list_request(self):
        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BLOCK_LIST_REQUEST)
        request = ClientBlockListRequest()
        request.ParseFromString(msg.content)
        return msg, request

    def _receive_state_request(self):
        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_STATE_GET_REQUEST)
        request = ClientStateGetRequest()
        request.ParseFromString(msg.content)
        return msg, request

    def _receive_transaction_request(self):
        msg = self.validator.receive()
        self.assertEqual(
            msg.message_type, Message.CLIENT_TRANSACTION_GET_REQUEST)
        request = ClientTransactionGetRequest()
        request.ParseFromString(msg.content)
        return msg, request

    def _receive_submit_request(self):
        msg = self.validator.receive()
        self.assertEqual(msg.message_type, Message.CLIENT_BATCH_SUBMIT_REQUEST)
        request = ClientBatchSubmitRequest()
        request.ParseFromString(msg.content)

        batch = request.batches[0]
        batch_header = BatchHeader()
        batch_header.ParseFromString(batch.header)
        self.assertEqual(batch_header.signer_public_key, self.public_key)

        txn = batch.transactions[0]
        txn_header = TransactionHeader()
        txn_header.ParseFromString(txn.header)
        self.assertEqual(txn_header.signer_public_key, self.public_key)
        self.assertEqual(txn_header.family_name, "seth")
        self.assertEqual(txn_header.family_version, "1.0")

        return msg, txn

    def _block_get_exchange(self, block=None):
        msg, _ = self._receive_block_request_num()
        self._send_block_back(msg, block)

    def _block_list_exchange(self, blocks=None):
        msg, _ = self._receive_block_list_request()
        self._send_block_list_back(msg, blocks)

    def _make_multi_txn_block(self, txn_ids):
        gas = self.gas
        nonce = self.nonce
        block_id = self.block_id
        block_num = self.block_num
        pub_key = self.public_key
        to = self.contract_address_b
        init = self.contract_init_b
        data = self.contract_call_b
        txns = [
            Transaction(
                header=TransactionHeader(
                    family_name="seth",
                    signer_public_key=pub_key,
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
                    create_contract_account=CreateContractAccountTxn(
                        init=init,
                    )),
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
