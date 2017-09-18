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
import abc
import enum
import logging
from threading import Condition
from threading import Thread
import queue
import uuid

from sawtooth_validator.networking.interconnect import get_enum_name
from sawtooth_validator.protobuf import validator_pb2

LOGGER = logging.getLogger(__name__)


def _gen_message_id():
    return uuid.uuid4().hex.encode()


class Dispatcher(Thread):
    def __init__(self, timeout=10):
        super().__init__(name='Dispatcher')
        self._timeout = timeout
        self._msg_type_handlers = {}
        self._in_queue = queue.Queue()
        self._send_message = {}
        self._send_last_message = {}
        self._message_information = {}
        self._condition = Condition()

    def add_send_message(self, connection, send_message):
        """Adds a send_message function to the Dispatcher's
        dictionary of functions indexed by connection.

        Args:
            connection (str): A locally unique identifier
                provided by the receiver of messages.
            send_message (fn): The method that should be called
                by the dispatcher to respond to messages which
                arrive via connection.
        """
        self._send_message[connection] = send_message
        LOGGER.debug("Added send_message function "
                     "for connection %s", connection)

    def add_send_last_message(self, connection, send_last_message):
        """Adds a send_last_message function to the Dispatcher's
        dictionary of functions indexed by connection.

        Args:
            connection (str): A locally unique identifier
                provided by the receiver of messages.
            send_last_message (fn): The method that should be called
                by the dispatcher to respond to messages which
                arrive via connection, when the connection should be closed
                after the message has been sent.
        """
        self._send_last_message[connection] = send_last_message
        LOGGER.debug("Added send_last_message function "
                     "for connection %s", connection)

    def remove_send_message(self, connection):
        """Removes a send_message function previously registered
        with the Dispatcher.

        Args:
            connection (str): A locally unique identifier provided
                by the receiver of messages.
        """
        if connection in self._send_message:
            del self._send_message[connection]
            LOGGER.debug("Removed send_message function "
                         "for connection %s", connection)
        else:
            LOGGER.debug("Attempted to remove send_message "
                         "function for connection %s, but no "
                         "send_message function was registered",
                         connection)

    def remove_send_last_message(self, connection):
        """Removes a send_last_message function previously registered
        with the Dispatcher.

        Args:
            connection (str): A locally unique identifier provided
                by the receiver of messages.
        """
        if connection in self._send_last_message:
            del self._send_last_message[connection]
            LOGGER.debug("Removed send_last_message function "
                         "for connection %s", connection)
        else:
            LOGGER.debug("Attempted to remove send_last_message "
                         "function for connection %s, but no "
                         "send_last_message function was registered",
                         connection)

    def dispatch(self, connection, message, connection_id):
        if message.message_type in self._msg_type_handlers:
            message_id = _gen_message_id()
            self._message_information[message_id] = (
                connection,
                connection_id,
                message,
                _ManagerCollection(
                    self._msg_type_handlers[message.message_type])
            )
            self._in_queue.put_nowait(message_id)
        else:
            LOGGER.info("received a message of type %s "
                        "from %s but have no handler for that type",
                        get_enum_name(message.message_type),
                        connection_id)

    def add_handler(self, message_type, handler, executor):
        if not isinstance(handler, Handler):
            raise TypeError("%s is not a Handler subclass" % handler)
        if message_type not in self._msg_type_handlers:
            self._msg_type_handlers[message_type] = [
                _HandlerManager(executor, handler)]
        else:
            self._msg_type_handlers[message_type].append(
                _HandlerManager(executor, handler))

    def _process(self, message_id):
        _, connection_id, \
            message, collection = self._message_information[message_id]
        try:
            handler_manager = next(collection)
            future = handler_manager.execute(connection_id, message.content)

            def do_next(future):
                try:
                    self._determine_next(message_id, future)
                except Exception:  # pylint: disable=broad-except
                    LOGGER.exception(
                        "Unhandled exception while determining next")

            future.add_done_callback(do_next)
        except IndexError:
            # IndexError is raised if done with handlers
            del self._message_information[message_id]

    def _determine_next(self, message_id, future):
        try:
            res = future.result(timeout=self._timeout)
        except TimeoutError:
            LOGGER.exception("Dispatcher timeout waiting on handler result.")
            raise

        if res.status == HandlerStatus.DROP:
            del self._message_information[message_id]

        elif res.status == HandlerStatus.PASS:
            self._process(message_id)

        elif res.status == HandlerStatus.RETURN_AND_PASS:
            connection, connection_id, \
                original_message, _ = self._message_information[message_id]

            message = validator_pb2.Message(
                content=res.message_out.SerializeToString(),
                correlation_id=original_message.correlation_id,
                message_type=res.message_type)
            try:
                self._send_message[connection](msg=message,
                                               connection_id=connection_id)
            except KeyError:
                LOGGER.info("Can't send message %s back to "
                            "%s because connection %s not in dispatcher",
                            get_enum_name(message.message_type), connection_id,
                            connection)
            self._process(message_id)

        elif res.status == HandlerStatus.RETURN:
            connection, connection_id,  \
                original_message, _ = self._message_information[message_id]

            del self._message_information[message_id]

            message = validator_pb2.Message(
                content=res.message_out.SerializeToString(),
                correlation_id=original_message.correlation_id,
                message_type=res.message_type)
            try:
                self._send_message[connection](msg=message,
                                               connection_id=connection_id)
            except KeyError:
                LOGGER.info("Can't send message %s back to "
                            "%s because connection %s not in dispatcher",
                            get_enum_name(message.message_type), connection_id,
                            connection)

        elif res.status == HandlerStatus.RETURN_AND_CLOSE:
            connection, connection_id,  \
                original_message, _ = self._message_information[message_id]

            del self._message_information[message_id]

            message = validator_pb2.Message(
                content=res.message_out.SerializeToString(),
                correlation_id=original_message.correlation_id,
                message_type=res.message_type)
            try:
                self._send_last_message[connection](
                    msg=message,
                    connection_id=connection_id)
            except KeyError:
                LOGGER.info("Can't send message %s back to "
                            "%s because connection %s not in dispatcher",
                            get_enum_name(message.message_type), connection_id,
                            connection)
        with self._condition:
            if not self._message_information:
                self._condition.notify()

    def run(self):
        while True:
            try:
                msg_id = self._in_queue.get()
                if msg_id == -1:
                    break
                self._process(msg_id)
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unhandled exception while dispatching")

    def stop(self):
        self._in_queue.put_nowait(-1)

    def block_until_complete(self):
        """Blocks until no more messages are in flight,
        useful for unit tests.
        """
        with self._condition:
            if self._message_information:
                self._condition.wait()


