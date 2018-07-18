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
import binascii
import logging
import subprocess

import zmq
import zmq.asyncio

from sawtooth_sdk.protobuf.processor_pb2 import TpRegisterRequest
from sawtooth_sdk.protobuf.processor_pb2 import TpRegisterResponse
from sawtooth_sdk.protobuf.validator_pb2 import Message

from sawtooth_processor_test.message_types import to_protobuf_class
from sawtooth_processor_test.message_types import to_message_type

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class UnexpectedMessageException(Exception):
    def __init__(self, message_type, expected, received):
        super().__init__("{}: Expected {}({}):'{}', Got {}({}):'{}'".format(
            to_protobuf_class(message_type).__name__,
            to_protobuf_class(to_message_type(expected)),
            to_message_type(expected),
            str(expected).strip(),
            to_protobuf_class(to_message_type(received)),
            to_message_type(received),
            str(received).strip()
        ))
        self.message_type_name = to_protobuf_class(message_type).__name__
        self.expected = expected
        self.received = received


class MockValidator:
    def __init__(self):
        self._comparators = {}

        # ZMQ connection
        self._url = None
        self._context = None
        self._socket = None

        # asyncio
        self._loop = None

        # Transaction processor
        self._tp_ident = None

        # The set request comparison is a little more complex by default
        self.register_comparator(Message.TP_STATE_SET_REQUEST,
                                 compare_set_request)
        self.register_comparator(Message.TP_PROCESS_RESPONSE,
                                 compare_tp_process_response_status_only)

    def listen(self, url):
        """
        Opens a connection to the processor. Must be called before using send
        or received.
        """
        self._url = url

        self._loop = zmq.asyncio.ZMQEventLoop()
        asyncio.set_event_loop(self._loop)

        self._context = zmq.asyncio.Context()

        # User ROUTER socket, the TransactionProcessor uses DEALER
        self._socket = self._context.socket(zmq.ROUTER)

        LOGGER.debug("Binding to %s", self._url)

        self._socket.set(zmq.LINGER, 0)

        try:
            self._socket.bind(self._url)

        # Catch errors with binding and print out more debug info
        except zmq.error.ZMQError:
            netstat = "netstat -lp | grep -e tcp"
            result = subprocess.check_output(netstat, shell=True).decode()
            LOGGER.debug("\n`%s`", netstat)
            LOGGER.debug(result)

            LOGGER.debug("`ps pid`")
            try:
                lines = result.split('\n')[:-1]
                for line in lines:
                    pidnprog = line.split()[6]
                    if pidnprog != '-':
                        pid = pidnprog.split('/')[0]
                        ps = subprocess.check_output(
                            ["ps", pid]
                        ).decode().split('\n')[1]
                        LOGGER.debug(ps)
            except BaseException:
                LOGGER.warning("Failed to show process info")

            # Raise the original error again
            raise

    def close(self):
        """
        Closes the connection to the processor. Must be called at the end of
        the program or sockets may be left open.
        """
        self._socket.close()
        self._context.term()
        self._loop.close()

    def register_processor(self):
        message, ident = self.receive()
        if message.message_type != Message.TP_REGISTER_REQUEST:
            return False

        self._tp_ident = ident

        request = TpRegisterRequest()
        request.ParseFromString(message.content)
        LOGGER.debug(
            "Processor registered: %s, %s, %s",
            str(request.family), str(request.version),
            str(request.namespaces)
        )
        response = TpRegisterResponse(
            status=TpRegisterResponse.OK)
        self.send(response, message.correlation_id)
        return True

    def send(self, message_content, correlation_id=None):
        """
        Convert the message content to a protobuf message, including
        serialization of the content and insertion of the content type.
        Optionally include the correlation id in the message. Messages
        are sent with the name of this class as the sender.
        """

        message = Message(
            message_type=to_message_type(message_content),
            content=message_content.SerializeToString(),
            correlation_id=correlation_id,
        )

        return self._loop.run_until_complete(
            self._send(self._tp_ident, message))

    async def _send(self, ident, message):
        """
        (asyncio coroutine) Send the message and wait for a response.
        :param message (sawtooth_sdk.protobuf.Message)
        :param ident (str) the identity of the zmq.DEALER to send to
        """

        LOGGER.debug(
            "Sending %s(%s) to %s",
            str(to_protobuf_class(message.message_type).__name__),
            str(message.message_type),
            str(ident)
        )

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

        LOGGER.debug(result)
        LOGGER.debug("%s:%s", len(result), binascii.hexlify(result))

        # Deconstruct the message
        message = Message()
        message.ParseFromString(result)

        LOGGER.debug(
            "Received %s(%s) from %s",
            str(to_protobuf_class(message.message_type).__name__),
            str(message.message_type),
            str(ident)
        )

        return message, ident

    async def _receive(self):
        ident, result = await self._socket.recv_multipart()
        return ident, result

    def expect(self, expected_content):
        """
        Receive a message and compare its contents to that of
        `expected_content`. If the contents are the same, return the message.
        If not, raise an UnexpectedMessageException with the message.

        Note that this will do a direct `==` comparison. If a more complex
        comparison must be performed (for example if a payload must first be
        deserialized) a comparison function may be registered for a specific
        message type using, `register_comparator()`.
        """

        # Receive a message
        message, _ = self.receive()

        # Parse the message content
        protobuf_class = to_protobuf_class(message.message_type)
        received_content = protobuf_class()
        received_content.ParseFromString(message.content)

        if not self._compare(received_content, expected_content):
            raise UnexpectedMessageException(
                message.message_type,
                expected_content,
                received_content
            )

        return message

    def expect_one(self, expected_content_list):
        """
        Receive a message and compare its contents to each item in the list.
        Upon finding a match, return the message and the index of the match
        as a tuple. If no match is found, raise an UnexpectedMessageException
        with the message.
        """

        message, _ = self.receive()

        # Parse the message content
        protobuf_class = to_protobuf_class(message.message_type)
        received_content = protobuf_class()
        received_content.ParseFromString(message.content)

        for exp_con in expected_content_list:
            if self._compare(exp_con, received_content):
                return message, expected_content_list.index(exp_con)

        raise UnexpectedMessageException(
            message.message_type,
            expected_content_list,
            received_content)

    def respond(self, message_content, message):
        """
        Respond to the message with the given message_content.
        """
        return self.send(message_content, message.correlation_id)

    def register_comparator(self, message_type, comparator):
        self._comparators[message_type] = comparator

    def _compare(self, obj1, obj2):
        msg_type = to_message_type(obj1)
        msg_type2 = to_message_type(obj2)

        if msg_type != msg_type2:
            return False

        if msg_type in self._comparators:
            return self._comparators[msg_type](obj1, obj2)

        return obj1 == obj2


def compare_set_request(req1, req2):
    if len(req1.entries) != len(req2.entries):
        return False

    entries1 = sorted([(e.address, e.data) for e in req1.entries])
    entries2 = sorted([(e.address, e.data) for e in req2.entries])
    if entries1 != entries2:
        return False

    return True


def compare_tp_process_response_status_only(res1, res2):
    return res1.status == res2.status
