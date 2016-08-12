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

from gossip import common
import gossip.signed_object as sign_obj
from gossip.node import Node
from gossip.messages import shutdown_message

from journal.global_store_manager import KeyValueStore, BlockStore
from journal.transaction_block import TransactionBlock, Status
from journal.transaction import Transaction
from journal.transaction import Status as tStatus
from journal.journal_core import Journal

from txnserver.web_pages.block_page import BasePage
from txnserver.web_pages.block_page import BlockPage
from txnserver.web_pages.forward_page import ForwardPage
from txnserver.web_pages.statistics_page import StatisticsPage
from txnserver.web_pages.store_page import StorePage
from txnserver.web_pages.transaction_page import TransactionPage


class TestValidator(object):
    def __init__(self, test_ledger):
        self.Ledger = test_ledger
        self.web_thread_pool = TestThreadPool()


class TestThreadPool(object):
    def __init__(self):
        pass

    def start(self):
        pass


class TestWebApi(unittest.TestCase):

    # Helper functions
    def _create_node(self, port):
        signingkey = sign_obj.generate_signing_key()
        ident = sign_obj.generate_identifier(signingkey)
        node = Node(identifier=ident, signingkey=signingkey,
                    address=("localhost", port))
        return node

    def _create_tblock(self, node, blocknum, prev_block, trans_id):
        minfo = {'__SIGNATURE__': 'Test', "BlockNum": blocknum,
                 "PreviousBlockID": prev_block, "TransactionIDs": trans_id}
        trans_block = TransactionBlock(minfo)
        trans_block.sign_from_node(node)
        trans_block.Status = Status.valid
        return trans_block

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
        local_node = self._create_node(8809)
        path = tempfile.mkdtemp()
        # Setup ledger and RootPage

        ledger = Journal(local_node, DataDirectory=path, GenesisLedger=True)
        validator = TestValidator(ledger)
        root = BasePage(validator)
        request = self._create_get_request("/stat", {})

        error = root.error_response(request, http.BAD_REQUEST,
                                    'error processing http request {0}',
                                    request.path)
        self.assertEquals(error, "error processing http request /stat\n")

    def test_web_api_forward(self):
        # Test _msgforward
        local_node = self._create_node(8807)
        path = tempfile.mkdtemp()
        ledger = Journal(local_node, DataDirectory=path, GenesisLedger=True)
        # Create peers for the message to be forwarded to
        node1 = self._create_node(8881)
        node2 = self._create_node(8882)
        node1.is_peer = True
        node2.is_peer = True
        ledger.add_node(node1)
        ledger.add_node(node2)
        validator = TestValidator(ledger)
        forward_page = ForwardPage(validator)
        # Create message to use and the data to forward
        msg = shutdown_message.ShutdownMessage()
        msg.sign_from_node(local_node)
        data = msg.dump()
        # Post /forward
        request = self._create_post_request("forward", data)
        r = yaml.load(forward_page.do_post(request))
        self.assertEquals(r, data)
        self.assertIn(msg.Identifier, node1.MessageQ.Messages)
        self.assertIn(msg.Identifier, node2.MessageQ.Messages)

    def test_web_api_store(self):
        # Test _handlestorerequest
        local_node = self._create_node(8800)
        path = tempfile.mkdtemp()
        ledger = Journal(local_node, DataDirectory=path, GenesisLedger=True)
        validator = TestValidator(ledger)
        store_page = StorePage(validator)
        request = self._create_get_request("/store", {})
        try:
            # Test no GlobalStore
            ledger.GlobalStore = None
            store_page.do_get(request)
            self.fail("This should throw an error.")
        except:
            self.assertIsNotNone(ledger.GlobalStore)
        kv = KeyValueStore()
        ledger.GlobalStore.TransactionStores["/TestTransaction"] = kv
        ledger.GlobalStore.TransactionStores["/TestTransaction"].set("TestKey",
                                                                     0)
        # GET /store
        self.assertEquals(store_page.do_get(request), '["/TestTransaction"]')

        # GET /store/TestTransaction
        request = self._create_get_request("/store/TestTransaction", {})
        self.assertEquals(store_page.do_get(request), '["TestKey"]')
        # GET /store/TestTransaction/*
        request = self._create_get_request("/store/TestTransaction/*", {})
        self.assertEquals(store_page.do_get(request), '{"TestKey": 0}')
        # GET /store/TestTransaction/*?delta=1
        request = self._create_get_request("/store/TestTransaction/*",
                                           {"delta": ['1']})
        self.assertEquals(store_page.do_get(request),
                          '{"DeletedKeys": [], "Store": {"TestKey": 0}}')
        # GET /store/TestTransaction/TestKey
        request = self._create_get_request("/store/TestTransaction/TestKey",
                                           {})
        self.assertEquals(store_page.do_get(request), "0")

        try:
            blockstore = BlockStore()
            ledger.GlobalStoreMap.commit_block_store("123", blockstore)
            request = self._create_get_request("/store/TestTransaction/*",
                                               {"blockid": ["123"]})
            store_page.do_get(request)
            self.fail("This should throw an error")
        except:
            blockstore = BlockStore()
            blockstore.add_transaction_store("/TestTransaction", kv)
            ledger.GlobalStoreMap.commit_block_store("123", blockstore)

        # GET /store/TestTransaction/*?blockid=123
        request = self._create_get_request("/store/TestTransaction/*",
                                           {"blockid": ["123"]})
        self.assertEquals(store_page.do_get(request), '{"TestKey": 0}')

    def test_web_api_block(self):
        # Test _handleblkrequest
        local_node = self._create_node(8801)
        path = tempfile.mkdtemp()
        # Setup ledger and RootPage
        ledger = Journal(local_node, DataDirectory=path, GenesisLedger=True)
        validator = TestValidator(ledger)
        block_page = BlockPage(validator)

        # TransactionBlock to the ledger
        trans_block = self._create_tblock(local_node, 0, common.NullIdentifier,
                                          [])
        trans_block2 = self._create_tblock(local_node, 1,
                                           trans_block.Identifier,
                                           [])
        ledger.BlockStore[trans_block.Identifier] = trans_block
        ledger.BlockStore[trans_block2.Identifier] = trans_block2
        ledger.handle_advance(trans_block)
        ledger.handle_advance(trans_block2)

        # GET /block
        request = self._create_get_request("/block", {})
        string = '["' + str(trans_block2.Identifier) + '", "' + \
            str(trans_block.Identifier) + '"]'
        self.assertEquals(block_page.do_get(request), string)
        # GET /block?blockcount=2
        request = self._create_get_request("/block", {"blockcount": [2]})
        self.assertEquals(block_page.do_get(request), string)
        # GET /block?blockcount=1
        string = '["' + str(trans_block2.Identifier) + '"]'
        request = self._create_get_request("/block", {"blockcount": [1]})
        self.assertEquals(block_page.do_get(request), string)
        # Add identifier to dictionary
        dict_b = trans_block.dump()
        dict_b["Identifier"] = trans_block.Identifier
        # GET /block/{BlockId}
        request = self._create_get_request("/block/" + trans_block.Identifier,
                                           {})
        self.assertEquals(yaml.load(block_page.do_get(request)), dict_b)
        # GET /block/{BlockId}/Signature
        request = self._create_get_request("/block/" +
                                           trans_block.Identifier +
                                           "/Signature", {})
        self.assertEquals(block_page.do_get(request), '"' +
                          trans_block.Signature + '"')

    def test_web_api_transaction(self):
        # Test _handletxnrequest
        local_node = self._create_node(8802)
        path = tempfile.mkdtemp()
        # Setup ledger and RootPage
        ledger = Journal(local_node, DataDirectory=path, GenesisLedger=True)
        validator = TestValidator(ledger)
        transaction_page = TransactionPage(validator)

        # TransactionBlock to the ledger
        txns = []
        i = 0
        while i < 10:
            txn = Transaction()
            txn.sign_from_node(local_node)
            txns += [txn.Identifier]
            ledger.TransactionStore[txn.Identifier] = txn
            i += 1
        trans_block = self._create_tblock(local_node, 0, common.NullIdentifier,
                                          txns)
        ledger.BlockStore[trans_block.Identifier] = trans_block
        ledger.handle_advance(trans_block)
        # GET /transaction
        request = self._create_get_request("/transaction/", {})
        r = transaction_page.do_get(request)
        print request.path, r
        r = r[1:-1].replace('"', "")
        r = r.replace(" ", "").split(",")
        self.assertEquals(r, txns)
        # GET /transaction?blockcount=1
        request = self._create_get_request("/transaction", {"blockcount": [1]})
        r = transaction_page.do_get(request)
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
        self.assertEquals(yaml.load(transaction_page.do_get(request)), tinfo)
        # GET /transaction/{TransactionID{}/InBlock
        request = self._create_get_request("/transaction/" + txns[1] +
                                           "/InBlock", {})
        self.assertEquals(transaction_page.do_get(request).replace('"', ""),
                          txn.InBlock)

    def test_web_api_stats(self):
        # Test _handlestatrequest
        local_node = self._create_node(8803)
        path = tempfile.mkdtemp()
        # Setup ledger and RootPage
        ledger = Journal(local_node, DataDirectory=path, GenesisLedger=True)
        validator = TestValidator(ledger)
        statistics_page = StatisticsPage(validator)
        request = self._create_get_request("/stat", {})
        try:
            statistics_page.do_get(request)
            self.fail("This should cause an error")
        except:
            self.assertIsNotNone(statistics_page)

        dic = {}
        dic["ledger"] = ledger.StatDomains["ledger"].get_stats()
        dic["ledgerconfig"] = ledger.StatDomains["ledgerconfig"].get_stats()
        dic["message"] = ledger.StatDomains["message"].get_stats()
        dic["packet"] = ledger.StatDomains["packet"].get_stats()
        # GET /statistics/ledger
        request = self._create_get_request("/statistics/ledger", {})
        self.assertEquals(yaml.load(statistics_page.do_get(request)), dic)
        # GET /statistics/node - with no peers
        request = self._create_get_request("/statistics/node", {})
        self.assertEquals(yaml.load(statistics_page.do_get(request)), {})
        node = self._create_node(8804)
        ledger.add_node(node)
        dic2 = {}
        dic2[node.Name] = node.Stats.get_stats()
        dic2[node.Name]["IsPeer"] = node.is_peer
        # GET /stats/node - with one peer
        self.assertEquals(yaml.load(statistics_page.do_get(request)), dic2)

        request = self._create_get_request("AnythingElse", {})
        dic3 = statistics_page.do_get(request)
        self.assertTrue('Invalid page name' in dic3)