class _HandlerManager(object):
    def __init__(self, executor, handler):
        """
        :param executor: concurrent.futures.Executor
        :param handler: Handler subclass
        """
        self._executor = executor
        self._handler = handler

    def execute(self, connection_id, message):
        return self._executor.submit(
            self._handler.handle, connection_id, message)


class _ManagerCollection(object):
    """Wraps a list of _HandlerManagers and
    keeps track of which handler_manager is next
    """
    def __init__(self, handler_managers):
        self._chain = handler_managers
        self._index = 0

    def __next__(self):
        result = self._chain[self._index]
        self._index += 1
        return result


class HandlerResult(object):
    def __init__(self, status, message_out=None, message_type=None):
        """
        :param status HandlerStatus: the status of the handler's processing
        :param message_out protobuf Python class:
        :param message_type: validator_pb2.Message.* enum value
        """
        self.status = status
        self.message_out = message_out
        self.message_type = message_type


class HandlerStatus(enum.Enum):
    DROP = 1  # Do no further processing on the message
    RETURN = 2  # Send the message out. Could be because of error condition
    RETURN_AND_PASS = 3  # Send a message out and process the next handler
    PASS = 4  # Send the message to the next handler
    RETURN_AND_CLOSE = 5  # Send the message out and close connection


class Handler(object, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def handle(self, connection_id, message_content):
        """

        :param connection_id: A unique identifier for the connection that
                              sent the message
        :param message_content: The bytes to be deserialized
                                into a protobuf python class
        :return HandlerResult: The status of the handling
                                and optionally the message
                                and message_type to send out
        """
        raise NotImplementedError()
