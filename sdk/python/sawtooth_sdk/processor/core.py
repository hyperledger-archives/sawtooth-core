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

from concurrent.futures import CancelledError
import concurrent.futures
import itertools
import logging


from sawtooth_sdk.messaging.exceptions import ValidatorConnectionError
from sawtooth_sdk.messaging.future import FutureTimeoutError
from sawtooth_sdk.messaging.stream import RECONNECT_EVENT
from sawtooth_sdk.messaging.stream import Stream

from sawtooth_sdk.processor.context import Context
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError

from sawtooth_sdk.protobuf.processor_pb2 import TpRegisterRequest
from sawtooth_sdk.protobuf.processor_pb2 import TpRegisterResponse
from sawtooth_sdk.protobuf.processor_pb2 import TpUnregisterRequest
from sawtooth_sdk.protobuf.processor_pb2 import TpUnregisterResponse
from sawtooth_sdk.protobuf.processor_pb2 import TpProcessRequest
from sawtooth_sdk.protobuf.processor_pb2 import TpProcessResponse
from sawtooth_sdk.protobuf.processor_pb2 import TpPingResponse
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_sdk.protobuf.validator_pb2 import Message


LOGGER = logging.getLogger(__name__)


class TransactionProcessor(object):
    def __init__(self, url):
        self._stream = Stream(url)
        self._url = url
        self._handlers = []

    @property
    def zmq_id(self):
        return self._stream.zmq_id

    def add_handler(self, handler):
        """Add a transaction family handler
        :param handler:
        """
        self._handlers.append(handler)

    def _matches(self, handler, header):
        return header.family_name == handler.family_name \
            and header.family_version in handler.family_versions \
            and header.payload_encoding in handler.encodings

    def _find_handler(self, header):
        """Find a handler for a particular (family_name,
        family_versions, payload_encoding)
        :param header transaction_pb2.TransactionHeader:
        :return: handler
        """
        try:
            return next(handler for handler in self._handlers
                        if self._matches(handler, header))
        except StopIteration:
            LOGGER.debug("Missing handler for header: %s", header)
            return None

    def _register_requests(self):
        """Returns all of the TpRegisterRequests for handlers

        :return (list): list of TpRegisterRequests
        """
        return itertools.chain.from_iterable(  # flattens the nested list
            [
                [TpRegisterRequest(
                    family=n,
                    version=v,
                    encoding=e,
                    namespaces=h.namespaces)
                 for n, v, e in itertools.product(
                    [h.family_name],
                     h.family_versions,
                     h.encodings)] for h in self._handlers])

    def _unregister_request(self):
        """Returns a single TP_UnregisterRequest that requests
        that the validator stop sending transactions for previously
        registered handlers.

        :return (processor_pb2.TpUnregisterRequest):
        """
        return TpUnregisterRequest()

    def _process(self, msg):
        if msg.message_type != Message.TP_PROCESS_REQUEST:
            LOGGER.debug(
                "Transaction Processor recieved invalid message type. "
                "Message type should be TP_PROCESS_REQUEST,"
                " but is %s", Message.MessageType.Name(msg.message_type))
            return

        request = TpProcessRequest()
        request.ParseFromString(msg.content)
        state = Context(self._stream, request.context_id)
        header = TransactionHeader()
        header.ParseFromString(request.header)
        try:
            if not self._stream.is_ready():
                raise ValidatorConnectionError()
            handler = self._find_handler(header)
            if handler is None:
                return
            handler.apply(request, state)
            self._stream.send_back(
                message_type=Message.TP_PROCESS_RESPONSE,
                correlation_id=msg.correlation_id,
                content=TpProcessResponse(
                    status=TpProcessResponse.OK
                ).SerializeToString())
        except InvalidTransaction as it:
            LOGGER.warning("Invalid Transaction %s", it)
            try:
                self._stream.send_back(
                    message_type=Message.TP_PROCESS_RESPONSE,
                    correlation_id=msg.correlation_id,
                    content=TpProcessResponse(
                        status=TpProcessResponse.INVALID_TRANSACTION,
                        message=str(it),
                        extended_data=it.extended_data
                    ).SerializeToString())
            except ValidatorConnectionError as vce:
                # TP_PROCESS_REQUEST has made it through the
                # handler.apply and an INVALID_TRANSACTION would have been
                # sent back but the validator has disconnected and so it
                # doesn't care about the response.
                LOGGER.warning("during invalid transaction response: %s", vce)
        except InternalError as ie:
            LOGGER.warning("internal error: %s", ie)
            try:
                self._stream.send_back(
                    message_type=Message.TP_PROCESS_RESPONSE,
                    correlation_id=msg.correlation_id,
                    content=TpProcessResponse(
                        status=TpProcessResponse.INTERNAL_ERROR,
                        message=str(ie),
                        extended_data=ie.extended_data
                    ).SerializeToString())
            except ValidatorConnectionError as vce:
                # Same as the prior except block, but an internal error has
                # happened, but because of the disconnect the validator
                # probably doesn't care about the response.
                LOGGER.warning("during internal error response: %s", vce)
        except ValidatorConnectionError as vce:
            # Somewhere within handler.apply a future resolved with an
            # error status that the validator has disconnected. There is
            # nothing left to do but reconnect.
            LOGGER.warning("during handler.apply a future was resolved "
                           "with error status: %s", vce)

    def _process_future(self, future, timeout=None, sigint=False):
        try:
            msg = future.result(timeout)
        except CancelledError:
            # This error is raised when Task.cancel is called on
            # disconnect from the validator in stream.py, for
            # this future.
            return
        if msg is RECONNECT_EVENT:
            if sigint is False:
                LOGGER.info("reregistering with validator")
                self._stream.wait_for_ready()
                self._register()
        else:
            LOGGER.debug(
                'received message of type: %s',
                Message.MessageType.Name(msg.message_type))
            if msg.message_type == Message.TP_PING:
                self._stream.send_back(
                    message_type=Message.TP_PING_RESPONSE,
                    correlation_id=msg.correlation_id,
                    content=TpPingResponse(
                        status=TpPingResponse.OK).SerializeToString())
                return
            self._process(msg)

    def _register(self):
        futures = []
        for message in self._register_requests():
            self._stream.wait_for_ready()
            future = self._stream.send(
                message_type=Message.TP_REGISTER_REQUEST,
                content=message.SerializeToString())
            futures.append(future)

        for future in futures:
            resp = TpRegisterResponse()
            try:
                resp.ParseFromString(future.result().content)
                LOGGER.info("register attempt: %s",
                            TpRegisterResponse.Status.Name(resp.status))
            except ValidatorConnectionError as vce:
                LOGGER.info("during waiting for response on registration: %s",
                            vce)

    def _unregister(self):
        message = self._unregister_request()
        self._stream.wait_for_ready()
        future = self._stream.send(
            message_type=Message.TP_UNREGISTER_REQUEST,
            content=message.SerializeToString())
        response = TpUnregisterResponse()
        try:
            response.ParseFromString(future.result(1).content)
            LOGGER.info("unregister attempt: %s",
                        TpUnregisterResponse.Status.Name(response.status))
        except ValidatorConnectionError as vce:
            LOGGER.info("during waiting for response on unregistration: %s",
                        vce)

    def start(self):
        fut = None
        try:
            self._register()
            while True:
                # During long running processing this
                # is where the transaction processor will
                # spend most of its time
                fut = self._stream.receive()
                self._process_future(fut)
        except KeyboardInterrupt:
            try:
                # tell the validator to not send any more messages
                self._unregister()
                while True:
                    if fut is not None:
                        # process futures as long as the tp has them,
                        # if the TP_PROCESS_REQUEST doesn't come from
                        # zeromq->asyncio in 1 second raise a
                        # concurrent.futures.TimeOutError and be done.
                        self._process_future(fut, 1, sigint=True)
                        fut = self._stream.receive()
            except concurrent.futures.TimeoutError:
                # Where the tp will usually exit after
                # a KeyboardInterrupt. Caused by the 1 second
                # timeout in _process_future.
                pass
            except FutureTimeoutError:
                # If the validator is not able to respond to the
                # unregister request, exit.
                pass

    def stop(self):
        self._stream.close()
