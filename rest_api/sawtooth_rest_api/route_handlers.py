# Copyright 2016, 2017 Intel Corporation
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

import re
import logging
import json
import base64
from concurrent.futures import ThreadPoolExecutor
from aiohttp import web

# pylint: disable=no-name-in-module,import-error
# needed for the google.protobuf imports to pass pylint
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError

from sawtooth_sdk.messaging.exceptions import ValidatorConnectionError
from sawtooth_sdk.messaging.future import FutureTimeoutError
from sawtooth_sdk.protobuf.validator_pb2 import Message

import sawtooth_rest_api.exceptions as errors
import sawtooth_rest_api.error_handlers as error_handlers
from sawtooth_rest_api.protobuf import client_pb2
from sawtooth_rest_api.protobuf.block_pb2 import BlockHeader
from sawtooth_rest_api.protobuf.batch_pb2 import BatchList
from sawtooth_rest_api.protobuf.batch_pb2 import BatchHeader
from sawtooth_rest_api.protobuf.transaction_pb2 import TransactionHeader


DEFAULT_TIMEOUT = 300
LOGGER = logging.getLogger(__name__)


class RouteHandler(object):
    """Contains a number of aiohttp handlers for endpoints in the Rest Api.

    Each handler takes an aiohttp Request object, and uses the data in
    that request to send Protobuf message to a validator. The Protobuf response
    is then parsed, and finally an aiohttp Response object is sent back
    to the client with JSON formatted data and metadata.

    If something goes wrong, an aiohttp HTTP exception is raised or returned
    instead.

    Args:
        stream (:obj: messaging.stream.Stream): The object that communicates
            with the validator.
        timeout (int, optional): The time in seconds before the Api should
            cancel a request and report that the validator is unavailable.
    """
    def __init__(self, loop, stream, timeout=DEFAULT_TIMEOUT):
        loop.set_default_executor(ThreadPoolExecutor())
        self._loop = loop
        self._stream = stream
        self._timeout = timeout

    async def submit_batches(self, request):
        """Accepts a binary encoded BatchList and submits it to the validator.

        Request:
            body: octet-stream BatchList of one or more Batches
            query:
                - wait: Request should not return until all batches committed

        Response:
            status:
                 - 200: Batches submitted, but wait timed out before committed
                 - 201: All batches submitted and committed
                 - 202: Batches submitted and pending (not told to wait)
            data: Status of uncommitted batches (if any, when told to wait)
            link: /batches or /batch_status link for submitted batches

        """
        # Parse request
        if request.headers['Content-Type'] != 'application/octet-stream':
            LOGGER.debug(
                'Submission headers had wrong Content-Type: %s',
                request.headers['Content-Type'])
            raise errors.SubmissionWrongContentType()

        body = await request.read()
        if not body:
            LOGGER.debug('Submission contained an empty body')
            raise errors.NoBatchesSubmitted()

        try:
            batch_list = BatchList()
            batch_list.ParseFromString(body)
        except DecodeError:
            LOGGER.debug('Submission body could not be decoded: %s', body)
            raise errors.BadProtobufSubmitted()

        # Query validator
        error_traps = [error_handlers.BatchInvalidTrap]
        validator_query = client_pb2.ClientBatchSubmitRequest(
            batches=batch_list.batches)
        self._set_wait(request, validator_query)

        response = await self._query_validator(
            Message.CLIENT_BATCH_SUBMIT_REQUEST,
            client_pb2.ClientBatchSubmitResponse,
            validator_query,
            error_traps)

        # Build response envelope
        data = self._format_statuses(response['batch_statuses']) or None
        id_string = ','.join(b.header_signature for b in batch_list.batches)

        if data is None or any(d['status'] != 'COMMITTED' for d in data):
            status = 202
            link = self._build_url(request, path='/batch_status', id=id_string)
        else:
            status = 201
            data = None
            link = self._build_url(request, wait=False, id=id_string)

        return self._wrap_response(
            request,
            data=data,
            metadata={'link': link},
            status=status)

    async def list_statuses(self, request):
        """Fetches the committed status of batches by either a POST or GET.

        Request:
            body: A JSON array of one or more id strings (if POST)
            query:
                - id: A comma separated list of up to 15 ids (if GET)
                - wait: Request should not return until all batches committed

        Response:
            data: A JSON object, with batch ids as keys, and statuses as values
            link: The /batch_status link queried (if GET)
        """
        error_traps = [error_handlers.StatusResponseMissing]

        # Parse batch ids from POST body, or query paramaters
        if request.method == 'POST':
            if request.headers['Content-Type'] != 'application/json':
                LOGGER.debug(
                    'Request headers had wrong Content-Type: %s',
                    request.headers['Content-Type'])
                raise errors.StatusWrongContentType()

            ids = await request.json()

            if (not ids
                    or not isinstance(ids, list)
                    or not all(isinstance(i, str) for i in ids)):
                LOGGER.debug('Request body was invalid: %s', ids)
                raise errors.StatusBodyInvalid()

        else:
            ids = self._get_filter_ids(request)
            if not ids:
                LOGGER.debug('Request for statuses missing id query')
                raise errors.StatusIdQueryInvalid()

        # Query validator
        validator_query = client_pb2.ClientBatchStatusRequest(batch_ids=ids)
        self._set_wait(request, validator_query)

        response = await self._query_validator(
            Message.CLIENT_BATCH_STATUS_REQUEST,
            client_pb2.ClientBatchStatusResponse,
            validator_query,
            error_traps)

        # Send response
        if request.method != 'POST':
            metadata = self._get_metadata(request, response)
        else:
            metadata = None

        return self._wrap_response(
            request,
            data=self._format_statuses(response['batch_statuses']),
            metadata=metadata)

    async def list_state(self, request):
        """Fetches list of data leaves, optionally filtered by address prefix.

        Request:
            query:
                - head: The id of the block to use as the head of the chain
                - address: Return leaves whose addresses begin with this prefix

        Response:
            data: An array of leaf objects with address and data keys
            head: The head used for this query (most recent if unspecified)
            link: The link to this exact query, including head block
            paging: Paging info and nav, like total resources and a next link
        """
        paging_controls = self._get_paging_controls(request)
        validator_query = client_pb2.ClientStateListRequest(
            head_id=request.url.query.get('head', None),
            address=request.url.query.get('address', None),
            sorting=self._get_sorting_message(request),
            paging=self._make_paging_message(paging_controls))

        response = await self._query_validator(
            Message.CLIENT_STATE_LIST_REQUEST,
            client_pb2.ClientStateListResponse,
            validator_query)

        return self._wrap_paginated_response(
            request=request,
            response=response,
            controls=paging_controls,
            data=response.get('leaves', []))

    async def fetch_state(self, request):
        """Fetches data from a specific address in the validator's state tree.

        Request:
            query:
                - head: The id of the block to use as the head of the chain
                - address: The 70 character address of the data to be fetched

        Response:
            data: The base64 encoded binary data stored at that address
            head: The head used for this query (most recent if unspecified)
            link: The link to this exact query, including head block
        """
        error_traps = [
            error_handlers.InvalidAddressTrap,
            error_handlers.StateNotFoundTrap]

        address = request.match_info.get('address', '')
        head = request.url.query.get('head', None)

        response = await self._query_validator(
            Message.CLIENT_STATE_GET_REQUEST,
            client_pb2.ClientStateGetResponse,
            client_pb2.ClientStateGetRequest(head_id=head, address=address),
            error_traps)

        return self._wrap_response(
            request,
            data=response['value'],
            metadata=self._get_metadata(request, response))

    async def list_blocks(self, request):
        """Fetches list of blocks from validator, optionally filtered by id.

        Request:
            query:
                - head: The id of the block to use as the head of the chain
                - id: Comma separated list of block ids to include in results

        Response:
            data: JSON array of fully expanded Block objects
            head: The head used for this query (most recent if unspecified)
            link: The link to this exact query, including head block
            paging: Paging info and nav, like total resources and a next link
        """
        paging_controls = self._get_paging_controls(request)
        validator_query = client_pb2.ClientBlockListRequest(
            head_id=request.url.query.get('head', None),
            block_ids=self._get_filter_ids(request),
            sorting=self._get_sorting_message(request),
            paging=self._make_paging_message(paging_controls))

        response = await self._query_validator(
            Message.CLIENT_BLOCK_LIST_REQUEST,
            client_pb2.ClientBlockListResponse,
            validator_query)

        return self._wrap_paginated_response(
            request=request,
            response=response,
            controls=paging_controls,
            data=[self._expand_block(b) for b in response['blocks']])

    async def fetch_block(self, request):
        """Fetches a specific block from the validator, specified by id.
        Request:
            path:
                - block_id: The 128-character id of the block to be fetched

        Response:
            data: A JSON object with the data from the fully expanded Block
            link: The link to this exact query
        """
        error_traps = [error_handlers.BlockNotFoundTrap]

        block_id = request.match_info.get('block_id', '')

        response = await self._query_validator(
            Message.CLIENT_BLOCK_GET_REQUEST,
            client_pb2.ClientBlockGetResponse,
            client_pb2.ClientBlockGetRequest(block_id=block_id),
            error_traps)

        return self._wrap_response(
            request,
            data=self._expand_block(response['block']),
            metadata=self._get_metadata(request, response))

    async def list_batches(self, request):
        """Fetches list of batches from validator, optionally filtered by id.

        Request:
            query:
                - head: The id of the block to use as the head of the chain
                - id: Comma separated list of batch ids to include in results

        Response:
            data: JSON array of fully expanded Batch objects
            head: The head used for this query (most recent if unspecified)
            link: The link to this exact query, including head block
            paging: Paging info and nav, like total resources and a next link
        """
        paging_controls = self._get_paging_controls(request)
        validator_query = client_pb2.ClientBatchListRequest(
            head_id=request.url.query.get('head', None),
            batch_ids=self._get_filter_ids(request),
            sorting=self._get_sorting_message(request),
            paging=self._make_paging_message(paging_controls))

        response = await self._query_validator(
            Message.CLIENT_BATCH_LIST_REQUEST,
            client_pb2.ClientBatchListResponse,
            validator_query)

        return self._wrap_paginated_response(
            request=request,
            response=response,
            controls=paging_controls,
            data=[self._expand_batch(b) for b in response['batches']])

    async def fetch_batch(self, request):
        """Fetches a specific batch from the validator, specified by id.

        Request:
            path:
                - batch_id: The 128-character id of the batch to be fetched

        Response:
            data: A JSON object with the data from the fully expanded Batch
            link: The link to this exact query
        """
        error_traps = [error_handlers.BatchNotFoundTrap]

        batch_id = request.match_info.get('batch_id', '')

        response = await self._query_validator(
            Message.CLIENT_BATCH_GET_REQUEST,
            client_pb2.ClientBatchGetResponse,
            client_pb2.ClientBatchGetRequest(batch_id=batch_id),
            error_traps)

        return self._wrap_response(
            request,
            data=self._expand_batch(response['batch']),
            metadata=self._get_metadata(request, response))

    async def list_transactions(self, request):
        """Fetches list of txns from validator, optionally filtered by id.

        Request:
            query:
                - head: The id of the block to use as the head of the chain
                - id: Comma separated list of txn ids to include in results

        Response:
            data: JSON array of Transaction objects with expanded headers
            head: The head used for this query (most recent if unspecified)
            link: The link to this exact query, including head block
            paging: Paging info and nav, like total resources and a next link
        """
        paging_controls = self._get_paging_controls(request)
        validator_query = client_pb2.ClientTransactionListRequest(
            head_id=request.url.query.get('head', None),
            transaction_ids=self._get_filter_ids(request),
            sorting=self._get_sorting_message(request),
            paging=self._make_paging_message(paging_controls))

        response = await self._query_validator(
            Message.CLIENT_TRANSACTION_LIST_REQUEST,
            client_pb2.ClientTransactionListResponse,
            validator_query)

        data = [self._expand_transaction(t) for t in response['transactions']]

        return self._wrap_paginated_response(
            request=request,
            response=response,
            controls=paging_controls,
            data=data)

    async def fetch_transaction(self, request):
        """Fetches a specific transaction from the validator, specified by id.

        Request:
            path:
                - transaction_id: The 128-character id of the txn to be fetched

        Response:
            data: A JSON object with the data from the expanded Transaction
            link: The link to this exact query
        """
        error_traps = [error_handlers.TransactionNotFoundTrap]

        txn_id = request.match_info.get('transaction_id', '')

        response = await self._query_validator(
            Message.CLIENT_TRANSACTION_GET_REQUEST,
            client_pb2.ClientTransactionGetResponse,
            client_pb2.ClientTransactionGetRequest(transaction_id=txn_id),
            error_traps)

        return self._wrap_response(
            request,
            data=self._expand_transaction(response['transaction']),
            metadata=self._get_metadata(request, response))

    async def _query_validator(self, request_type, response_proto,
                               payload, error_traps=None):
        """Sends a request to the validator and parses the response.
        """
        LOGGER.debug(
            'Sending %s request to validator',
            self._get_type_name(request_type))

        payload_bytes = payload.SerializeToString()
        response = await self._send_request(request_type, payload_bytes)
        content = self._parse_response(response_proto, response)

        LOGGER.debug(
            'Received %s response from validator with status %s',
            self._get_type_name(response.message_type),
            self._get_status_name(response_proto, content.status))

        self._check_status_errors(response_proto, content, error_traps)
        return self._message_to_dict(content)

    async def _send_request(self, request_type, payload):
        """Uses an executor to send an asynchronous ZMQ request to the validator
        with the handler's Stream.
        """
        future = self._stream.send(message_type=request_type, content=payload)

        try:
            return await self._loop.run_in_executor(
                None, future.result, self._timeout)
        except FutureTimeoutError:
            LOGGER.warning('Timed out while waiting for validator response')
            raise errors.ValidatorTimedOut()

    @staticmethod
    def _parse_response(proto, response):
        """Parses the content from a validator response Message.
        """
        try:
            content = proto()
            content.ParseFromString(response.content)
            return content
        except ValidatorConnectionError:
            LOGGER.warning('Validator disconnected while waiting for response')
            raise errors.ValidatorDisconnected()
        except (DecodeError, AttributeError):
            LOGGER.error('Validator response was not parsable: %s', response)
            raise errors.ValidatorResponseInvalid()

    @staticmethod
    def _check_status_errors(proto, content, error_traps=None):
        """Raises HTTPErrors based on error statuses sent from validator.
        Checks for common statuses and runs route specific error traps.
        """
        if content.status == proto.OK:
            return

        try:
            if content.status == proto.INTERNAL_ERROR:
                raise errors.UnknownValidatorError()
        except AttributeError:
            # Not every protobuf has every status enum, so pass AttributeErrors
            pass

        try:
            if content.status == proto.NOT_READY:
                raise errors.ValidatorNotReady()
        except AttributeError:
            pass

        try:
            if content.status == proto.NO_ROOT:
                raise errors.HeadNotFound()
        except AttributeError:
            pass

        try:
            if content.status == proto.INVALID_PAGING:
                raise errors.PagingInvalid()
        except AttributeError:
            pass

        try:
            if content.status == proto.INVALID_SORT:
                raise errors.SortInvalid()
        except AttributeError:
            pass

        # Check custom error traps from the particular route message
        if error_traps is not None:
            for trap in error_traps:
                trap.check(content.status)

    @staticmethod
    def add_cors_headers(request, headers):
        if 'Origin' in request.headers:
            headers['Access-Control-Allow-Origin'] = request.headers['Origin']
            headers["Access-Control-Allow-Methods"] = "GET,POST"
            headers["Access-Control-Allow-Headers"] =\
                "Origin, X-Requested-With, Content-Type, Accept"

    @staticmethod
    def _wrap_response(request, data=None, metadata=None, status=200):
        """Creates the JSON response envelope to be sent back to the client.
        """
        envelope = metadata or {}

        if data is not None:
            envelope['data'] = data

        headers = {}
        RouteHandler.add_cors_headers(request, headers)

        return web.Response(
            status=status,
            content_type='application/json',
            headers=headers,
            text=json.dumps(
                envelope,
                indent=2,
                separators=(',', ': '),
                sort_keys=True))

    @classmethod
    def _wrap_paginated_response(cls, request, response, controls, data):
        """Builds the metadata for a pagingated response and wraps everying in
        a JSON encoded web.Response
        """
        head = response['head_id']
        link = cls._build_url(request, head=head)

        paging_response = response['paging']
        total = paging_response['total_resources']
        paging = {'total_count': total}

        # If there are no resources, there should be nothing else in paging
        if total == 0:
            return cls._wrap_response(
                request,
                data=data,
                metadata={'head': head, 'link': link, 'paging': paging})

        count = controls.get('count', len(data))
        start = paging_response['start_index']
        paging['start_index'] = start

        # Builds paging urls specific to this response
        def build_pg_url(min_pos=None, max_pos=None):
            return cls._build_url(request, head=head, count=count,
                                  min=min_pos, max=max_pos)

        # Build paging urls based on ids
        if 'start_id' in controls or 'end_id' in controls:
            if paging_response['next_id']:
                paging['next'] = build_pg_url(paging_response['next_id'])
            if paging_response['previous_id']:
                paging['previous'] = build_pg_url(
                    max_pos=paging_response['previous_id'])

        # Build paging urls based on indexes
        else:
            end_index = controls.get('end_index', None)
            if end_index is None and start + count < total:
                paging['next'] = build_pg_url(start + count)
            elif end_index is not None and end_index + 1 < total:
                paging['next'] = build_pg_url(end_index + 1)
            if start - count >= 0:
                paging['previous'] = build_pg_url(start - count)

        return cls._wrap_response(
            request,
            data=data,
            metadata={'head': head, 'link': link, 'paging': paging})

    @classmethod
    def _get_metadata(cls, request, response):
        """Parses out the head and link properties based on the HTTP Request
        from the client, and the Protobuf response from the validator.
        """
        head = response.get('head_id', None)
        metadata = {'link': cls._build_url(request, head=head)}

        if head is not None:
            metadata['head'] = head
        return metadata

    @classmethod
    def _build_url(cls, request, path=None, **changes):
        """Builds a response URL by overriding the original queries with
        specified change queries. Change queries set to None will not be used.
        Setting a change query to False will remove it even if there is an
        original query with a value.
        """
        changes = {k: v for k, v in changes.items() if v is not None}
        queries = {**request.url.query, **changes}
        queries = {k: v for k, v in queries.items() if v is not False}
        query_strings = []

        def add_query(key):
            query_strings.append('{}={}'.format(key, queries[key])
                                 if queries[key] != '' else key)

        def del_query(key):
            queries.pop(key, None)

        if 'head' in queries:
            add_query('head')
            del_query('head')

        if 'min' in changes:
            add_query('min')
        elif 'max' in changes:
            add_query('max')
        elif 'min' in queries:
            add_query('min')
        elif 'max' in queries:
            add_query('max')

        del_query('min')
        del_query('max')

        if 'count' in queries:
            add_query('count')
            del_query('count')

        for key in sorted(queries):
            add_query(key)

        scheme = cls._get_forwarded(request, 'proto') or request.url.scheme
        host = cls._get_forwarded(request, 'host') or request.host
        forwarded_path = cls._get_forwarded(request, 'path')
        path = path if path is not None else request.path
        query = '?' + '&'.join(query_strings) if query_strings else ''

        url = '{}://{}{}{}{}'.format(scheme, host, forwarded_path, path, query)
        return url

    @staticmethod
    def _get_forwarded(request, key):
        """Gets a forwarded value from the `Forwarded` header if present, or
        the equivalent `X-Forwarded-` header if not. If neither is present,
        returns an empty string.
        """
        forwarded = request.headers.get('Forwarded', '')
        match = re.search(
            r'(?<={}=).+?(?=[\s,;]|$)'.format(key),
            forwarded,
            re.IGNORECASE)

        if match is not None:
            header = match.group(0)

            if header[0] == '"' and header[-1] == '"':
                return header[1:-1]

            return header

        return request.headers.get('X-Forwarded-{}'.format(key.title()), '')

    @classmethod
    def _expand_block(cls, block):
        """Deserializes a Block's header, and the header of its Batches.
        """
        cls._parse_header(BlockHeader, block)
        if 'batches' in block:
            block['batches'] = [cls._expand_batch(b) for b in block['batches']]
        return block

    @classmethod
    def _expand_batch(cls, batch):
        """Deserializes a Batch's header, and the header of its Transactions.
        """
        cls._parse_header(BatchHeader, batch)
        if 'transactions' in batch:
            batch['transactions'] = [
                cls._expand_transaction(t) for t in batch['transactions']]
        return batch

    @classmethod
    def _expand_transaction(cls, transaction):
        """Deserializes a Transaction's header.
        """
        return cls._parse_header(TransactionHeader, transaction)

    @classmethod
    def _parse_header(cls, header_proto, resource):
        """Deserializes a resource's base64 encoded Protobuf header.
        """
        header = header_proto()
        try:
            header_bytes = base64.b64decode(resource['header'])
            header.ParseFromString(header_bytes)
        except (KeyError, TypeError, ValueError, DecodeError):
            header = resource.get('header', None)
            LOGGER.error(
                'The validator sent a resource with %s %s',
                'a missing header' if header is None else 'an invalid header:',
                header or '')
            raise errors.ResourceHeaderInvalid()

        resource['header'] = cls._message_to_dict(header)
        return resource

    @staticmethod
    def _get_paging_controls(request):
        """Parses min, max, and/or count queries into A paging controls dict.
        """
        min_pos = request.url.query.get('min', None)
        max_pos = request.url.query.get('max', None)
        count = request.url.query.get('count', None)
        controls = {}

        if count is not None:
            try:
                controls['count'] = int(count)
            except ValueError:
                LOGGER.debug('Request query had an invalid count: %s', count)
                raise errors.CountInvalid()

            if controls['count'] <= 0:
                LOGGER.debug('Request query had an invalid count: %s', count)
                raise errors.CountInvalid()

        if min_pos is not None:
            try:
                controls['start_index'] = int(min_pos)
            except ValueError:
                controls['start_id'] = min_pos

        elif max_pos is not None:
            try:
                controls['end_index'] = int(max_pos)
            except ValueError:
                controls['end_id'] = max_pos

        return controls

    @staticmethod
    def _make_paging_message(controls):
        """Turns a raw paging controls dict into Protobuf PagingControls.
        """
        count = controls.get('count', None)
        end_index = controls.get('end_index', None)

        # an end_index must be changed to start_index, possibly modifying count
        if end_index is not None:
            if count is None:
                start_index = 0
                count = end_index
            elif count > end_index + 1:
                start_index = 0
                count = end_index + 1
            else:
                start_index = end_index + 1 - count
        else:
            start_index = controls.get('start_index', None)

        return client_pb2.PagingControls(
            start_id=controls.get('start_id', None),
            end_id=controls.get('end_id', None),
            start_index=start_index,
            count=count)

    @staticmethod
    def _get_sorting_message(request):
        """Parses the sort query into a list of SortControls protobuf messages.
        """
        control_list = []
        sort_query = request.url.query.get('sort', None)
        if sort_query is None:
            return control_list

        for key_string in sort_query.split(','):
            if key_string[0] == '-':
                reverse = True
                key_string = key_string[1:]
            else:
                reverse = False

            keys = key_string.split('.')

            if keys[-1] == 'length':
                compare_length = True
                keys.pop()
            else:
                compare_length = False

            control_list.append(client_pb2.SortControls(
                keys=keys,
                reverse=reverse,
                compare_length=compare_length))

        return control_list

    def _set_wait(self, request, validator_query):
        """Parses the `wait` query parameter, and sets the corresponding
        `wait_for_commit` and `timeout` properties in the validator query.
        """
        wait = request.url.query.get('wait', 'false')
        if wait.lower() != 'false':
            validator_query.wait_for_commit = True
            try:
                validator_query.timeout = int(wait)
            except ValueError:
                # By default, waits for 95% of REST API's configured timeout
                validator_query.timeout = int(self._timeout * 0.95)

    @staticmethod
    def _format_statuses(statuses):
        """Reformat converted BatchStatus dicts: drop empty keys, rename 'id'.
        """
        for status in statuses:
            status['id'] = status.pop('batch_id')
            for k, v in status.copy().items():
                if v == '':
                    status.pop(k)
        return statuses


    @staticmethod
    def _get_filter_ids(request):
        """Parses the `id` filter paramter from the url query.
        """
        filter_ids = request.url.query.get('id', None)
        return filter_ids and filter_ids.split(',')

    @staticmethod
    def _message_to_dict(message):
        """Converts a Protobuf object to a python dict with desired settings.
        """
        return MessageToDict(
            message,
            including_default_value_fields=True,
            preserving_proto_field_name=True)

    @staticmethod
    def _get_type_name(type_enum):
        return Message.MessageType.Name(type_enum)

    @staticmethod
    def _get_status_name(proto, status_enum):
        return proto.Status.Name(status_enum)
