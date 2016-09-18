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

from twisted.internet import reactor

from gossip.messages import random_walk_message

logger = logging.getLogger(__name__)

TimeBetweenProbes = 1.0
TargetConnectivity = 3


def start_topology_update(gossiper, callback):
    """Initiates a random walk topology update.

    Args:
        gossiper (Node): The local node.
        callback (function): The function to call once the random walk
            topology update has completed.
    """
    logger.info("initiate random walk topology update")

    count = max(0, TargetConnectivity - len(gossiper.peer_list()))
    logger.debug('adding %d connections through random walk', count)

    _sendrandomwalk(gossiper, callback, count)


def _sendrandomwalk(gossiper, callback, count):
    if count <= 0:
        callback()
        return

    random_walk_message.send_random_walk_message(gossiper)
    reactor.callLater(TimeBetweenProbes, _sendrandomwalk, gossiper, callback,
                      count - 1)
