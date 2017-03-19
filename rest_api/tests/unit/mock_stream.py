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

from sawtooth_sdk.protobuf.validator_pb2 import Message
from sawtooth_rest_api.protobuf import client_pb2 as client
from sawtooth_rest_api.protobuf.block_pb2 import Block
from sawtooth_rest_api.protobuf.block_pb2 import BlockHeader
from sawtooth_rest_api.protobuf.batch_pb2 import Batch
from sawtooth_rest_api.protobuf.batch_pb2 import BatchHeader
from sawtooth_rest_api.protobuf.transaction_pb2 import Transaction
from sawtooth_rest_api.protobuf.transaction_pb2 import TransactionHeader


class _MockFuture(object):
    class Response(object):
        def __init__(self, content):
            self.content = content

    def __init__(self, response_content):
        self._response = self.Response(response_content)

    def result(self, timeout):
        return self._response


class MockStream(object):
    """Replace a route handler's stream with an instance of this class to
    intercept attempts to send requests, and send back custom responses.
    """
    def __init__(self):
        self._handlers = {}
        self._add_handler(Message.CLIENT_BATCH_SUBMIT_REQUEST, _SubmitHandler)
        self._add_handler(Message.CLIENT_BATCH_STATUS_REQUEST, _StatusHandler)
        self._add_handler(Message.CLIENT_STATE_LIST_REQUEST, _StateListHandler)
        self._add_handler(Message.CLIENT_STATE_GET_REQUEST, _StateGetHandler)
        self._add_handler(Message.CLIENT_BLOCK_LIST_REQUEST, _BlockListHandler)
        self._add_handler(Message.CLIENT_BLOCK_GET_REQUEST, _BlockGetHandler)
        self._add_handler(Message.CLIENT_BATCH_LIST_REQUEST, _BatchListHandler)
        self._add_handler(Message.CLIENT_BATCH_GET_REQUEST, _BatchGetHandler)

    def send(self, message_type, content):
        if not self._handlers[message_type]:
            raise NotImplementedError(
                'No handler for type {}'.format(message_type))
        response = self._handlers[message_type].handle(content)
        return _MockFuture(response.SerializeToString())

    def _add_handler(self, message_type, handler_class):
        self._handlers[message_type] = handler_class()


class _MockBlockStore(object):
    """A wrapper for a mock block store.
    Access data with the get_blocks and get_block methods.

    By default, it creates a store that looks like this:
        chain_head_id: '2',
        '2': {
            header: {previous_block_id: '1', ...},
            header_signature: '2',
            batches: [{
                header: {signer_pubkey: 'pubkey', ...},
                header_signature: '2',
                transactions: [{
                    header: {nonce: '2', ...},
                    header_signature: '2',
                    payload: b'payload'
                }]
            }]
        },
        '1': {header: {...}, header_signature: '1', batches: [{...}]},
        '0': {header: {...}, header_signature: '0', batches: [{...}]}
    """
    def __init__(self, size=3):
        self._store = {}
        self._chain_head_id = 'zzzzz'
        for i in range(size):
            self.add_block(str(i))

    def add_block(self, block_id, root='merkle_root'):
        txn_header = TransactionHeader(
            batcher_pubkey='pubkey',
            family_name='family',
            family_version='0.0',
            nonce=block_id,
            signer_pubkey='pubkey')

        txn = Transaction(
            header=txn_header.SerializeToString(),
            header_signature=block_id,
            payload=b'payload')

        batch_header = BatchHeader(
            signer_pubkey='pubkey',
            transaction_ids=[txn.header_signature])

        batch = Batch(
            header=batch_header.SerializeToString(),
            header_signature=block_id,
            transactions=[txn])

        blk_header = BlockHeader(
            block_num=len(self._store),
            previous_block_id=self._chain_head_id,
            signer_pubkey='pubkey',
            batch_ids=[batch.header_signature],
            consensus=b'consensus',
            state_root_hash=root)

        block = Block(
            header=blk_header.SerializeToString(),
            header_signature=block_id,
            batches=[batch])

        self._store[block_id] = block
        self._chain_head_id = block_id

    def get_blocks(self, head_id=None):
        blocks = []
        current_id = head_id or self._chain_head_id
        while current_id in self._store:
            blocks.append(self._store[current_id])
            header = BlockHeader()
            header.ParseFromString(blocks[-1].header)
            current_id = header.previous_block_id
        return blocks

    def get_block(self, block_id):
        return self._store.get(block_id, None)


