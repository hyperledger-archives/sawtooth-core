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

import asyncio
import binascii
import logging

import zmq
import zmq.asyncio

from sawtooth_sdk.protobuf.validator_pb2 import Message

LOGGER = logging.getLogger(__name__)


class MockValidator(object):

    def __init__(self):
        # ZMQ connection
        self._url = None
        self._context = None
        self._socket = None

        # asyncio
        self._loop = None

        self._ident = None

    def listen(self, url):
        """
        Opens a connection to the processor. Must be called before using send
        or received.
        """
        self._url = url

        self._loop = zmq.asyncio.ZMQEventLoop()
        asyncio.set_event_loop(self._loop)

        self._context = zmq.asyncio.Context()

        self._socket = self._context.socket(zmq.ROUTER)
        LOGGER.debug("Binding to " + self._url)
        self._socket.set(zmq.LINGER, 0)
        self._socket.bind(self._url)

    def close(self):
        """
        Closes the connection to the processor. Must be called at the end of
        the program or sockets may be left open.
        """
        self._socket.close()
        self._context.term()
        self._loop.close()

    def send(self, message_type, message_content, correlation_id=None):
        """
        Convert the message content to a protobuf message, including
        serialization of the content and insertion of the content type.
        Optionally include the correlation id in the message. Messages
        are sent with the name of this class as the sender.
        """
        if self._ident is None:
            raise ValueError("Must receive a message first.")

        message = Message(
            message_type=message_type,
            content=message_content.SerializeToString(),
            correlation_id=correlation_id,
        )

        return self._loop.run_until_complete(
            self._send(self._ident, message)
        )

    async def _send(self, ident, message):
        """
        (asyncio coroutine) Send the message and wait for a response.
        :param message (sawtooth_sdk.protobuf.Message)
        :param ident (str) the identity of the zmq.DEALER to send to
        """

        return await self._socket.send_multipart([
            ident,
            message.SerializeToString()
        ])

    def receive(self):
        """
        Receive a message back. Does not parse the message content.
        """
        ident, result = self._loop.run_until_complete(
            self._receive()
        )
        if self._ident is None:
            self._ident = ident

        LOGGER.debug(result)
        LOGGER.debug("%s:%s", len(result), binascii.hexlify(result))

        # Deconstruct the message
        message = Message()
        message.ParseFromString(result)

        LOGGER.debug(
            "Received %s from %s",
            str(message.message_type),
            str(ident)
        )

        return message

    async def _receive(self):
        ident, result = await self._socket.recv_multipart()
        return ident, result

    def respond(self, message_type, message_content, message):
        """
        Respond to the message with the given message_type and
        message_content.
        """
        return self.send(
            message_type, message_content, message.correlation_id)
