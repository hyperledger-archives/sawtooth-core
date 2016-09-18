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
import random

from gossip.messages import connect_message, topology_message

logger = logging.getLogger(__name__)

MaximumConnectivity = 15
MinimumConnectivity = 1
ConnectivityFudgeFactor = 1


def start_topology_update(gossiper, oncomplete):
    """Initiates a Barabasi-Albert topology update.

    Args:
        gossiper (Node): The local node.
        oncomplete(function): The function to call once the topology
            update has completed.
    """
    logger.info("initiate topology probe")
    topology_message.initiate_topology_probe(
        gossiper, lambda g, m: update_connections(g, m, oncomplete))


def update_connections(gossiper, topology, oncomplete):
    """Connects the node to the network by building a Barabasi-Albert graph.

    Note:
        For more information see
        http://en.wikipedia.org/wiki/Barab%C3%A1si%E2%80%93Albert_model

    Args:
        gossiper (Node): The local node.
        topology (dict): Map of nodes to connections.
        oncomplete (function): The function to call once the topology
            update has completed.
    """
    logger.info("update connections from topology probe")

    for peer, connections in topology.iteritems():
        logger.debug("node %s --> %s", peer.Name, len(connections))

    # First pass through the topology information that was collected, compute
    # the total number of connections per node which will give us a
    # distribution for connections, Bara
    total = 0
    candidates = {}
    for peer, connections in topology.iteritems():
        if peer.Identifier == gossiper.LocalNode.Identifier:
            continue

        if peer.Identifier in gossiper.NodeMap:
            continue

        # this is strictly NOT part of the Barabasi graph construction because
        # it forces a limit on connectivity, however it removes some of the
        # worst hotspots without fundamentally changing the graph structure
        count = len(connections)
        if count > MaximumConnectivity:
            continue

        candidates[peer] = count
        total += count

    # Second pass selects some subset of nodes based on the number of existing
    # connections and sends out a connection request to each
    if total > 0:
        for peer, count in candidates.iteritems():

            # the FudgeFactor is used to increase the chance that we'll connect
            # to a node, strictly speaking the fudge factor should be 0
            if random.randint(0, total - 1) < count + ConnectivityFudgeFactor:
                connect_message.send_connection_request(gossiper, peer)

    # call the final handler
    oncomplete(gossiper)


def _sendconnectionrequest(gossiper, peer):
    logger.info("add node %s, %s, %s", peer, peer.Identifier[:8],
                peer.NetAddress)

    gossiper.add_node(peer)

    request = connect_message.ConnectSynMessage()
    request.NetHost = gossiper.LocalNode.endpoint_host
    request.NetPort = gossiper.LocalNode.endpoint_port
    request.Name = gossiper.LocalNode.Name

    gossiper.send_message(request, peer.Identifier)
