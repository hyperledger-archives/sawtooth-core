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
import asyncio
import json
import base64
from aiohttp import web
from aiohttp.helpers import parse_mimetype
# pylint: disable=no-name-in-module,import-error
# needed for the google.protobuf imports to pass pylint
from google.protobuf.json_format import MessageToJson, MessageToDict
from google.protobuf.message import Message as BaseMessage

from sawtooth_sdk.client.future import FutureTimeoutError
from sawtooth_sdk.client.stream import Stream
from sawtooth_sdk.protobuf.validator_pb2 import Message

from sawtooth_rest_api.protobuf import client_pb2 as client
from sawtooth_rest_api.protobuf.block_pb2 import BlockHeader
from sawtooth_rest_api.protobuf.batch_pb2 import BatchHeader
from sawtooth_rest_api.protobuf.transaction_pb2 import TransactionHeader


class RouteHandler(object):
    def __init__(self, stream_url):
        self._stream = Stream(stream_url)

    @asyncio.coroutine
    def hello(self, request):
        text = "Hello World \n"
        return web.Response(text=text)

    @asyncio.coroutine
    def batches(self, request):
        """
        Takes protobuf binary from HTTP POST, and sends it to the validator
        """
        mime_type = 'application/octet-stream'
        type_msg = 'Expected an octet-stream encoded Protobuf binary'
        type_error = web.HTTPBadRequest(reason=type_msg)

        if request.headers['Content-Type'] != mime_type:
            return type_error

        payload = yield from request.read()
        validator_response = self._try_validator_request(
            Message.CLIENT_BATCH_SUBMIT_REQUEST,
            payload
        )
        response = client.ClientBatchSubmitResponse()
        response.ParseFromString(validator_response)
        return RouteHandler._try_client_response(request.headers, response)

    @asyncio.coroutine
    def state_current(self, request):
        # CLIENT_STATE_CURRENT_REQUEST
        return self._generic_get(
            web_request=request,
            msg_type=Message.CLIENT_STATE_CURRENT_REQUEST,
            msg_content=client.ClientStateCurrentRequest(),
            resp_proto=client.ClientStateCurrentResponse,
        )

    @asyncio.coroutine
    def state_list(self, request):
        # CLIENT_STATE_LIST_REQUEST
        root = RouteHandler._safe_get(request.match_info, 'merkle_root')
        # if no prefix is defined return all
        prefix = RouteHandler._safe_get(request.rel_url.query, 'prefix')
        client_request = client.ClientStateListRequest(merkle_root=root,
                                                       prefix=prefix)
        return self._generic_get(
            web_request=request,
            msg_type=Message.CLIENT_STATE_LIST_REQUEST,
            msg_content=client_request,
            resp_proto=client.ClientStateListResponse,
        )

    @asyncio.coroutine
    def state_get(self, request):
        # CLIENT_STATE_GET_REQUEST
        nonleaf_msg = 'Expected a specific leaf address, ' \
                      'but received a prefix instead'

        root = RouteHandler._safe_get(request.match_info, 'merkle_root')
        addr = RouteHandler._safe_get(request.match_info, 'address')
        client_request = client.ClientStateGetRequest(merkle_root=root,
                                                      address=addr)

        validator_response = self._try_validator_request(
            Message.CLIENT_STATE_GET_REQUEST,
            client_request
        )

        parsed_response = RouteHandler._old_response_parse(
            client.ClientStateGetResponse,
            validator_response
        )

        if parsed_response.status == client.ClientStateGetResponse.NONLEAF:
            raise web.HTTPBadRequest(reason=nonleaf_msg)

        return RouteHandler._try_client_response(
            request.headers,
            parsed_response
        )

    @asyncio.coroutine
    def block_list(self, request):
        """
        Fetch a list of blocks from the validator
        """
        response = self._query_validator(
            Message.CLIENT_BLOCK_LIST_REQUEST,
            client.ClientBlockListResponse,
            client.ClientBlockListRequest()
        )

        blocks = [RouteHandler._expand_block(b) for b in response['blocks']]
        return RouteHandler._wrap_response(data=blocks)

    @asyncio.coroutine
    def block_get(self, request):
        """
        Fetch a list of blocks from the validator
        """
        block_id = RouteHandler._safe_get(request.match_info, 'block_id')
        request = client.ClientBlockGetRequest(block_id=block_id)

        response = self._query_validator(
            Message.CLIENT_BLOCK_GET_REQUEST,
            client.ClientBlockGetResponse,
            request
        )

        block = RouteHandler._expand_block(response['block'])
        return RouteHandler._wrap_response(data=block)

    @staticmethod
    def _safe_get(obj, key, default=''):
        """
        aiohttp very helpfully parses param strings to replace '+' with ' '
        This is very bad when your block ids contain meaningful +'s
        """
        return obj.get(key, default).replace(' ', '+')

    def _query_validator(self, request_type, response_proto, content):
        """
        Sends a request to the validator and parses the response
        """
        response = self._try_validator_request(request_type, content)
        return RouteHandler._try_response_parse(response_proto, response)

    def _try_validator_request(self, message_type, content):
        """
        Sends a protobuf message to the validator
        Handles a possible timeout if validator is unresponsive
        """
        timeout = 300
        timeout_msg = 'Could not reach validator, validator timed out'

        if isinstance(content, BaseMessage):
            content = content.SerializeToString()

        future = self._stream.send(message_type=message_type, content=content)

        try:
            response = future.result(timeout=timeout)
        except FutureTimeoutError:
            raise web.HTTPServiceUnavailable(reason=timeout_msg)

        return response.content

    @staticmethod
    def _try_response_parse(proto, response):
        """
        Parses a protobuf response from the validator
        Raises common validator error statuses as HTTP errors
        """
        unknown_msg = 'An unknown error occured with your request'
        notfound_msg = 'There is no resource at that root, address or prefix'

        parsed = proto()
        parsed.ParseFromString(response)

        try:
            if parsed.status == proto.ERROR:
                raise web.HTTPInternalServerError(reason=unknown_msg)
            if parsed.status == proto.NORESOURCE:
                raise web.HTTPNotFound(reason=notfound_msg)
        except AttributeError:
            # Not every protobuf has every status, so pass AttributeErrors
            pass

        return MessageToDict(parsed, preserving_proto_field_name=True)

    @staticmethod
    def _wrap_response(data=None, head=None, link=None):
        """
        Creates a JSON response envelope and sends it back to the client
        """
        envelope = {}

        if data:
            envelope['data'] = data
        if head:
            envelope['head'] = head
        if link:
            envelope['link'] = link

        return web.Response(
            content_type='application/json',
            text=json.dumps(
                envelope,
                indent=2,
                separators=(',', ': '),
                sort_keys=True
            )
        )

    @staticmethod
    def _expand_block(block):
        RouteHandler._parse_header(BlockHeader, block)
        if 'batches' in block:
            block['batches'] = [RouteHandler._expand_batch(b)
                                for b in block['batches']]
        return block

    @staticmethod
    def _expand_batch(batch):
        RouteHandler._parse_header(BatchHeader, batch)
        if 'transactions' in batch:
            batch['transactions'] = [RouteHandler._expand_transaction(t)
                                     for t in batch['transactions']]
        return batch

    @staticmethod
    def _expand_transaction(transaction):
        return RouteHandler._parse_header(TransactionHeader, transaction)

    @staticmethod
    def _parse_header(header_proto, obj):
        """
        A helper method to parse a byte string encoded protobuf 'header'
        Args:
            header_proto: The protobuf class of the encoded header
            obj: The dict formatted object containing the 'header'
        """
        header = header_proto()
        header_bytes = base64.b64decode(obj['header'])
        header.ParseFromString(header_bytes)
        obj['header'] = MessageToDict(header, preserving_proto_field_name=True)
        return obj

    def _generic_get(self, web_request, msg_type, msg_content, resp_proto):
        """
        Used by pre-spec /state routes
        Should be removed when routes are updated to spec
        """
        response = self._try_validator_request(msg_type, msg_content)
        parsed = RouteHandler._old_response_parse(resp_proto, response)
        return RouteHandler._try_client_response(web_request.headers, parsed)

    @staticmethod
    def _old_response_parse(proto, response):
        """
        Used by pre-spec /state routes
        Should be removed when routes are updated to spec
        """
        unknown_msg = 'An unknown error occured with your request'
        notfound_msg = 'There is no resource at that root, address or prefix'

        parsed = proto()
        parsed.ParseFromString(response)

        try:
            if parsed.status == proto.ERROR:
                raise web.HTTPInternalServerError(reason=unknown_msg)
            if parsed.status == proto.NORESOURCE:
                raise web.HTTPNotFound(reason=notfound_msg)
        except AttributeError:
            # Not every protobuf has every status, so pass AttributeErrors
            pass

        return parsed

    @staticmethod
    def _try_client_response(headers, parsed):
        """
        Used by pre-spec /state and /batches routes
        Should be removed when routes are updated to spec
        """
        media_msg = 'The requested media type is unsupported'
        mime_type = None
        sub_type = None

        try:
            accept_types = headers['Accept']
            mime_type, sub_type, _, _ = parse_mimetype(accept_types)
        except KeyError:
            pass

        if mime_type == 'application' and sub_type == 'octet-stream':
            return web.Response(
                content_type='application/octet-stream',
                body=parsed.SerializeToString()
            )

        if ((mime_type in ['application', '*'] or mime_type is None)
                and (sub_type in ['json', '*'] or sub_type is None)):
            return web.Response(
                content_type='application/json',
                text=MessageToJson(parsed)
            )

        raise web.HTTPUnsupportedMediaType(reason=media_msg)
