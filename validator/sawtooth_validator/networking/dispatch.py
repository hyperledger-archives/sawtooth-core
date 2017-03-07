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
from functools import partial
import hashlib
import logging
from threading import Condition
from threading import Thread
import queue
import uuid

from sawtooth_validator.networking.interconnect import get_enum_name
from sawtooth_validator.protobuf import validator_pb2

LOGGER = logging.getLogger(__name__)


def _gen_message_id():
    return hashlib.sha512(uuid.uuid4().hex.encode()).hexdigest()


class Dispatcher(Thread):
    def __init__(self):
        super().__init__()
        self._msg_type_handlers = {}
        self._in_queue = queue.Queue()
        self._send_message = {}
        self._message_information = {}
        self._condition = Condition()
        self.daemon = True

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
        with self._condition:
            self._send_message[connection] = send_message
        LOGGER.debug("Added send_message function "
                     "for connection %s", connection)

    def remove_send_message(self, connection):
        """Removes a send_message function previously registered
        with the Dispatcher.

        Args:
            connection (str): A locally unique identifier provided
                by the receiver of messages.
        """
        if connection in self._send_message:
            with self._condition:
                del self._send_message[connection]
            LOGGER.debug("Removed send_message function "
                         "for connection %s", connection)
        else:
            LOGGER.debug("Attempted to remove send_message "
                         "function for connection %s, but no "
                         "send_message function was registered",
                         connection)

    def dispatch(self, connection, message, identity=None):
        if message.message_type in self._msg_type_handlers:
            message_id = _gen_message_id()
            self._message_information[message_id] = (
                connection,
                identity,
                message,
                _ManagerCollection(
                    self._msg_type_handlers[message.message_type])
            )
            self._in_queue.put_nowait(message_id)
        else:
            LOGGER.info("received a message of type %s "
                        "from %s but have no handler for that type",
                        get_enum_name(message.message_type),
                        identity)

    def add_handler(self, message_type, handler, executor):
        if not isinstance(handler, Handler):
            raise ValueError("%s is not a Handler subclass" % handler)
        if message_type not in self._msg_type_handlers:
            self._msg_type_handlers[message_type] = [
                _HandlerManager(executor, handler)]
        else:
            self._msg_type_handlers[message_type].append(
                _HandlerManager(executor, handler))

    def _process(self, message_id):
        with self._condition:
            connection, identity, \
                message, collection = self._message_information[message_id]
        try:
            handler_manager = next(collection)
            future = handler_manager.execute(
                identity, connection, message.content)
            future.add_done_callback(partial(self._determine_next, message_id))
        except IndexError:
            # IndexError is raised if done with handlers
            with self._condition:
                del self._message_information[message_id]

    def _determine_next(self, message_id, future):
        if future.result().status == HandlerStatus.DROP:
            with self._condition:
                del self._message_information[message_id]

        elif future.result().status == HandlerStatus.PASS:
            self._process(message_id)

        elif future.result().status == HandlerStatus.RETURN_AND_PASS:
            with self._condition:
                connection, ident, \
                    original_message, _ = self._message_information[message_id]

            message = validator_pb2.Message(
                content=future.result().message_out.SerializeToString(),
                correlation_id=original_message.correlation_id,
                message_type=future.result().message_type)

            self._send_message[connection](msg=message,
                                           identity=ident)
            self._process(message_id)

        elif future.result().status == HandlerStatus.RETURN:
            with self._condition:
                connection, ident, \
                    original_message, _ = self._message_information[message_id]

                del self._message_information[message_id]

            message = validator_pb2.Message(
                content=future.result().message_out.SerializeToString(),
                correlation_id=original_message.correlation_id,
                message_type=future.result().message_type)

            self._send_message[connection](msg=message,
                                           identity=ident)
        with self._condition:
            if len(self._message_information) == 0:
                self._condition.notify()

    def run(self):
        while True:
            msg_id = self._in_queue.get()
            if msg_id == -1:
                break
            self._process(msg_id)

    def stop(self):
        self._in_queue.put_nowait(-1)

    def block_until_complete(self):
        """Blocks until no more messages are in flight,
        useful for unit tests.
        """
        with self._condition:
            if len(self._message_information) > 0:
                self._condition.wait()


class _HandlerManager(object):
    def __init__(self, executor, handler):
        """
        :param executor: concurrent.futures.Executor
        :param handler: Handler subclass
        """
        self._executor = executor
        self._handler = handler

    def execute(self, identity, connection, message):
        return self._executor.submit(
            self._handler.handle, identity, connection, message)


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


class Handler(object, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def handle(self, identity, connection, message_content):
        """

        :param identity: zmq identity set on the peer's dealer zmq socket
        :param connection: Unique identifier for peer's zmq router socket
        :param message_content: The bytes to be deserialized
                                into a protobuf python class
        :return HandlerResult: The status of the handling
                                and optionally the message
                                and message_type to send out
        """
        raise NotImplementedError()
