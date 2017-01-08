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
from sawtooth_sdk.client.stream import Stream


class Routes(object):
    def __init__(self, stream_url):
        self._stream = Stream(stream_url)

    @asyncio.coroutine
    def hello(self, request):
        text = "Hello World \n"
        return web.Response(text=text)

    @asyncio.coroutine
    def stream(self, request):
        # will need to figure out a way to handle the case where the Validator
        # is not running so no result will be returned
        text = "Connecting to Validator \n"
        future = self._stream.send(
            message_type='client/get',
            content=b"Temp Data")
        extra = future.result().content
        return web.Response(text=text + str(extra) + "\n")
