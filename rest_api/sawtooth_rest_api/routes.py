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
from google.protobuf.json_format import MessageToJson

from sawtooth_sdk.client.future import FutureTimeoutError
from sawtooth_sdk.client.stream import Stream

from sawtooth_validator.protobuf import client_pb2 as client
from sawtooth_validator.protobuf.validator_pb2 import Message


class Routes(object):
    def __init__(self, stream_url):
        self._stream = Stream(stream_url)

    def _try_future_content(self, future):
        timeout = 5
        timeout_msg = 'Could not reach validator, validator timed out'

        try:
            content = future.result(timeout=timeout).content
        except FutureTimeoutError as e:
            print(str(e))
            raise web.HTTPGatewayTimeout(reason=timeout_msg)

        return content

    def _parsed_response(self, headers, response, proto):
        """
        Parses a protobuf response from the validator,
        and formats it as a JSON HTTP response.
        Protos must have an OK and NO RESOURCE enum status.
        """
        notfound_msg = 'There is no resource at that address or prefix'
        unknown_msg = 'An unknown error occured with your request'
        media_msg = 'The requested media type is unsupported'
        mime_type = None
        sub_type = None

        parsed = proto()
        parsed.ParseFromString(response)

        try:
            if parsed.status == proto.ERROR:
                raise web.HTTPInternalServerError(reason=unknown_msg)
            if parsed.status == proto.NORESOURCE:
                raise web.HTTPNotFound(reason=notfound_msg)
        except AttributeError:
            pass


        try:
            accept_types = headers['Accept']
            mime_type, sub_type, suffix, params = parse_mimetype(accept_types)
        except KeyError:
            pass

        if mime_type == 'application' and sub_type == 'octet-stream':
            return web.Response(
                content_type='application/octet-stream',
                body=response
            )

        if ((mime_type == 'application' or mime_type == '*' or mime_type == None)
            and (sub_type == 'json' or sub_type == '*' or sub_type == None)):
            return web.Response(
                content_type='application/json',
                text=MessageToJson(parsed)
            )

        raise web.HTTPUnsupportedMediaType(reason=media_msg)


    @asyncio.coroutine
    def hello(self, request):
        text = "Hello World \n"
        return web.Response(text=text)

    @asyncio.coroutine
    def batches(self, request):
        """
        Takes a Protobuf binary from an HTTP Post, and sends it
        to the Validator
        """
        mime_type = 'application/octet-stream'
        type_msg = 'Expected an octet-stream encoded Protobuf binary'
        type_error = web.HTTPBadRequest(reason=type_msg)

        if request.headers['Content-Type'] != mime_type:
            return type_error

        payload = yield from request.read()

        if type(payload) is not bytes:
            return type_error

        future = self._stream.send(
            message_type=Message.CLIENT_BATCH_SUBMIT_REQUEST,
            content=payload
        )

        validator_response = self._try_future_content(future)

        # TODO: Update decode to serializing protobuf once merged
        return web.json_response(validator_response.decode('utf-8'))

    @asyncio.coroutine
    def state_current(self, request):
        #CLIENT_STATE_CURRENT_REQUEST
        client_request = client.ClientStateCurrentRequest()
        future = self._stream.send(
            message_type=Message.CLIENT_STATE_CURRENT_REQUEST,
            content=client_request.SerializeToString()
        )

        validator_response = self._try_future_content(future)

        return self._parsed_response(
            request.headers,
            validator_response,
            client.ClientStateCurrentResponse
        )

    @asyncio.coroutine
    def state_get(self, request):
        #CLIENT_STATE_GET_REQUEST
        root = request.match_info.get("merkle_root", "")
        addr = request.match_info.get("address", "")

        client_request = client.ClientStateGetRequest(merkle_root=root,
                                                      address=addr)
        future = self._stream.send(
            message_type=Message.CLIENT_STATE_GET_REQUEST,
            content=client_request.SerializeToString()
        )

        validator_response = self._try_future_content(future)

        return self._parsed_response(
            request.headers,
            validator_response,
            client.ClientStateGetResponse
        )

    @asyncio.coroutine
    def state_list(self, request):
        #CLIENT_STATE_LIST_REQUEST
        root = request.match_info.get("merkle_root", "")
        params = request.rel_url.query
        # if no prefix is defined return all
        prefix = params.get("prefix", "")

        client_request = client.ClientStateListRequest(merkle_root=root,
                                                       prefix=prefix)
        future = self._stream.send(
            message_type=Message.CLIENT_STATE_LIST_REQUEST,
            content=client_request.SerializeToString()
        )

        validator_response = self._try_future_content(future)

        return self._parsed_response(
            request.headers,
            validator_response,
            client.ClientStateListResponse
        )
