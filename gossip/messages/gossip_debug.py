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
This module implements classes derived from Message for representing
debug messages, including pings, dump connections, dump peer stats,
reset peer stats, dump node stats, and reset stats. It also defines
handler methods to be called when these message types arrive.
"""

import logging
import string
import time

from gossip import message

logger = logging.getLogger(__name__)


def register_message_handlers(gossiper):
    """Registers the debug-related message handlers for a node.

    Args:
        gossiper (Node): The node to register message handlers on.
    """
    gossiper.register_message_handler(PingMessage, _pinghandler)
    gossiper.register_message_handler(DumpConnectionsMessage,
                                      _dumpconnectionshandler)
    gossiper.register_message_handler(DumpPeerStatsMessage, _dumppeerhandler)
    gossiper.register_message_handler(ResetPeerStatsMessage, _resetpeerhandler)
    gossiper.register_message_handler(DumpNodeStatsMessage, _dumpstatshandler)
    gossiper.register_message_handler(ResetStatsMessage, _resetstatshandler)


class PingMessage(message.Message):
    """Ping messages are sent to a peer node to verify connectivity.

    Attributes:
        PingMessage.MessageType (str): The class name of the message.
        IsSystemMessage (bool): Whether or not this is a system message.
            System messages have special delivery priority rules.
        IsForward (bool): Whether the message should be automatically
            forwarded.
        IsReliable (bool): Whether reliable delivery is required.
    """
    MessageType = "/gossip.messages.GossipDebug/Ping"

    def __init__(self, minfo={}):
        """Constructor for the PingMessage class.

        Args:
            minfo (dict): Dictionary of values for message fields.
        """
        super(PingMessage, self).__init__(minfo)

        self.IsSystemMessage = True
        self.IsForward = True
        self.IsReliable = True

    def dump(self):
        """Dumps a dict containing object attributes.

        Returns:
            dict: A mapping of object attribute names to values.
        """
        result = super(PingMessage, self).dump()
        return result


def _pinghandler(msg, gossiper):
    logger.warn("ping, %s, %s", time.time(), msg.Identifier[:8])


class DumpConnectionsMessage(message.Message):
    """Dump connections messages are sent to a peer node to request
    it to log enabled and disabled connections information.

    Attributes:
        DumpConnectionsMessage.MessageType (str): The class name of the
            message.
        IsSystemMessage (bool): Whether or not this is a system message.
            System messages have special delivery priority rules.
        IsForward (bool): Whether the message should be automatically
            forwarded.
        IsReliable (bool): Whether reliable delivery is required.
    """
    MessageType = "/gossip.messages.GossipDebug/DumpConnections"

    def __init__(self, minfo={}):
        """Constructor for the DumpConnectionsMessage class.

        Args:
            minfo (dict): Dictionary of values for message fields.
        """
        super(DumpConnectionsMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = True
        self.IsReliable = True

    def dump(self):
        """Dumps a dict containing object attributes.

        Returns:
            dict: A mapping of object attribute names to values.
        """
        result = super(DumpConnectionsMessage, self).dump()
        return result


def _dumpconnectionshandler(msg, gossiper):
    identifier = "{0}, {1:0.2f}, {2}".format(gossiper.LocalNode, time.time(),
                                             msg.Identifier[:8])

    enabled = []
    disabled = []
    for peer in gossiper.peer_list(allflag=True):
        if peer.Enabled:
            enabled.append(peer.Name)
        else:
            disabled.append(peer.Name)

    logger.info("connections, %s, enabled, %s", identifier,
                string.join(enabled, ', '))
    logger.info("connections, %s, disabled, %s", identifier,
                string.join(disabled, ', '))


class DumpPeerStatsMessage(message.Message):
    """Dump peer stats messages are sent to a peer node to request
    it to log statistics about specified peer connections.

    Attributes:
        DumpPeerStatsMessage.MessageType (str): The class name of the message.
        IsSystemMessage (bool): Whether or not this is a system message.
            System messages have special delivery priority rules.
        IsForward (bool): Whether the message should be automatically
            forwarded.
        IsReliable (bool): Whether reliable delivery is required.
        PeerIDList (list): A list of peers to dump stats for.
        MetricIDList (list): A list of stats to dump.
    """
    MessageType = "/gossip.messages.GossipDebug/DumpPeerStats"

    def __init__(self, minfo={}):
        """Constructor for the DumpPeerStatsMessage class.

        Args:
            minfo (dict): Dictionary of values for message fields.
        """
        super(DumpPeerStatsMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = True
        self.IsReliable = True

        self.PeerIDList = minfo.get('PeerIDList', [])
        self.MetricList = minfo.get('MetricList', [])

    def dump(self):
        """Dumps a dict containing object attributes.

        Returns:
            dict: A mapping of object attribute names to values.
        """
        result = super(DumpPeerStatsMessage, self).dump()

        result['PeerIDList'] = []
        for peerid in self.PeerIDList:
            result['PeerIDList'].append(peerid)

        result['MetricList'] = []
        for peerid in self.MetricList:
            result['MetricList'].append(peerid)

        return result


def _dumppeerhandler(msg, gossiper):
    idlist = msg.PeerIDList
    if len(idlist) == 0:
        idlist = gossiper.peer_id_list()

    for peer in gossiper.NodeMap.itervalues():
        if peer.Identifier in idlist or peer.Name in idlist:
            if peer.Enabled:
                peer.dump_peer_stats(msg.Identifier, msg.MetricList)


class ResetPeerStatsMessage(message.Message):
    """Reset peer stats messages are sent to a peer node to request
    it to reset statistics about specified peer connections.

    Attributes:
        ResetPeerStatsMessage.MessageType (str): The class name of the message.
        IsSystemMessage (bool): Whether or not this is a system message.
            System messages have special delivery priority rules.
        IsForward (bool): Whether the message should be automatically
            forwarded.
        IsReliable (bool): Whether reliable delivery is required.
        PeerIDList (list): A list of peers to reset stats for.
        MetricIDList (list): A list of stats to reset.
    """
    MessageType = "/gossip.messages.GossipDebug/ResetPeerStats"

    def __init__(self, minfo={}):
        """Constructor for the ResetPeerStatsMessage class.

        Args:
            minfo (dict): Dictionary of values for message fields.
        """
        super(ResetPeerStatsMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = True
        self.IsReliable = True

        self.PeerIDList = minfo.get('PeerIDList', [])
        self.MetricList = minfo.get('MetricList', [])

    def dump(self):
        """Dumps a dict containing object attributes.

        Returns:
            dict: A mapping of object attribute names to values.
        """
        result = super(ResetPeerStatsMessage, self).dump()

        result['PeerIDList'] = []
        for peerid in self.PeerIDList:
            result['PeerIDList'].append(peerid)

        result['MetricList'] = []
        for peerid in self.MetricList:
            result['MetricList'].append(peerid)

        return result


def _resetpeerhandler(msg, gossiper):
    idlist = msg.PeerIDList
    if len(idlist) == 0:
        idlist = gossiper.peer_id_list()

    for peer in gossiper.NodeMap.itervalues():
        if peer.Identifier in idlist or peer.Name in idlist:
            if peer.Enabled:
                peer.reset_peer_stats(msg.MetricList)


class DumpNodeStatsMessage(message.Message):
    """Dump node stats messages are sent to a peer node to request
    it to dump statistics.

    Attributes:
        DumpNodeStatsMessage.MessageType (str): The class name of the message.
        IsSystemMessage (bool): Whether or not this is a system message.
            System messages have special delivery priority rules.
        IsForward (bool): Whether the message should be automatically
            forwarded.
        IsReliable (bool): Whether reliable delivery is required.
        DomainList (list): A list of domains to dump stats for.
        MetricList (list): A list of stats to dump.
    """
    MessageType = "/gossip.messages.GossipDebug/DumpNodeStats"

    def __init__(self, minfo={}):
        """Constructor for the DumpNodeStatsMessage class.

        Args:
            minfo (dict): Dictionary of values for message fields.
        """
        super(DumpNodeStatsMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = True
        self.IsReliable = True

        self.DomainList = minfo.get('DomainList', [])
        self.MetricList = minfo.get('MetricList', [])

    def dump(self):
        """Dumps a dict containing object attributes.

        Returns:
            dict: A mapping of object attribute names to values.
        """
        result = super(DumpNodeStatsMessage, self).dump()

        result['DomainList'] = []
        for domain in self.DomainList:
            result['DomainList'].append(domain)

        result['MetricList'] = []
        for metric in self.MetricList:
            result['MetricList'].append(metric)

        return result


def _dumpstatshandler(msg, gossiper):
    domains = gossiper.StatDomains.keys() if len(
        msg.DomainList) == 0 else msg.DomainList
    for domain in domains:
        if domain in gossiper.StatDomains:
            gossiper.StatDomains[domain].dump_stats(msg.Identifier,
                                                    msg.MetricList)


class ResetStatsMessage(message.Message):
    """Reset stats messages are sent to a peer node to request
    it to reset statistics.

    Attributes:
        ResetStatsMessage.MessageType (str): The class name of the message.
        IsSystemMessage (bool): Whether or not this is a system message.
            System messages have special delivery priority rules.
        IsForward (bool): Whether the message should be automatically
            forwarded.
        IsReliable (bool): Whether reliable delivery is required.
        DomainList (list): A list of domains to reset stats for.
        MetricList (list): A list of stats to reset.
    """
    MessageType = "/gossip.messages.GossipDebug/ResetStats"

    def __init__(self, minfo={}):
        """Constructor for the ResetStatsMessage class.

        Args:
            minfo (dict): Dictionary of values for message fields.
        """
        super(ResetStatsMessage, self).__init__(minfo)

        self.IsSystemMessage = False
        self.IsForward = True
        self.IsReliable = True

        self.DomainList = minfo.get('DomainList', [])
        self.MetricList = minfo.get('MetricList', [])

    def dump(self):
        """Dumps a dict containing object attributes.

        Returns:
            dict: A mapping of object attribute names to values.
        """
        result = super(ResetStatsMessage, self).dump()

        result['DomainList'] = []
        for domain in self.DomainList:
            result['DomainList'].append(domain)

        result['MetricList'] = []
        for metric in self.MetricList:
            result['MetricList'].append(metric)

        return result


def _resetstatshandler(msg, gossiper):
    domains = gossiper.StatDomains.keys() if len(
        msg.DomainList) == 0 else msg.DomainList
    for domain in domains:
        if domain in gossiper.StatDomains:
            gossiper.StatDomains[domain].reset_stats(msg.MetricList)
