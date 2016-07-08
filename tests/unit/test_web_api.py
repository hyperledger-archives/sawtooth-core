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

import unittest
import json
import tempfile
import yaml
from twisted.web import http
from twisted.web.http_headers import Headers
from twisted.internet import address

from gossip import common
import gossip.signed_object as SigObj
from gossip.node import Node
from gossip.messages import shutdown_message

from txnserver.web_api import RootPage

from journal.global_store_manager import KeyValueStore, BlockStore
from journal.transaction_block import TransactionBlock, Status
from journal.transaction import Transaction
from journal.transaction import Status as tStatus
from journal.journal_core import Journal


class TestValidator(object):
    def __init__(self, testLedger):
        self.Ledger = testLedger


class TestWebApi(unittest.TestCase):

    # Helper functions
    def _create_node(self, port):
        signingkey = SigObj.generate_signing_key()
        ident = SigObj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", port))
        return node

    def _create_tblock(self, node, blocknum, prevB, transId):
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": blocknum,
                 "PreviousBlockID": prevB, "TransactionIDs": transId}
        transBlock = TransactionBlock(minfo)
        transBlock.sign_from_node(node)
        transBlock.Status = Status.valid
        return transBlock

    def _create_post_request(self, path, data):
        request = http.Request(http.HTTPChannel(), True)
        request.method = "post"
        request.path = path
        request.args = {}
        request.gotLength(1000)
        request.requestHeaders = Headers({"Content-Type":
                                         ['application/json']})
        request.handleContentChunk(json.dumps(data))
        return request

    def _create_get_request(self, path, args):
        request = http.Request(http.HTTPChannel(), True)
        request.method = "get"
        request.path = path
        request.args = args
        return request

    def test_web_api_error_response(self):
        # Test error_response
        LocalNode = self._create_node(8809)
        path = tempfile.mkdtemp()
        # Setup ledger and RootPage

        ledger = Journal(LocalNode, DataDirectory=path, GenesisLedger=True)
        validator = TestValidator(ledger)
        root = RootPage(validator)
        request = self._create_get_request("/stat", {})
        error = root.error_response(request, http.BAD_REQUEST,
                                    'error processing http request {0}',
                                    request.path)
        self.assertEquals(error, "error processing http request /stat\n")

    def test_web_api_forward(self):
        # Test _msgforward
        LocalNode = self._create_node(8807)
        path = tempfile.mkdtemp()
        ledger = Journal(LocalNode, DataDirectory=path, GenesisLedger=True)
        # Create peers for the message to be forwarded to
        node1 = self._create_node(8881)
        node2 = self._create_node(8882)
        node1.is_peer = True
        node2.is_peer = True
        ledger.add_node(node1)
        ledger.add_node(node2)
        validator = TestValidator(ledger)
        root = RootPage(validator)
        # Create message to use and the data to forward
        msg = shutdown_message.ShutdownMessage()
        msg.sign_from_node(LocalNode)
        data = msg.dump()
        # Post /forward
        request = self._create_post_request("forward", data)
        r = yaml.load(root.render_POST(request))
        self.assertEquals(r, data)
        self.assertIn(msg.Identifier, node1.MessageQ.Messages)
        self.assertIn(msg.Identifier, node2.MessageQ.Messages)

    def test_web_api_msg_initiate(self):
        # Test _msginitiate
        LocalNode = self._create_node(8806)
        path = tempfile.mkdtemp()
        ledger = Journal(LocalNode, DataDirectory=path, GenesisLedger=True)
        validator = TestValidator(ledger)
        root = RootPage(validator)
        # Create message to use and the data to  initiate
        msg = shutdown_message.ShutdownMessage()
        data = msg.dump()
        request = self._create_post_request("/initiate", data)
        r = root.render_POST(request)
        self.assertEquals(r, "error processing http request /initiate\n")
        request.client = address.IPv4Address("TCP", '127.0.0.1', 8806)
        # Post /initiate - This should sign the message
        r = yaml.load(root.render_POST(request))
        sig = r["__SIGNATURE__"]
        r.pop("__SIGNATURE__", None)
        data.pop("__SIGNATURE__", None)
        self.assertEquals(r, data)
        self.assertIsNotNone(sig)

    def test_web_api_msg_echo(self):
        # Test _msgecho
        LocalNode = self._create_node(8805)
        path = tempfile.mkdtemp()
        ledger = Journal(LocalNode, DataDirectory=path, GenesisLedger=True)
        validator = TestValidator(ledger)
        root = RootPage(validator)
        # Create message to use and the data to echo
        msg = shutdown_message.ShutdownMessage({'__SIGNATURE__': "test"})
        msg.sign_from_node(LocalNode)
        data = msg.dump()
        # POST /echo
        request = self._create_post_request("/echo", data)
        self.assertEquals(yaml.load(root.render_POST(request)), data)

    def test_web_api_store(self):
        # Test _handlestorerequest
        LocalNode = self._create_node(8800)
        path = tempfile.mkdtemp()
        ledger = Journal(LocalNode, DataDirectory=path, GenesisLedger=True)
        validator = TestValidator(ledger)
        root = RootPage(validator)
        request = self._create_get_request("/store", {})
        try:
            # Test no GlobalStore
            ledger.GlobalStore = None
            root.render_GET(request)
            self.fail("This should throw an error.")
        except:
            self.assertIsNotNone(ledger.GlobalStore)
        kv = KeyValueStore()
        ledger.GlobalStore.TransactionStores["/TestTransaction"] = kv
        ledger.GlobalStore.TransactionStores["/TestTransaction"].set("TestKey",
                                                                     0)
        # GET /store
        self.assertEquals(root.render_GET(request), '["/TestTransaction"]')

        # GET /store/TestTransaction
        request = self._create_get_request("/store/TestTransaction", {})
        self.assertEquals(root.render_GET(request), '["TestKey"]')
        # GET /store/TestTransaction/*
        request = self._create_get_request("/store/TestTransaction/*", {})
        self.assertEquals(root.render_GET(request), '{"TestKey": 0}')
        # GET /store/TestTransaction/*?delta=1
        request = self._create_get_request("/store/TestTransaction/*",
                                           {"delta": ['1']})
        self.assertEquals(root.render_GET(request),
                          '{"DeletedKeys": [], "Store": {"TestKey": 0}}')
        # GET /store/TestTransaction/TestKey
        request = self._create_get_request("/store/TestTransaction/TestKey",
                                           {})
        self.assertEquals(root.render_GET(request), "0")

        try:
            blockstore = BlockStore()
            ledger.GlobalStoreMap.commit_block_store("123", blockstore)
            request = self._create_get_request("/store/TestTransaction/*",
                                               {"blockid": ["123"]})
            root.render_GET(request)
            self.fail("This should throw an error")
        except:
            blockstore = BlockStore()
            blockstore.add_transaction_store("/TestTransaction", kv)
            ledger.GlobalStoreMap.commit_block_store("123", blockstore)

        # GET /store/TestTransaction/*?blockid=123
        request = self._create_get_request("/store/TestTransaction/*",
                                           {"blockid": ["123"]})
        self.assertEquals(root.render_GET(request), '{"TestKey": 0}')

    def test_web_api_block(self):
        # Test _handleblkrequest
        LocalNode = self._create_node(8801)
        path = tempfile.mkdtemp()
        # Setup ledger and RootPage
        ledger = Journal(LocalNode, DataDirectory=path, GenesisLedger=True)
        validator = TestValidator(ledger)
        root = RootPage(validator)
        # TransactionBlock to the ledger
        transBlock = self._create_tblock(LocalNode, 0, common.NullIdentifier,
                                         [])
        transBlock2 = self._create_tblock(LocalNode, 1, transBlock.Identifier,
                                          [])
        ledger.BlockStore[transBlock.Identifier] = transBlock
        ledger.BlockStore[transBlock2.Identifier] = transBlock2
        ledger.handle_advance(transBlock)
        ledger.handle_advance(transBlock2)
        # GET /block
        request = self._create_get_request("/block", {})
        string = '["' + str(transBlock2.Identifier) + '", "' + \
            str(transBlock.Identifier) + '"]'
        self.assertEquals(root.render_GET(request), string)
        # GET /block?blockcount=2
        request = self._create_get_request("/block", {"blockcount": [2]})
        self.assertEquals(root.render_GET(request), string)
        # GET /block?blockcount=1
        string = '["' + str(transBlock2.Identifier) + '"]'
        request = self._create_get_request("/block", {"blockcount": [1]})
        self.assertEquals(root.render_GET(request), string)
        # Add identifier to dictionary
        dictB = transBlock.dump()
        dictB["Identifier"] = transBlock.Identifier
        # GET /block/{BlockId}
        request = self._create_get_request("/block/" + transBlock.Identifier,
                                           {})
        self.assertEquals(yaml.load(root.render_GET(request)), dictB)
        # GET /block/{BlockId}/Signature
        request = self._create_get_request("/block/" +
                                           transBlock.Identifier +
                                           "/Signature", {})
        self.assertEquals(root.render_GET(request), '"' +
                          transBlock.Signature + '"')

    def test_web_api_transaction(self):
        # Test _handletxnrequest
        LocalNode = self._create_node(8802)
        path = tempfile.mkdtemp()
        # Setup ledger and RootPage
        ledger = Journal(LocalNode, DataDirectory=path, GenesisLedger=True)
        validator = TestValidator(ledger)
        root = RootPage(validator)

        # TransactionBlock to the ledger
        txns = []
        i = 0
        while i < 10:
            txn = Transaction()
            txn.sign_from_node(LocalNode)
            txns += [txn.Identifier]
            ledger.TransactionStore[txn.Identifier] = txn
            i += 1
        transBlock = self._create_tblock(LocalNode, 0, common.NullIdentifier,
                                         txns)
        ledger.BlockStore[transBlock.Identifier] = transBlock
        ledger.handle_advance(transBlock)
        request = self._create_get_request("/transaction", {})
        # GET /transaction
        request = self._create_get_request("/transaction", {})
        r = root.render_GET(request)
        r = r[1:-1].replace('"', "")
        r = r.replace(" ", "").split(",")
        self.assertEquals(r, txns)
        # GET /transaction?blockcount=1
        request = self._create_get_request("/transaction", {"blockcount": [1]})
        r = root.render_GET(request)
        r = r[1:-1].replace('"', "")
        r = r.replace(" ", "").split(",")
        self.assertEquals(r, txns)
        # Returns None if testing
        # GET /transaction/{TransactionID}
        request = self._create_get_request("/transaction/" + txns[1], {})
        txn = ledger.TransactionStore[txns[1]]
        tinfo = txn.dump()
        tinfo['Identifier'] = txn.Identifier
        tinfo['Status'] = txn.Status
        if txn.Status == tStatus.committed:
            tinfo['InBlock'] = txn.InBlock
        self.assertEquals(yaml.load(root.render_GET(request)), tinfo)
        # GET /transaction/{TransactionID{}/InBlock
        request = self._create_get_request("/transaction/" + txns[1] +
                                           "/InBlock", {})
        self.assertEquals(root.render_GET(request).replace('"', ""),
                          txn.InBlock)

    def test_web_api_stats(self):
        # Test _handlestatrequest
        LocalNode = self._create_node(8803)
        path = tempfile.mkdtemp()
        # Setup ledger and RootPage
        ledger = Journal(LocalNode, DataDirectory=path, GenesisLedger=True)
        validator = TestValidator(ledger)
        root = RootPage(validator)
        request = self._create_get_request("/stat", {})
        try:
            root.render_GET(request)
            self.fail("This should cause an error")
        except:
            self.assertIsNotNone(root)

        dic = {}
        dic["ledger"] = ledger.StatDomains["ledger"].get_stats()
        dic["ledgerconfig"] = ledger.StatDomains["ledgerconfig"].get_stats()
        dic["message"] = ledger.StatDomains["message"].get_stats()
        dic["packet"] = ledger.StatDomains["packet"].get_stats()
        # GET /statistics/ledger
        request = self._create_get_request("/statistics/ledger", {})
        self.assertEquals(yaml.load(root.render_GET(request)), dic)
        # GET /statistics/node - with no peers
        request = self._create_get_request("/statistics/node", {})
        self.assertEquals(yaml.load(root.render_GET(request)), {})
        node = self._create_node(8804)
        ledger.add_node(node)
        dic2 = {}
        dic2[node.Name] = node.Stats.get_stats()
        dic2[node.Name]["IsPeer"] = node.is_peer
        # GET /stats/node - with one peer
        self.assertEquals(yaml.load(root.render_GET(request)), dic2)

        request = self._create_get_request("AnythingElse", {})
        dic3 = root.render_GET(request)
        self.assertEquals(dic3, 'unknown request AnythingElse\n')
