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
import time

from twisted.internet import task

from gossip import event_handler

LOGGER = logging.getLogger(__name__)


class MessageDispatcher(object):
    """
    Attributes:
        message_handler_map (dict): A map of message types to handler
            functions.
        on_heartbeat (EventHandler): An EventHandler for functions
            to call when the heartbeat timer fires.
    """

    def __init__(self,
                 context=None,
                 message_source=None):
        """
        :param context: context object to pass to message handlers.
        :param message_source: A message source(dispatcher) that provides
            the incoming messages to dispatch.
        """
        self.message_handler_map = {}
        self.context = context
        self.message_source = message_source

        self.on_heartbeat = event_handler.EventHandler(
            'MessageDispatcher.on_heartbeat')
        self._heartbeat_timer = task.LoopingCall(self._heartbeat)
        self._heartbeat_timer.start(0.05)

    def has_message_handler(self, type_name):
        return type_name in self.message_handler_map

    def register_message_handler(self, msg, handler):
        """Register a function to handle incoming messages for the
        specified message type.

        Args:
            msg (type): A type object derived from MessageType.
            handler (function): Function to be called when messages of
                that type arrive.
        """
        self.message_handler_map[msg.MessageType] = (msg, handler)
        if self.message_source is not None:
            self.message_source.register_message_handler(msg, self.dispatch)

    def clear_message_handler(self, msg):
        """Remove any handlers associated with incoming messages for the
        specified message type.

        Args:
            msg (type): A type object derived from MessageType.
        """
        try:
            del self.message_handler_map[msg.MessageType]
        except:
            pass

    def get_message_handler(self, msg):
        """Returns the function registered to handle incoming messages
        for the specified message type.

        Args:
            msg (type): A type object derived from MessageType.
            handler (function): Function to be called when messages of
                that type arrive.

        Returns:
            function: The registered handler function for this message
                type.
        """
        return self.message_handler_map[msg.MessageType][1]

    def unpack_message(self, mtype, minfo):
        """Unpack a dictionary into a message object using the
        registered handlers.

        Args:
            mtype (str): Name of the message type.
            minfo (dict): Dictionary with message data.

        Returns:
            The result of the handler called with minfo.
        """
        return self.message_handler_map[mtype][0](minfo)

    def dispatch(self, msg, context=None):
        """Dispatch message to handler if there is a
        registered handler.
        """
        if msg is None or not hasattr(msg, 'MessageType'):
            LOGGER.error('Invalid message sent to dispatch')
            return

        if msg.MessageType in self.message_handler_map:
            self.message_handler_map[msg.MessageType][1](msg, self.context)
        else:
            LOGGER.error(
                'No handler registered for MessageType %s',
                msg.MessageType)

    def _heartbeat(self):
        """Invoke functions that are connected to the heartbeat timer.
        """
        self.on_heartbeat.fire(time.time())
