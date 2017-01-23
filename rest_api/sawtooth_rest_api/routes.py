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
from aiohttp import web
from aiohttp.helpers import parse_mimetype
# pylint: disable=no-name-in-module,import-error
# needed for the google.protobuf imports to pass pylint
from google.protobuf.json_format import MessageToJson
from google.protobuf.message import Message as BaseMessage

from sawtooth_sdk.client.future import FutureTimeoutError
from sawtooth_sdk.client.stream import Stream

from sawtooth_protobuf import client_pb2 as client
from sawtooth_protobuf.validator_pb2 import Message


class Routes(object):
    def __init__(self, stream_url):
        self._stream = Stream(stream_url)

    def _try_validator_request(self, message_type, content):
        """
        Sends a protobuf message to the validator
        Handles a possible timeout if validator is unresponsive
        """
        timeout = 5
        timeout_msg = 'Could not reach validator, validator timed out'

        if isinstance(content, BaseMessage):
            content = content.SerializeToString()

        future = self._stream.send(message_type=message_type, content=content)

        try:
            response = future.result(timeout=timeout)
        except FutureTimeoutError as e:
            print(str(e))
            raise web.HTTPGatewayTimeout(reason=timeout_msg)

        return response.content

    def _try_response_parse(self, proto, response):
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
            pass

        return parsed

    def _try_client_response(self, headers, parsed):
        """
        Sends a response back to the client based on Accept header
        Defaults to JSON
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

    def _generic_get(self, web_request, msg_type, msg_content, resp_proto):
        response = self._try_validator_request(msg_type, msg_content)
        parsed = self._try_response_parse(resp_proto, response)
        return self._try_client_response(web_request.headers, parsed)

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

        # TODO: Update to parsing protobuf once validator updated
        parsed_response = validator_response.decode('utf-8')
        return web.json_response(parsed_response)

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
        root = request.match_info.get("merkle_root", "")
        params = request.rel_url.query
        # if no prefix is defined return all
        prefix = params.get("prefix", "")
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

        root = request.match_info.get("merkle_root", "")
        addr = request.match_info.get("address", "")
        client_request = client.ClientStateGetRequest(merkle_root=root,
                                                      address=addr)

        validator_response = self._try_validator_request(
            Message.CLIENT_STATE_GET_REQUEST,
            client_request
        )

        parsed_response = self._try_response_parse(
            client.ClientStateGetResponse,
            validator_response
        )

        if parsed_response.status == client.ClientStateGetResponse.NONLEAF:
            raise web.HTTPBadRequest(reason=nonleaf_msg)

        return self._try_client_response(
            request.headers,
            parsed_response
        )
