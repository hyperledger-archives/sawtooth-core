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

from sawtooth_sdk.client.future import FutureTimeoutError
from sawtooth_sdk.client.stream import Stream
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

    @asyncio.coroutine
    def hello(self, request):
        text = "Hello World \n"
        return web.Response(text=text)

    @asyncio.coroutine
    def stream(self, request):
        text = "Connecting to Validator \n"
        future = self._stream.send(
            message_type='client/get',
            content=b"Temp Data")
        extra = self._try_future_content(future)
        return web.Response(text=text + str(extra) + "\n")

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
