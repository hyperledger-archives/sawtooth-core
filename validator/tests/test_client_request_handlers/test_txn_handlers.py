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
from sawtooth_validator.protobuf import client_pb2
from sawtooth_validator.protobuf.transaction_pb2 import Transaction
from test_client_request_handlers.base_case import ClientHandlerTestCase
from test_client_request_handlers.mocks import MockBlockStore


class TestTransactionListRequests(ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.TransactionListRequest(store),
            client_pb2.ClientTransactionListRequest,
            client_pb2.ClientTransactionListResponse,
            store=store)

    def test_txn_list_request(self):
        """Verifies requests for txn lists without parameters work properly.

        Queries the default mock block store with three blocks:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - the default paging response, showing all 3 resources returned
            - a list of transactions with 3 items
            - those items are instances of Transaction
            - the first item has a header_signature of 't-2'
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-2', response.transactions[0].header_signature)

    def test_txn_list_bad_request(self):
        """Verifies requests for txn lists break with bad protobufs.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that head_id, paging, and transactions are missing
        """
        response = self.make_bad_request(head_id='B-1')

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.transactions)

    def test_txn_list_bad_request(self):
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

        Queries the default mock block store with 'B-1' as the head:
            {
                header_signature: 'B-1',
                batches: [{
                    header_signature: 'b-1',
                    transactions: [{
                        header_signature: 't-1',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-1'
            - a paging response showing all 2 resources returned
            - a list of transactions with 2 items
            - those items are instances of Transaction
            - the first item has a header_signature of 't-1'
        """
        response = self.make_request(head_id='B-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-1', response.head_id)
        self.assert_valid_paging(response, total=2)
        self.assertEqual(2, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-1', response.transactions[0].header_signature)

    def test_txn_list_with_bad_head(self):
        """Verifies requests for txn lists break with a bad head.

        Expects to find:
            - a status of NO_ROOT
            - that head_id, paging, and transactions are missing
        """
        response = self.make_request(head_id='bad')

        self.assertEqual(self.status.NO_ROOT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.transactions)

    def test_txn_list_filtered_by_ids(self):
        """Verifies requests for txn lists work filtered by txn ids.

        Queries the default mock block store with three blocks:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response showing all 2 resources returned
            - a list of transactions with 2 items
            - the items are instances of Transaction
            - the first item has a header_signature of 't-0'
            - the second item has a header_signature of 't-2'
        """
        response = self.make_request(transaction_ids=['t-0', 't-2'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, total=2)
        self.assertEqual(2, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-0', response.transactions[0].header_signature)
        self.assertEqual('t-2', response.transactions[1].header_signature)

    def test_txn_list_by_bad_ids(self):
        """Verifies txn list requests break properly when ids are not found.

        Queries the default mock block store with three blocks:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'B-2', the latest
            - that paging and transactions are missing
        """
        response = self.make_request(transaction_ids=['bad', 'notgood'])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.transactions)

    def test_txn_list_by_good_and_bad_ids(self):
        """Verifies txn list requests work filtered by good and bad ids.

        Queries the default mock block store with three blocks:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response showing all 1 resources returned
            - a list of transactions with 1 items
            - that item is an instances of Transaction
            - that item has a header_signature of 't-1'
        """
        response = self.make_request(transaction_ids=['bad', 't-1'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, total=1)
        self.assertEqual(1, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-1', response.transactions[0].header_signature)

    def test_txn_list_by_head_and_ids(self):
        """Verifies txn list requests work with both head and txn ids.

        Queries the default mock block store with 'B-1' as the head:
            {
                header_signature: 'B-1',
                batches: [{
                    header_signature: 'b-1',
                    transactions: [{
                        header_signature: 't-1',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-1'
            - a paging response showing all 1 resources returned
            - a list of transactions with 1 item
            - that item is an instance of Transaction
            - that item has a header_signature of 't-0'
        """
        response = self.make_request(head_id='B-1', transaction_ids=['t-0'])

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-1', response.head_id)
        self.assert_valid_paging(response, total=1)
        self.assertEqual(1, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-0', response.transactions[0].header_signature)

    def test_txn_list_head_ids_mismatch(self):
        """Verifies txn list requests break when ids not found with head.

        Queries the default mock block store with 'B-0' as the head:
            {
                header_signature: 'B-0',
                batches: [{
                    header_signature: 'b-0',
                    transactions: [{
                        header_signature: 't-0',
                        ...
                    }],
                    ...
                }],
                ...
            }

        Expects to find:
            - a status of NO_RESOURCE
            - a head_id of 'B-0'
            - that paging and transactions are missing
        """
        response = self.make_request(head_id='B-0', transaction_ids=['t-1', 't-2'])

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertEqual('B-0', response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.transactions)

    def test_txn_list_paginated(self):
        """Verifies requests for txn lists work when paginated just by count.

        Queries the default mock block store:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response with:
                * a next_id of 't-0'
                * the default empty previous_id
                * the default start_index of 0
                * the default total resource count of 3
            - a list of transactions with 2 items
            - those items are instances of Transaction
            - the first item has a header_signature of 't-2'
        """
        response = self.make_paged_request(count=2)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, next_id='t-0')
        self.assertEqual(2, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-2', response.transactions[0].header_signature)

    def test_txn_list_paginated_by_start_id (self):
        """Verifies txn list requests work paginated by count and start_id.

        Queries the default mock block store:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response with:
                * a next_id of 't-0'
                * a previous_id of 't-2'
                * a start_index of 1
                * the default total resource count of 3
            - a list of transactions with 1 item
            - that item is an instance of Transaction
            - that item has a header_signature of 't-1'
        """
        response = self.make_paged_request(count=1, start_id='t-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, 't-0', 't-2', 1)
        self.assertEqual(1, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-1', response.transactions[0].header_signature)

    def test_txn_list_paginated_by_end_id (self):
        """Verifies txn list requests work paginated by count and end_id.

        Queries the default mock block store:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response with:
                * the default empty next_id
                * a previous_id of 't-2'
                * a start_index of 1
                * the default total resource count of 3
            - a list of transactions with 2 items
            - those items are instances of Transaction
            - the first item has a header_signature of 't-1'
        """
        response = self.make_paged_request(count=2, end_id='t-0')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, previous_id='t-2', start_index=1)
        self.assertEqual(2, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-1', response.transactions[0].header_signature)

    def test_txn_list_paginated_by_index (self):
        """Verifies txn list requests work paginated by count and min_index.

        Queries the default mock block store:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response with a next_id of 't-1'
            - a list of transactions with 1 item
            - that item is an instance of Transaction
            - that item has a header_signature of 't-2'
        """
        response = self.make_paged_request(count=1, start_index=0)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response, next_id='t-1')
        self.assertEqual(1, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-2', response.transactions[0].header_signature)

    def test_txn_list_with_bad_pagination(self):
        """Verifies txn requests break when paging specifies missing txns.

        Queries the default mock block store:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of INVALID_PAGING
            - that head_id, paging, and transactions are missing
        """
        response = self.make_paged_request(count=3, start_id='bad')

        self.assertEqual(self.status.INVALID_PAGING, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.transactions)

    def test_txn_list_paginated_with_head (self):
        """Verifies txn list requests work with both paging and a head id.

        Queries the default mock block store with 'B-1' as the head:
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-1'
            - a paging response with:
                * an empty next_id
                * a previous_id of 't-1'
                * a start_index of 1
                * a total resource count of 2
            - a list of transactions with 1 item
            - that item is an instance of Transaction
            - that has a header_signature of 't-0'
        """
        response = self.make_paged_request(count=1, start_index=1, head_id='B-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-1', response.head_id)
        self.assert_valid_paging(response, '', 't-1', 1, 2)
        self.assertEqual(1, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-0', response.transactions[0].header_signature)

    def test_txn_list_sorted_by_key(self):
        """Verifies txn list requests work sorted by header_signature.

        Queries the default mock block store:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response showing all 3 resources returned
            - a list of transactions with 3 items
            - the items are instances of Transaction
            - the first item has a header_signature of 't-0'
            - the last item has a header_signature of 't-2'
        """
        controls = self.make_sort_controls('header_signature')
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-0', response.transactions[0].header_signature)
        self.assertEqual('t-2', response.transactions[2].header_signature)

    def test_txn_list_sorted_by_bad_key(self):
        """Verifies txn list requests break properly sorted by a bad key.

        Queries the default mock block store:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of INVALID_SORT
            - that head_id, paging, and transactions are missing
        """
        controls = self.make_sort_controls('bad')
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.INVALID_SORT, response.status)
        self.assertFalse(response.head_id)
        self.assertFalse(response.paging.SerializeToString())
        self.assertFalse(response.transactions)

    def test_txn_list_sorted_by_nested_key(self):
        """Verifies txn list requests work sorted by header.signer_public_key.

        Queries the default mock block store:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response showing all 3 resources returned
            - a list of transactions with 3 items
            - the items are instances of Transaction
            - the first item has a header_signature of 't-0'
            - the last item has a header_signature of 't-2'
        """
        controls = self.make_sort_controls('header', 'signer_public_key')
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-0', response.transactions[0].header_signature)
        self.assertEqual('t-2', response.transactions[2].header_signature)

    def test_txn_list_sorted_by_implied_header(self):
        """Verifies txn list requests work sorted by an implicit header key.

        Queries the default mock block store:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response showing all 3 resources returned
            - a list of transactions with 3 items
            - the items are instances of Transaction
            - the first item has a header_signature of 't-0'
            - the last item has a header_signature of 't-2'
        """
        controls = self.make_sort_controls('signer_public_key')
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-0', response.transactions[0].header_signature)
        self.assertEqual('t-2', response.transactions[2].header_signature)

    def test_txn_list_sorted_by_many_keys(self):
        """Verifies txn list requests work sorted by two keys.

        Queries the default mock block store:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response showing all 3 resources returned
            - a list of transactions with 3 items
            - the items are instances of Transaction
            - the first item has a header_signature of 't-0'
            - the last item has a header_signature of 't-2'
        """
        controls = (self.make_sort_controls('family_name') +
                    self.make_sort_controls('signer_public_key'))
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-0', response.transactions[0].header_signature)
        self.assertEqual('t-2', response.transactions[2].header_signature)

    def test_txn_list_sorted_in_reverse(self):
        """Verifies txn list requests work sorted by a key in reverse.

        Queries the default mock block store:
            {
                header_signature: 'B-2',
                batches: [{
                    header_signature: 'b-2',
                    transactions: [{
                        header_signature: 't-2',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-2', the latest
            - a paging response showing all 3 resources returned
            - a list of transactions with 3 items
            - the items are instances of Transaction
            - the first item has a header_signature of 't-0'
            - the last item has a header_signature of 't-2'
        """
        controls = self.make_sort_controls('header_signature', reverse=True)
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-2', response.head_id)
        self.assert_valid_paging(response)
        self.assertEqual(3, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-2', response.transactions[0].header_signature)
        self.assertEqual('t-0', response.transactions[2].header_signature)

    def test_txn_list_sorted_by_length(self):
        """Verifies txn list requests work sorted by a property's length.

        Queries the default mock block store with two added blocks:
            {
                header_signature: 'B-long',
                batches: [{
                    header_signature: 'b-long',
                    transactions: [{
                        header_signature: 't-long',
                        ...
                    }],
                    ...
                }],
                ...
            },
            {header_signature: 'B-longest', ...},
            {header_signature: 'B-2', ...},
            {header_signature: 'B-1', ...},
            {header_signature: 'B-0', ...}

        Expects to find:
            - a status of OK
            - a head_id of 'B-long', the latest
            - a paging response showing all 5 resources returned
            - a list of transactions with 5 items
            - the items are instances of Transaction
            - the second to last item has a header_signature of 't-long'
            - the last item has a header_signature of 't-longest'
        """
        self.add_blocks('longest', 'long')
        controls = self.make_sort_controls(
            'header_signature', compare_length=True)
        response = self.make_request(sorting=controls)

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual('B-long', response.head_id)
        self.assert_valid_paging(response, total=5)
        self.assertEqual(5, len(response.transactions))
        self.assert_all_instances(response.transactions, Transaction)
        self.assertEqual('t-long', response.transactions[3].header_signature)
        self.assertEqual('t-longest', response.transactions[4].header_signature)


class TestTransactionGetRequests(ClientHandlerTestCase):
    def setUp(self):
        store = MockBlockStore()
        self.initialize(
            handlers.TransactionGetRequest(store),
            client_pb2.ClientTransactionGetRequest,
            client_pb2.ClientTransactionGetResponse)

    def test_txn_get_request(self):
        """Verifies requests for a specific txn by id work properly.

        Queries the default three block mock store for a txn id of 't-1'

        Expects to find:
            - a status of OK
            - a transaction property which is an instances of Transaction
            - the transaction has a header_signature of 't-1'
        """
        response = self.make_request(transaction_id='t-1')

        self.assertEqual(self.status.OK, response.status)
        self.assertIsInstance(response.transaction, Transaction)
        self.assertEqual('t-1', response.transaction.header_signature)

    def test_txn_get_bad_request(self):
        """Verifies requests for a specific txn break with a bad protobuf.

        Expects to find:
            - a status of INTERNAL_ERROR
            - that the Transaction returned, when serialized, is actually empty
        """
        response = self.make_bad_request(transaction_id='t-1')

        self.assertEqual(self.status.INTERNAL_ERROR, response.status)
        self.assertFalse(response.transaction.SerializeToString())

    def test_txn_get_with_bad_id(self):
        """Verifies requests for a specific txn break with a bad id.

        Expects to find:
            - a status of NO_RESOURCE
            - that the Transaction returned, when serialized, is actually empty
        """
        response = self.make_request(transaction_id='bad')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.transaction.SerializeToString())

    def test_txn_get_with_block_id(self):
        """Verifies requests for a specific txn break properly with a block id.

        Expects to find:
            - a status of NO_RESOURCE
            - that the Transaction returned, when serialized, is actually empty
        """
        response = self.make_request(transaction_id='B-1')

        self.assertEqual(self.status.NO_RESOURCE, response.status)
        self.assertFalse(response.transaction.SerializeToString())