class _MockState(object):
    """A wrapper for simplified state data.

    By default, it creates a dict of state contexts that look like this:
        '0': {'a': b'1'},
        '1': {'a': b'2', 'b': b'4'},
        '2': {'a': b'3', 'b': b'5', 'c': b'7'}
    """
    def __init__(self, size=3, start='a'):
        self._state = {}
        start_ord = ord(start)

        for i in range(size):
            if self._state:
                self._state[str(i)] = self._state[str(i - 1)].copy()
            else:
                self._state[str(i)] = {}

            data = self._state[str(i)]
            data[chr(start_ord + i)] = str(i * size).encode()
            for k, v in data.items():
                data[k] = str(int(v) + 1).encode()

    def get_leaves(self, address=None, head=None):
        """Fetches state data as a list of leaves, as well as
        determining the head id as needed
        """
        if not head:
            head = str(len(self._state) - 1)
        if not address:
            address = ''

        try:
            state = self._state[head]
        except KeyError:
            return head, None

        return head, [client.Leaf(address=k, data=v)
            for k, v in state.items()
            if k.startswith(address)]

    def get_leaf(self, address, head=None):
        """Fetches state data for a particular address, as well as
        determining the head id as needed
        """
        if not head:
            head = str(len(self._state) - 1)

        try:
            state = self._state[head]
        except KeyError:
            return head, None

        try:
            value = state[address]
        except KeyError:
            return head, ''

        return head, value


class _MockHandler(object):
    """Parent class for any mock validator handlers. Children should call
    super().__init__ as part of their own __init__.
    """
    def __init__(self, request_proto, response_proto, response_type):
        self._request_proto = request_proto
        self._response_proto = response_proto
        self.response_type = response_type

    def handle(self):
        raise NotImplementedError('Handler needs handle method')

    def _parse_request(self, content):
        request = self._request_proto()
        request.ParseFromString(content)
        return request


class _SubmitHandler(_MockHandler):
    def __init__(self):
        super().__init__(
            client.ClientBatchSubmitRequest,
            client.ClientBatchSubmitResponse,
            Message.CLIENT_BATCH_SUBMIT_RESPONSE)

    def handle(self, content):
        request = self._parse_request(content)

        # A batch id of 'bad' will trigger an invalid batch response
        for batch in request.batches:
            if batch.header_signature == 'bad':
                return self._response_proto(
                    status=self._response_proto.INVALID_BATCH)

        # simulate having waited for a batches to be committed
        if request.wait_for_commit == True and request.timeout > 0:
            statuses = {}
            for batch in request.batches:
                key = batch.header_signature
                if key == 'pending':
                    statuses[key] = self._response_proto.PENDING
                else:
                    statuses[key] = self._response_proto.COMMITTED

            return self._response_proto(
                status=self._response_proto.OK,
                batch_statuses=statuses)

        return self._response_proto(status=self._response_proto.OK)


class _StatusHandler(_MockHandler):
    def __init__(self):
        super().__init__(
            client.ClientBatchStatusRequest,
            client.ClientBatchStatusResponse,
            Message.CLIENT_BATCH_STATUS_RESPONSE)

    def handle(self, content):
        mock = {
            'committed': self._response_proto.COMMITTED,
            'pending': self._response_proto.PENDING}

        request = self._parse_request(content)

        # simulate having waited for a pending batch to be committed
        if request.wait_for_commit == True and request.timeout > 0:
            mock['pending'] = self._response_proto.COMMITTED

        statuses = {
            b_id: mock[b_id] if b_id in mock else self._response_proto.UNKNOWN
            for b_id in request.batch_ids}

        if not statuses:
            return self._response_proto(
                status=self._response_proto.NO_RESOURCE)

        return self._response_proto(
            status=self._response_proto.OK,
            batch_statuses=statuses)


