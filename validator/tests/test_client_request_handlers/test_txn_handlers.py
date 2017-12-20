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

import sawtooth_validator.state.client_handlers as handlers
from sawtooth_validator.protobuf import client_transaction_pb2
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from test_client_request_handlers.base_case import ClientHandlerTestCase
from test_client_request_handlers.mocks import MockBlockStore


B_0 = 'b' * 127 + '0'
B_1 = 'b' * 127 + '1'
B_2 = 'b' * 127 + '2'
C_0 = 'c' * 127 + '0'
C_1 = 'c' * 127 + '1'
C_2 = 'c' * 127 + '2'


class TestTransactionListRequests(ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.TransactionListRequest(store),
            client_transaction_pb2.ClientTransactionListRequest,
            client_transaction_pb2.ClientTransactionListResponse,
            store=store)

    def test_txn_list_request(self):
        """Verifies requests for txn lists without parameters work properly.

        Queries the default mock block store with three blocks:
            {
                header_signature: 'bbb...2',
                batches: [{
                    header_signature: 'aaa...2',
                    transactions: [{
                        header_signature: 'ccc...2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'bbb...1', ...},
            {header_signature: 'bbb...0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - a paging response with start of C_2 and limit 100
            - a list of transactions with 3 items
            - those items are instances of Transaction
            - the first item has a header_signature of 'ccc...2'
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, C_2, 100)
        self.assertEqual(3, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual(C_2, response.transactions[0].header_signature)

    def test_txn_list_bad_protobufs(self):
        """Verifies requests for txn lists break with bad protobufs.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that head_id, paging, and transactions are missing
        """
        response = self.make_bad_request(head_id=B_1)

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.transactions)

    def test_txn_list_no_genesis(self):
        """Verifies requests for txn lists break with no genesis.

        Expects to find:
            - a status of NOT_READY
            - that head_id, paging, and transactions are missing
        """
        self.break_genesis()
        response = self.make_request()

        self.assertEqual(self.status.NOT_READY, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.transactions)

    def test_txn_list_with_head(self):
        """Verifies requests for txn lists work properly with a head id.

        Queries the default mock block store with 'bbb...1' as the head:
            {
                header_signature: 'bbb...1',
                batches: [{
                    header_signature: 'aaa...1',
                    transactions: [{
                        header_signature: 'ccc...1',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'bbb...0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...1'
            - a paging response with start of C_1 and limit 100
            - a list of transactions with 2 items
            - those items are instances of Transaction
            - the first item has a header_signature of 'ccc...1'
        """
        response = self.make_request(head_id=B_1)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_1, response.head_id)
        self.assert_valid_paging(response, C_1, 100)
        self.assertEqual(2, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual(C_1, response.transactions[0].header_signature)

    def test_txn_list_with_bad_head(self):
        """Verifies requests for txn lists break with a bad head.

        Expects to find:
            - a status of NO_ROOT
            - that head_id, paging, and transactions are missing
        """
        response = self.make_request(head_id='f' * 128)

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.transactions)

    def test_txn_list_filtered_by_ids(self):
        """Verifies requests for txn lists work filtered by txn ids.

        Queries the default mock block store with three blocks:
            {
                header_signature: 'bbb...2',
                batches: [{
                    header_signature: 'aaa...2',
                    transactions: [{
                        header_signature: 'ccc...2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'bbb...1', ...},
            {header_signature: 'bbb...0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - a paging response with start of C_0 and limit 100
            - a list of transactions with 2 items
            - the items are instances of Transaction
            - the first item has a header_signature of 'ccc...0'
            - the second item has a header_signature of 'ccc...2'
        """
        response = self.make_request(transaction_ids=[C_0, C_2])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, C_0, 100)
        self.assertEqual(2, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual(C_0, response.transactions[0].header_signature)
        self.assertEqual(C_2, response.transactions[1].header_signature)

    def test_txn_list_by_missing_ids(self):
        """Verifies txn list requests break properly when ids are not found.

        Queries the default mock block store with three blocks:
            {
                header_signature: 'bbb...2',
                batches: [{
                    header_signature: 'aaa...2',
                    transactions: [{
                        header_signature: 'ccc...2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'bbb...1', ...},
            {header_signature: 'bbb...0', ...}

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'bbb...2', the latest
            - that paging and transactions are missing
        """
        response = self.make_request(transaction_ids=['f' * 128, 'e' * 128])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.transactions)

    def test_txn_list_by_found_and_missing_ids(self):
        """Verifies txn list requests work filtered by good and bad ids.

        Queries the default mock block store with three blocks:
            {
                header_signature: 'bbb...2',
                batches: [{
                    header_signature: 'aaa...2',
                    transactions: [{
                        header_signature: 'ccc...2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'bbb...1', ...},
            {header_signature: 'bbb...0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
        - a paging response with start of C_1 and limit 100
            - a list of transactions with 1 items
            - that item is an instances of Transaction
            - that item has a header_signature of 'ccc...1'
        """
        response = self.make_request(transaction_ids=['f' * 128, C_1])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, C_1, 100)
        self.assertEqual(1, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual(C_1, response.transactions[0].header_signature)

    def test_txn_list_by_invalid_ids(self):
        """Verifies txn list requests break when invalid ids are sent.

        Expects to find:
            - a status of INVALID_ID
            - that paging and transactions are missing
        """
        response = self.make_request(transaction_ids=['not', 'valid'])

        self.assertEqual(self.status.INVALID_ID, response.status)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.transactions)

    def test_txn_list_by_head_and_ids(self):
        """Verifies txn list requests work with both head and txn ids.

        Queries the default mock block store with 'bbb...1' as the head:
            {
                header_signature: 'bbb...1',
                batches: [{
                    header_signature: 'aaa...1',
                    transactions: [{
                        header_signature: 'ccc...1',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'bbb...0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...1'
            - a paging response with a start of C_0 and limit 100
            - a list of transactions with 1 item
            - that item is an instance of Transaction
            - that item has a header_signature of 'ccc...0'
        """
        response = self.make_request(head_id=B_1, transaction_ids=[C_0])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_1, response.head_id)
        self.assert_valid_paging(response, C_0, 100)
        self.assertEqual(1, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual(C_0, response.transactions[0].header_signature)

    def test_txn_list_head_ids_mismatch(self):
        """Verifies txn list requests break when ids not found with head.

        Queries the default mock block store with 'bbb...0' as the head:
            {
                header_signature: 'bbb...0',
                batches: [{
                    header_signature: 'aaa...0',
                    transactions: [{
                        header_signature: 'ccc...0',
                        ...
                    }],
                    ...
                }],
                ...
            }

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'bbb...0'
            - that paging and transactions are missing
        """
        response = self.make_request(head_id=B_0, transaction_ids=[C_1, C_2])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual(B_0, response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.transactions)

    def test_txn_list_paginated(self):
        """Verifies requests for txn lists work when paginated just by limit.

        Queries the default mock block store:
            {
                header_signature: 'bbb...2',
                batches: [{
                    header_signature: 'aaa...2',
                    transactions: [{
                        header_signature: 'ccc...2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'bbb...1', ...},
            {header_signature: 'bbb...0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - a paging response with:
                * a next_id of C_0
                * the default start of C_2
                * limit of 2
            - a list of transactions with 2 items
            - those items are instances of Transaction
            - the first item has a header_signature of 'ccc...2'
        """
        response = self.make_paged_request(limit=2)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, C_2, 2, next_id=C_0)
        self.assertEqual(2, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual(C_2, response.transactions[0].header_signature)

    def test_txn_list_paginated_by_start_id(self):
        """Verifies txn list requests work paginated by limit and start_id.

        Queries the default mock block store:
            {
                header_signature: 'bbb...2',
                batches: [{
                    header_signature: 'aaa...2',
                    transactions: [{
                        header_signature: 'ccc...2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'bbb...1', ...},
            {header_signature: 'bbb...0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - a paging response with:
                * a next_id of C_0
                * a start of C_1
                * limit of 1
            - a list of transactions with 1 item
            - that item is an instance of Transaction
            - that item has a header_signature of 'ccc...1'
        """
        response = self.make_paged_request(limit=1, start=C_1)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, C_1, 1, C_0)
        self.assertEqual(1, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual(C_1, response.transactions[0].header_signature)

    def test_txn_list_paginated_by_index(self):
        """Verifies txn list requests work paginated by limit and min_index.

        Queries the default mock block store:
            {
                header_signature: 'bbb...2',
                batches: [{
                    header_signature: 'aaa...2',
                    transactions: [{
                        header_signature: 'ccc...2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'bbb...1', ...},
            {header_signature: 'bbb...0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - a paging response with a next of C_1, start of C_2 and limit of 1
            - a list of transactions with 1 item
            - that item is an instance of Transaction
            - that item has a header_signature of 'ccc...2'
        """
        response = self.make_paged_request(limit=1, start=C_2)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, C_2, 1, C_1)
        self.assertEqual(1, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual(C_2, response.transactions[0].header_signature)

    def test_txn_list_with_bad_pagination(self):
        """Verifies txn requests break when paging specifies missing txns.

        Queries the default mock block store:
            {
                header_signature: 'bbb...2',
                batches: [{
                    header_signature: 'aaa...2',
                    transactions: [{
                        header_signature: 'ccc...2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'bbb...1', ...},
            {header_signature: 'bbb...0', ...}

        Expects to find:
            - a status of INVALID_PAGING
            - that head_id, paging, and transactions are missing
        """
        response = self.make_paged_request(limit=3, start='f' * 128)

        self.assertEqual(self.status.INVALID_PAGING, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.transactions)

    def test_txn_list_paginated_with_head(self):
        """Verifies txn list requests work with both paging and a head id.

        Queries the default mock block store with 'bbb...1' as the head:
            {header_signature: 'bbb...1', ...},
            {header_signature: 'bbb...0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...1'
            - a paging response with:
                * a start of C_0
                * limit of 1
            - a list of transactions with 1 item
            - that item is an instance of Transaction
            - that has a header_signature of 'ccc...0'
        """
        response = self.make_paged_request(limit=1, start=C_0, head_id=B_1)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_1, response.head_id)
        self.assert_valid_paging(response, C_0, 1)
        self.assertEqual(1, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual(C_0, response.transactions[0].header_signature)

    def test_txn_list_sorted_in_reverse(self):
        """Verifies txn list requests work sorted by a key in reverse.

        Queries the default mock block store:
            {
                header_signature: 'bbb...2',
                batches: [{
                    header_signature: 'aaa...2',
                    transactions: [{
                        header_signature: 'ccc...2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'bbb...1', ...},
            {header_signature: 'bbb...0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2', the latest
            - a paging response start of C_0 and limit of 100
            - a list of transactions with 3 items
            - the items are instances of Transaction
            - the first item has a header_signature of 'ccc...0'
            - the last item has a header_signature of 'ccc...2'
        """
        controls = self.make_sort_controls('default', reverse=True)
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(B_2, response.head_id)
        self.assert_valid_paging(response, C_0, 100)
        self.assertEqual(3, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual(C_0, response.transactions[0].header_signature)
        self.assertEqual(C_2, response.transactions[2].header_signature)


class TestTransactionGetRequests(ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.TransactionGetRequest(store),
            client_transaction_pb2.ClientTransactionGetRequest,
            client_transaction_pb2.ClientTransactionGetResponse)

    def test_txn_get_request(self):
        """Verifies requests for a specific txn by id work properly.

        Queries the default three block mock store for a txn id of 'ccc...1'

        Expects to find:
            - a status of OK
            - a transaction property which is an instances of Transaction
            - the transaction has a header_signature of 'ccc...1'
        """
        response = self.make_request(transaction_id=C_1)

        self.assertEqual(self.status.OK, response.status)
        self.assertIsInstance(response.transaction, Transaction)
        self.assertEqual(C_1, response.transaction.header_signature)

    def test_txn_get_bad_request(self):
        """Verifies requests for a specific txn break with a bad protobuf.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that the Transaction returned, when serialized, is actually empty
        """
        response = self.make_bad_request(transaction_id=C_1)

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.transaction.SerializeToString())

    def test_txn_get_with_missing_id(self):
        """Verifies requests for a specific txn break with an unfound id.

        Expects to find:
            - a status of NO_RESOURCE
            - that the Transaction returned, when serialized, is actually empty
        """
        response = self.make_request(transaction_id='f' * 128)

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.transaction.SerializeToString())

    def test_txn_get_with_invalid_id(self):
        """Verifies requests for a specific txn break with an invalid id.

        Expects to find:
            - a status of INVALID_ID
            - that the Transaction returned, when serialized, is actually empty
        """
        response = self.make_request(transaction_id='invalid')

        self.assertEqual(self.status.INVALID_ID, response.status)
        self.assertFalse(response.transaction.SerializeToString())

    def test_txn_get_with_block_id(self):
        """Verifies requests for a specific txn break properly with a block id.

        Expects to find:
            - a status of NO_RESOURCE
            - that the Transaction returned, when serialized, is actually empty
        """
        response = self.make_request(transaction_id=B_1)

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.transaction.SerializeToString())
