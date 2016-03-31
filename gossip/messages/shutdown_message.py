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
"""
This module implements a ShutdownMessage class derived from Message for
representing shutdown messages. It also defines a handler method for taking
action when shutdown messages are received.
"""

import logging

from twisted.internet import reactor

from gossip import message

logger = logging.getLogger(__name__)

# Unless this is set we ignore shutdown messages, it should be set
# to the identifier for a source that is allowed to execute the
# shutdown message

AdministrationNode = None


def register_message_handlers(gossiper):
    """Registers the shutdown-related message handlers for a node.

    Args:
        gossiper (Node): The node to register message handlers on.
    """
    gossiper.register_message_handler(ShutdownMessage, shutdown_handler)


class ShutdownMessage(message.Message):
    """Shutdown messages are sent to a peer node to initiate shutdown.

    Attributes:
        MessageType (str): The class name of the message.
        NodeList (list): The list of nodes to shutdown.
        IsSystemMessage (bool): Whether or not this is a system message.
            System messages have special delivery priority rules.
        IsForward (bool): Whether the message should be automatically
            forwarded.
        IsReliable (bool): Whether reliable delivery is required.
    """
    MessageType = "/" + __name__ + "/ShutdownMessage"

    def __init__(self, minfo={}):
        """Constructor for the ShutdownMessage class.

        Args:
            minfo (dict): Dictionary of values for message fields.
        """
        super(ShutdownMessage, self).__init__(minfo)

        # We are not going to hang around waiting for acks to come back
        self.NodeList = minfo.get('NodeList', [])

        # We are not going to hang around waiting for acks to come back
        self.IsSystemMessage = True
        self.IsForward = True
        self.IsReliable = False

    def dump(self):
        """Dumps a dict containing object attributes.

        Returns:
            dict: A mapping of object attribute names to values.
        """
        result = super(ShutdownMessage, self).dump()
        result['NodeList'] = self.NodeList

        return result


def shutdown_handler(msg, gossiper):
    """Handles shutdown events.

    When a shutdown message arrives, the node checks to see if it is
    included in the shutdown list and, if so, shuts down.

    Args:
        msg (Message): The recevied shutdown request message.
        gossiper (Node): The local node.
    """
    if msg.OriginatorID != AdministrationNode:
        logger.warn(
            'shutdown received from non-administrator; received from %s, '
            'expecting %s',
            msg.OriginatorID, AdministrationNode)
        return

    if msg.NodeList and gossiper.LocalNode.Identifier not in msg.NodeList:
        logger.warn('this node not included in shutdown list, %s',
                    msg.NodeList)
        return

    # Need to wait long enough for all the shutdown packets to be sent out
    logging.warn('shutdown message received from %s', msg.OriginatorID)
    reactor.callLater(1.0, shutdown, gossiper)


def shutdown(gossiper):
    """Callback for node shutdown.

    Shuts down the gossip networking locally and stops the main event loop.

    Args:
        gossiper (Node): The local node.
    """
    gossiper.shutdown()
    reactor.stop()
