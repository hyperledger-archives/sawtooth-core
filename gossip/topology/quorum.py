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

import random
import logging
from twisted.internet import reactor

from gossip.messages.connect_message import send_connection_request
from sawtooth.client import LedgerWebClient
from sawtooth.exceptions import MessageException


logger = logging.getLogger(__name__)

# TimeBetweenProbes vs ProbeTimeout should be a function of the network
# magnitude N, optimized to provide availability, A, while keeping ProbeTimout
# realistic. If a node spends all its time initially probing other nodes, it
# wont be able to respond to ther node's probes.  For sure
# A ~= N*ProbeTimeout/TimeBetweenProbes > .5, but we suggest a greater A.
TimeBetweenProbes = 8.0
ProbeTimeout = 0.25

TargetConnectivity = 3


def start_topology_update(gossiper, callback):
    """Initiates a quorum topology update.
    Args:
        gossiper (Node): The local node.
        callback (function): The function to call once the quorum topology
            update has completed.
    """
    logger.info("initiate quorum topology update")
    _get_quorum(gossiper, callback)


def _get_quorum(gossiper, callback):
    """Attempts to connect gossiper to new available quorum nodes
    Args:
        gossiper (Node): The local node.
        callback (function): The function to call once the quorum topology
            update has completed.
    """
    # find out how many we have and how many nodes we still need need
    count = max(0, TargetConnectivity - len(gossiper.VotingQuorum.keys()))
    # we have all the nodes we need; do next operation (the callback)
    if count <= 0:
        logger.debug('sufficiently connected via %s',
                     [str(x.Name) for x in gossiper.VotingQuorum.itervalues()])
        callback()
        return
    # add nodes we don't have already, in random order
    candidates = [x for x in gossiper.quorum_list()
                  if gossiper.VotingQuorum.get(x.Identifier, None) is None]
    random.shuffle(candidates)
    logger.debug('trying to increase working quorum by %d from candidates %s',
                 count, [str(x.Name) for x in candidates])
    for nd in candidates:
        lwc = LedgerWebClient('http://{0}:{1}'.format(nd.NetHost,
                                                      nd.HttpPort))
        try:
            status = lwc.get_status(verbose=False, timeout=2)
        except MessageException as e:
            logger.debug(e.message)
            continue
        status = status.get('Status', '')
        if status in ['started', "transferring ledger",
                      "waiting for initial connections"]:
            # candidate node is live; add it
            logger.debug('adding %s to quorum', nd.Name)
            gossiper.add_quorum_node(nd)
            if nd.Identifier not in gossiper.peer_id_list():
                send_connection_request(gossiper, nd)
            count -= 1
            if count == 0:
                logger.debug('now sufficiently connected')
                break
    # try again (or possibly execute the piggybacked callback)
    reactor.callLater(TimeBetweenProbes, _get_quorum, gossiper, callback)
