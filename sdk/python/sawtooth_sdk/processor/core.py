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

import logging

from sawtooth_sdk.client.stream import Stream
from sawtooth_sdk.client.stream import MessageType

from sawtooth_sdk.processor.state import State
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError

from sawtooth_protobuf.processor_pb2 import TransactionProcessorRegisterRequest
from sawtooth_protobuf.processor_pb2 import TransactionProcessRequest
from sawtooth_protobuf.processor_pb2 import TransactionProcessResponse


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)


class TransactionProcessor(object):
    def __init__(self, url):
        self._stream = Stream(url)
        self._handlers = []

    def add_handler(self, handler):
        self._handlers.append(handler)

    def start(self):
        futures = []
        for handler in self._handlers:
            for version in handler.family_versions:
                for encoding in handler.encodings:
                    future = self._stream.send(
                        message_type='tp/register',
                        content=TransactionProcessorRegisterRequest(
                            family=handler.family_name,
                            version=version,
                            encoding=encoding,
                            namespaces=handler.namespaces).SerializeToString())
                    futures.append(future)

        for future in futures:
            LOGGER.info("future result: %s", repr(future.result))

        while True:
            msg = self._stream.receive()
            LOGGER.info("received %s", msg.message_type)

            request = TransactionProcessRequest()
            request.ParseFromString(msg.content)
            state = State(self._stream, request.context_id)

            try:
                self._handlers[0].apply(request, state)
                self._stream.send_back(
                    message_type=MessageType.TP_RESPONSE,
                    correlation_id=msg.correlation_id,
                    content=TransactionProcessResponse(
                        status=TransactionProcessResponse.OK
                    ).SerializeToString())
            except InvalidTransaction as it:
                LOGGER.warning("Invalid Transaction %s", it)
                self._stream.send_back(
                    message_type=MessageType.TP_RESPONSE,
                    correlation_id=msg.correlation_id,
                    content=TransactionProcessResponse(
                        status=TransactionProcessResponse.INVALID_TRANSACTION
                    ).SerializeToString())
            except InternalError as ie:
                LOGGER.warning("State Error! %s", ie)
                self._stream.send_back(
                    message_type=MessageType.TP_RESPONSE,
                    correlation_id=msg.correlation_id,
                    content=TransactionProcessResponse(
                        status=TransactionProcessResponse.INTERNAL_ERROR
                    ).SerializeToString())