class _StateListHandler(_MockHandler):
    def __init__(self):
        super().__init__(
            client.ClientStateListRequest,
            client.ClientStateListResponse,
            Message.CLIENT_STATE_LIST_RESPONSE)

    def handle(self, content):
        request = self._parse_request(content)
        state = _MockState()

        head_id, leaves = state.get_leaves(request.address, request.head_id)
        if leaves == None:
            return self._response_proto(status=self._response_proto.NO_ROOT)
        if leaves == []:
            return self._response_proto(
                status=self._response_proto.NO_RESOURCE,
                head_id=head_id)

        return self._response_proto(
            status=self._response_proto.OK,
            head_id=head_id,
            leaves=leaves)


class _StateGetHandler(_MockHandler):
    def __init__(self):
        super().__init__(
            client.ClientStateGetRequest,
            client.ClientStateGetResponse,
            Message.CLIENT_STATE_GET_RESPONSE)

    def handle(self, content):
        request = self._parse_request(content)
        state = _MockState()

        head_id, value = state.get_leaf(request.address, request.head_id)
        if value == None:
            return self._response_proto(status=self._response_proto.NO_ROOT)
        if value == '':
            return self._response_proto(
                status=self._response_proto.NO_RESOURCE,
                head_id=head_id)

        return self._response_proto(
            status=self._response_proto.OK,
            head_id=head_id,
            value=value)


class _BlockListHandler(_MockHandler):
    def __init__(self):
        super().__init__(
            client.ClientBlockListRequest,
            client.ClientBlockListResponse,
            Message.CLIENT_BLOCK_LIST_RESPONSE)

    def handle(self, content):
        request = self._parse_request(content)
        store = _MockBlockStore()

        blocks = store.get_blocks(request.head_id)
        if not blocks:
            return self._response_proto(status=self._response_proto.NO_ROOT)
        head_id=blocks[0].header_signature

        if request.block_ids:
            matches = {b.header_signature: b for b in blocks
                if b.header_signature in request.block_ids}
            blocks = [matches[i] for i in request.block_ids if i in matches]
            if not blocks:
                self._response_proto(status=self._response_proto.NO_RESOURCE)


        return self._response_proto(
            status=self._response_proto.OK,
            head_id=head_id,
            blocks=blocks)


class _BlockGetHandler(_MockHandler):
    def __init__(self):
        super().__init__(
            client.ClientBlockGetRequest,
            client.ClientBlockGetResponse,
            Message.CLIENT_BLOCK_GET_RESPONSE)

    def handle(self, content):
        request = self._parse_request(content)
        store = _MockBlockStore()

        if request.block_id == 'bad':
            return self._response_proto(
                status=self._response_proto.INVALID_ID)

        block = store.get_block(request.block_id)
        if not block:
            return self._response_proto(
                status=self._response_proto.NO_RESOURCE)

        return self._response_proto(
            status=self._response_proto.OK,
            block=block)


class _BatchListHandler(_MockHandler):
    def __init__(self):
        super().__init__(
            client.ClientBatchListRequest,
            client.ClientBatchListResponse,
            Message.CLIENT_BATCH_LIST_RESPONSE)

    def handle(self, content):
        request = self._parse_request(content)
        store = _MockBlockStore()

        blocks = store.get_blocks(request.head_id)
        batches = [a for b in blocks for a in b.batches]
        if not batches:
            return self._response_proto(status=self._response_proto.NO_ROOT)
        head_id = blocks[0].header_signature

        if request.batch_ids:
            matches = {b.header_signature: b for b in batches
                if b.header_signature in request.batch_ids}
            batches = [matches[i] for i in request.batch_ids if i in matches]
            if not batches:
                self._response_proto(status=self._response_proto.NO_RESOURCE)

        return self._response_proto(
            status=self._response_proto.OK,
            head_id=head_id,
            batches=batches)


class _BatchGetHandler(_MockHandler):
    def __init__(self):
        super().__init__(
            client.ClientBatchGetRequest,
            client.ClientBatchGetResponse,
            Message.CLIENT_BATCH_GET_RESPONSE)

    def handle(self, content):
        request = self._parse_request(content)
        store = _MockBlockStore()

        if request.batch_id == 'bad':
            return self._response_proto(
                status=self._response_proto.INVALID_ID)

        block = store.get_block(request.batch_id)

        if not block:
            return self._response_proto(
                status=self._response_proto.NO_RESOURCE)

        return self._response_proto(
            status=self._response_proto.OK,
            batch=block.batches[0])
