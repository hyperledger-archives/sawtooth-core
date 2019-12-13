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
import queue
import uuid
from collections import namedtuple

# pylint: disable=import-error,no-name-in-module
# needed for google.protobuf import
from google.protobuf.message import DecodeError

from sawtooth_validator.concurrent.thread import InstrumentedThread
from sawtooth_validator.networking.interconnect import get_enum_name
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator import metrics

LOGGER = logging.getLogger(__name__)
COLLECTOR = metrics.get_collector(__name__)


class Priority(enum.IntEnum):
    HIGH = 0
    MEDIUM = 1
    LOW = 2


def _gen_message_id():
    return uuid.uuid4().hex.encode()


_MessageInformation = namedtuple('_MessageInformation', (
    'connection',
    'connection_id',
    'content',
    'correlation_id',
    'collection',
    'message_type'))


class Dispatcher(InstrumentedThread):
    def __init__(self, timeout=10):
        super().__init__(name='Dispatcher')
        self._timeout = timeout
        self._msg_type_handlers = {}
        self._in_queue = queue.PriorityQueue()
        self._send_message = {}
        self._send_last_message = {}
        self._message_information = {}
        self._condition = Condition()
        self._dispatch_timers = {}
        self._priority = {}
        self._preprocessors = {}

    def _get_dispatch_timer(self, tag):
        if tag not in self._dispatch_timers:
            self._dispatch_timers[tag] = COLLECTOR.timer(
                'dispatch_execution_time', tags={"handler": tag},
                instance=self)
        return self._dispatch_timers[tag]

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
            LOGGER.warning("Attempted to remove send_message "
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
            LOGGER.warning("Attempted to remove send_last_message "
                           "function for connection %s, but no "
                           "send_last_message function was registered",
                           connection)

    def dispatch(self, connection, message, connection_id):
        if message.message_type in self._msg_type_handlers:
            priority = self._priority.get(message.message_type, Priority.LOW)
            message_id = _gen_message_id()

            self._message_information[message_id] = \
                _MessageInformation(
                    connection=connection,
                    connection_id=connection_id,
                    content=message.content,
                    correlation_id=message.correlation_id,
                    message_type=message.message_type,
                    collection=_ManagerCollection(
                        self._msg_type_handlers[message.message_type]))

            self._in_queue.put_nowait((priority, message_id))

            queue_size = self._in_queue.qsize()
            if queue_size > 10:
                LOGGER.debug("Dispatch incoming queue size: %s", queue_size)
        else:
            LOGGER.info("received a message of type %s "
                        "from %s but have no handler for that type",
                        get_enum_name(message.message_type),
                        connection_id)

    def add_handler(self, message_type, handler, executor, priority=None):
        if not isinstance(handler, Handler):
            raise TypeError("%s is not a Handler subclass" % handler)
        if message_type not in self._msg_type_handlers:
            self._msg_type_handlers[message_type] = [
                _HandlerManager(executor, handler)]
        else:
            self._msg_type_handlers[message_type].append(
                _HandlerManager(executor, handler))

        if priority is not None:
            self._priority[message_type] = priority

    def set_preprocessor(self, message_type, preprocessor, executor):
        '''
        Sets PREPROCESSOR to run on MESSAGE_TYPE in EXECUTOR.

        PREPROCESSOR: fn(message_content: bytes) -> PreprocessorResult
        '''
        self._preprocessors[message_type] = \
            _PreprocessorManager(
                executor=executor,
                preprocessor=preprocessor)

    def set_message_priority(self, message_type, priority):
        self._priority[message_type] = priority

    def _process(self, message_id):
        message_info = self._message_information[message_id]

        try:
            preprocessor = self._preprocessors[message_info.message_type]
        except KeyError:
            self._process_next(message_id)
            return

        def do_next(result):
            message_info = self._message_information[message_id]

            try:
                # check for a None result
                if result is None:
                    LOGGER.error(
                        "%s preprocessor returned None result for messsage %s",
                        preprocessor,
                        message_id)
                    return

                # check for result status
                if result.status == HandlerStatus.DROP:
                    del self._message_information[message_id]
                    return

                if result.status == HandlerStatus.RETURN:
                    del self._message_information[message_id]

                    message = validator_pb2.Message(
                        content=result.message_out.SerializeToString(),
                        correlation_id=message_info.correlation_id,
                        message_type=result.message_type)

                    try:
                        self._send_message[message_info.connection](
                            msg=message,
                            connection_id=message_info.connection_id)
                    except KeyError:
                        LOGGER.warning(
                            "Can't send message %s back to "
                            "%s because connection %s not in dispatcher",
                            get_enum_name(message.message_type),
                            message_info.connection_id,
                            message_info.connection)

                    return

                # store the preprocessor result
                self._message_information[message_id] = \
                    _MessageInformation(
                        connection=message_info.connection,
                        connection_id=message_info.connection_id,
                        content=result.content,
                        correlation_id=message_info.correlation_id,
                        collection=message_info.collection,
                        message_type=message_info.message_type)

                self._process_next(message_id)

            except Exception:  # pylint: disable=broad-except
                LOGGER.exception(
                    "Unhandled exception after preprocessing")

        preprocessor.execute(
            connection_id=message_info.connection_id,
            message_content=message_info.content,
            callback=do_next)

    def _process_next(self, message_id):
        message_info = self._message_information[message_id]

        try:
            handler_manager = next(message_info.collection)
        except IndexError:
            # IndexError is raised if done with handlers
            del self._message_information[message_id]
            return

        timer_tag = type(handler_manager.handler).__name__
        timer_ctx = self._get_dispatch_timer(timer_tag).time()

        def do_next(result):
            timer_ctx.stop()
            try:
                self._determine_next(message_id, result)
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception(
                    "Unhandled exception while determining next")

        handler_manager.execute(
            message_info.connection_id,
            message_info.content,
            do_next)

    def _determine_next(self, message_id, result):
        if result is None:
            LOGGER.debug('Ignoring None handler result, likely due to an '
                         'unhandled error while executing the handler')
            return

        if result.status == HandlerStatus.DROP:
            del self._message_information[message_id]

        elif result.status == HandlerStatus.PASS:
            self._process_next(message_id)

        elif result.status == HandlerStatus.RETURN_AND_PASS:
            message_info = self._message_information[message_id]

            if result.message_out and result.message_type:
                message = validator_pb2.Message(
                    content=result.message_out.SerializeToString(),
                    correlation_id=message_info.correlation_id,
                    message_type=result.message_type)
                try:
                    self._send_message[message_info.connection](
                        msg=message,
                        connection_id=message_info.connection_id)
                except KeyError:
                    LOGGER.warning(
                        "Can't send message %s back to "
                        "%s because connection %s not in dispatcher",
                        get_enum_name(message.message_type),
                        message_info.connection_id,
                        message_info.connection)

                self._process_next(message_id)
            else:
                LOGGER.error("HandlerResult with status of RETURN_AND_PASS "
                             "is missing message_out or message_type")

        elif result.status == HandlerStatus.RETURN:
            message_info = self._message_information[message_id]

            del self._message_information[message_id]

            if result.message_out and result.message_type:
                message = validator_pb2.Message(
                    content=result.message_out.SerializeToString(),
                    correlation_id=message_info.correlation_id,
                    message_type=result.message_type)
                try:
                    self._send_message[message_info.connection](
                        msg=message,
                        connection_id=message_info.connection_id)
                except KeyError:
                    LOGGER.warning(
                        "Can't send message %s back to "
                        "%s because connection %s not in dispatcher",
                        get_enum_name(message.message_type),
                        message_info.connection_id,
                        message_info.connection)
            else:
                LOGGER.error("HandlerResult with status of RETURN "
                             "is missing message_out or message_type")

        elif result.status == HandlerStatus.RETURN_AND_CLOSE:
            message_info = self._message_information[message_id]

            del self._message_information[message_id]

            if result.message_out and result.message_type:
                message = validator_pb2.Message(
                    content=result.message_out.SerializeToString(),
                    correlation_id=message_info.correlation_id,
                    message_type=result.message_type)
                try:
                    LOGGER.warning(
                        "Sending hang-up in reply to %s to connection %s",
                        get_enum_name(message_info.message_type),
                        message_info.connection_id)
                    self._send_last_message[message_info.connection](
                        msg=message,
                        connection_id=message_info.connection_id)
                except KeyError:
                    LOGGER.warning(
                        "Can't send last message %s back to "
                        "%s because connection %s not in dispatcher",
                        get_enum_name(message.message_type),
                        message_info.connection_id,
                        message_info.connection)
            else:
                LOGGER.error("HandlerResult with status of RETURN_AND_CLOSE "
                             "is missing message_out or message_type")
        with self._condition:
            if not self._message_information:
                self._condition.notify()

    def run(self):
        while True:
            try:
                _, msg_id = self._in_queue.get()
                if msg_id == -1:
                    break
                self._process(msg_id)
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unhandled exception while dispatching")

    def stop(self):
        self._in_queue.put_nowait((Priority.HIGH, -1))

    def block_until_complete(self):
        """Blocks until no more messages are in flight,
        useful for unit tests.
        """
        with self._condition:
            if self._message_information:
                self._condition.wait()


class _PreprocessorManager:
    def __init__(self, executor, preprocessor):
        self._executor = executor
        self._preprocessor = preprocessor

    def execute(self, connection_id, message_content, callback):
        def wrapped(message_content):
            try:
                processed = self._preprocessor(message_content)
            except DecodeError:
                LOGGER.exception(
                    'Could not deserialize message from %s',
                    connection_id)

                return PreprocessorResult(
                    status=HandlerStatus.DROP)

            return callback(processed)

        return self._executor.submit(wrapped, message_content)


class _HandlerManager:
    def __init__(self, executor, handler):
        """
        :param executor: concurrent.futures.Executor
        :param handler: Handler subclass
        """
        self._executor = executor
        self._handler = handler

    @property
    def handler(self):
        return self._handler

    def execute(self, connection_id, message, callback):
        def wrapped(connection_id, message):
            return callback(self._handler.handle(connection_id, message))

        return self._executor.submit(wrapped, connection_id, message)


class _ManagerCollection:
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


class HandlerResult:
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


class PreprocessorResult(HandlerResult):
    def __init__(self, content=None, status=None,
                 message_out=None, message_type=None):
        """
        :param content: the content returned if preprocessing is successful
        :param status HandlerStatus: informs the dispatcher on how to proceed
        :param message_out protobuf Python class:
        :param message_type: validator_pb2.Message.* enum value
        """
        self.content = content
        super().__init__(status, message_out, message_type)


class Handler(metaclass=abc.ABCMeta):
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
