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
This module defines the Node class for the Gossip protocol and the
RoundTripEstimator and TransmissionQueue classes, both of which are used
by the Node implementation.
"""

import logging
import random
import time
from threading import Lock

from heapq import heappop, heappush, heapify

import pybitcointools

from gossip import stats
from gossip import token_bucket

logger = logging.getLogger(__name__)


class Node(object):
    """The Node class represents network peers in the gossip protocol.

    Attributes:
        NetHost (str): hostname or IP address identifying the node.
        SigningKey (str): a PEM formatted signing key.
        Identifier (str): an identifier for the node.
        Name (str): a short, human-readable name for the node.
        is_peer (bool): whether or not the node is treated as a peer.
            This is set from outside the Node class.
        Estimator (RoundTripEstimator): tracks network timing between nodes.
        MessageQ (TransmissionQueue): a transmission queue ordered by time
            to send.
        TokenBucket (token_bucket): limits the average rate of data flow.
        FixedRandomDelay (float): a random delay in the range of DelayRange.
        Delay (float): a random delay for the node using either a uniform
            or an exponential distribution depending on the value of the
            UseFixedDelay boolean. By default, a uniform random distribution
            is used.
        Stats (stats): tracks statistics associated with node communication.
        MissedTicks (int): tracks the number of time slices where no messages
            are received from the node. If MissedTicks exceeds 10, the node
            is considered disconnected (see Gossip._keepalive()).
        UseFixedDelay (bool): whether or not to use a uniform or exponential
            random distribution. If UseFixedDelay is True (default), a
            uniform distribution in DelayRange is used.
        DelayRange (list of floats): specifies the floor and ceiling for
            the uniform random value of FixedRandomDelay.
        DistributionLambda (float): the lambda value provided to the
            exponential random function if UsedFixedDelay is false.

    """
    UseFixedDelay = True
    DelayRange = [0.1, 0.4]
    DistributionLambda = 10.0

    def __init__(self,
                 address=(None, None),
                 identifier=None,
                 signingkey=None,
                 name=None,
                 rate=None,
                 capacity=None,
                 endpoint_address=(None, None)):
        """Constructor for the Node class.

        Args:
            address (ordered pair of str, int): address of the node in the
                form of (host, port).  This is the local address to which the
                node is bound.
            identifier (str): an identifier for the node.
            signingkey (str): used to create a signing key, in PEM format.
            name (str): a short, human-readable name for the node.
            rate (int): the number of tokens to be added to the TokenBucket
                per drip.
            capacity (int): the total capacity of tokens in the node's
                TokenBucket.
            endpoint_address (ordered pair of str, int): the publicly-
                reachable address of the node in the form of (host, port).
                If the node is publicly-reachable, this should be the same as
                address.  If not, this is the address at the NAT used to route
                to address.
        """

        self.NetHost = address[0]
        self.NetPort = address[1]
        self._endpoint_host = endpoint_address[0]
        self._endpoint_port = endpoint_address[1]

        self.SigningKey = signingkey
        self.Identifier = identifier

        self.Name = name if name else self.Identifier[:8]
        self.is_peer = False

        self.Estimator = RoundTripEstimator()
        self.MessageQ = TransmissionQueue()
        self.TokenBucket = token_bucket.TokenBucket(rate, capacity)

        self.FixedRandomDelay = random.uniform(*self.DelayRange)
        if self.UseFixedDelay:
            self.Delay = self._fixeddelay
        else:
            self.Delay = self._randomdelay
        self.Stats = None

        self.MissedTicks = 0

    @property
    def NetAddress(self):
        """Returns an ordered pair containing the host and port number of
        the node.
        """
        return (self.NetHost, self.NetPort)

    @property
    def endpoint_host(self):
        """
        Returns the endpoint host address, i.e., the externally-visible
        address.  If not set, it returns the net host as that is both the
        host address bound to as well as the externally-visible one.
        """
        return \
            self._endpoint_host \
            if self._endpoint_host is not None else self.NetHost

    @property
    def endpoint_port(self):
        """
        Returns the endpoint port, i.e., the externally-visible port.  If not
        set or zero, returns the net port as that is both the host port bound
        to as well as the externally-visible one.
        """
        if self._endpoint_port is None or self._endpoint_port == 0:
            return self.NetPort

        return self._endpoint_port

    @property
    def endpoint_address(self):
        """
        Returns an ordered pair containing the endpoint host and port of the
        node.
        """
        return (self.endpoint_host, self.endpoint_port)

    def __str__(self):
        return self.Name

    def _randomdelay(self):
        return random.expovariate(self.DistributionLambda)

    def _fixeddelay(self):
        return self.FixedRandomDelay

    def initialize_stats(self, localnode):
        """Initializes statistics collection for the node.

        Args:
            localnode (Node): the local node. Statistics are relative to
                the local node and the remote node.
        """
        self.Stats = stats.Stats(localnode.Name, self.Name)
        self.Stats.add_metric(stats.Value('Identifier', self.Identifier))
        self.Stats.add_metric(stats.Value('Address', "{0}:{1}".format(
            self.NetHost, self.NetPort)))
        self.Stats.add_metric(stats.Sample('MessageQueue',
                                           lambda: str(self.MessageQ)))
        self.Stats.add_metric(stats.Sample('MessageQueueLength',
                                           lambda: self.MessageQ.Count))
        self.Stats.add_metric(stats.Sample('RoundTripEstimate',
                                           lambda: self.Estimator.RTO))

    def enqueue_message(self, msg, now):
        """Enqueue a message for future delivery.

        System messages are queued for immediate delivery, others are
        queued at some point in the future determined by the configured
        delay.

        Args:
            msg (message): the message to enqueue.
            now (float): the current time.

        """
        timetosend = 0 if msg.IsSystemMessage else now + self.Delay()
        self.MessageQ.enqueue_message(msg, timetosend)

    def dequeue_message(self, msg):
        """Remove a message from the transmission queue.

        Args:
            msg (message): the message to remove.

        """
        return self.MessageQ.dequeue_message(msg)

    def get_next_message(self, now):
        """Removes the next sendable message from the queue and returns it.

        A message is sendable if it is a system message or if there are
        sufficient tokens in the token bucket to support the length of the
        message.

        Args:
            now (float): the current time.

        Returns:
            message: if a sendable message is found it is returned,
                otherwise None

        """
        if self.MessageQ.Count > 0:
            info = self.MessageQ.Head
            if info is None:
                return None

            (timetosend, msg) = info
            if timetosend < now:
                if msg.IsSystemMessage or self.TokenBucket.consume(len(msg)):
                    self.MessageQ.dequeue_message(msg)
                    return msg

        return None

    def message_delivered(self, msg, rtt):
        """Updates the RoundTripEstimator based on packet round trip
        time and dequeues the specified message.

        Args:
            msg (message): the message to remove.
            rtt (int): round trip time between outgoing packet and
                incoming packet.
        """
        self.Estimator.update(rtt)
        self.MessageQ.dequeue_message(msg)

    def message_dropped(self, msg, now=None):
        """Updates the RoundTripEstimator based on the assertion that
        the message has been dropped and re-enqueues the outgoing
        message for re-delivery.

        Args:
            msg (message): the message to re-send.
            now (int): current time since the epoch in seconds.
        """
        if not now:
            now = time.time()

        self.Estimator.backoff()
        self.enqueue_message(msg, now)

    def reset_ticks(self):
        """Resets the MissedTicks counter to zero.
        """
        self.MissedTicks = 0

    def bump_ticks(self):
        """Increments the MissedTicks counter.
        """
        self.MissedTicks += 1

    def dump_peer_stats(self, identifier, metrics):
        """Dumps statistics for the node to the log.

        Args:
            identifier (str): the batchid for logging statistics.
            metrics (list of str): a list of metrics to dump.
        """
        self.Stats.dump_stats(identifier, metrics)

    def reset_peer_stats(self, metrics):
        """Resets statistics for the node.

        Args:
            metrics (list of str): a list of metrics to reset.
        """
        self.Stats.reset_stats(metrics)

    def _clone(self):
        """Create a copy of the node, primarily useful for debugging
        multiple instances of a gossiper in one process.
        """
        return Node(address=self.NetAddress, identifier=self.Identifier)

    def signing_address(self):
        return pybitcointools.pubtoaddr(
            pybitcointools.privtopub(self.SigningKey))


class RoundTripEstimator(object):
    """The RoundTripEstimator estimates round trip message time based on
       measured round-trip time.
    """

    # Minimum and Maximum RTO measured in seconds
    MinimumRTO = 1.0
    MaximumRTO = 60.0
    BackoffRate = 2.0

    MinResolution = 0.025
    ALPHA = 0.125
    BETA = 0.25
    K = 4.0

    def __init__(self):
        self.RTO = self.MinimumRTO
        self._SRTT = 0.0
        self._RTTVAR = 0.0

    def update(self, measuredrto):
        """Updates estimator values based on measured round trip message
        time.

        Args:
            measuredrto (int): actual time from packet transmission to
                ack reception.
        """

        if self._RTTVAR == 0.0:
            self._SRTT = measuredrto
            self._RTTVAR = measuredrto * 0.5
        else:
            self._RTTVAR = (1.0 - self.BETA) * self._RTTVAR + self.BETA * abs(
                self._SRTT - measuredrto)
            self._SRTT = (1.0 -
                          self.ALPHA) * self._SRTT + self.ALPHA * measuredrto

        self.RTO = self._SRTT + max(self.MinResolution, self.K * self._RTTVAR)
        self.RTO = max(self.MinimumRTO, min(self.MaximumRTO, self.RTO))

    def backoff(self):
        """Increases the round-trip estimate by a factor of BackoffRate
        (until reaching MaximumRTO).
        """
        self._SRTT = 0.0
        self._RTTVAR = 0.0

        self.RTO = min(self.RTO * self.BackoffRate, self.MaximumRTO)


class TransmissionQueue(object):
    """Implements a transmission queue ordered by time to send. A
    heap is used to order message identifiers by transmission time.

    Note:
        The heap is not authoritative. Because messages can be queued
        and dequeued, elements in the heap might become out of date.
    """

    def __init__(self):
        self._messages = {}
        self._times = {}  # this allows reinsertion of a message
        self._heap = []
        self._lock = Lock()

    def __str__(self):
        idlist = self._times.keys()
        if len(idlist) > 4:
            idlist = idlist[:4]
            idlist.append('...')

        return '[' + ', '.join([ident[:8] for ident in idlist]) + ']'

    def enqueue_message(self, msg, timetosend):
        """Adds a message to the transmission queue.

        At most one instance of a message can exist in the queue at a
        time however multiple references may exist in the heap.

        Args:
            msg (message): the message to send.
            timetosend (float): python time when message should be sent,
                0 for system message.
        """
        with self._lock:
            messageid = msg.Identifier
            if (messageid not in self._messages and
                    messageid not in self._times):
                self._messages[messageid] = msg
                self._times[messageid] = timetosend

                heappush(self._heap, (timetosend, messageid))
            else:
                logger.debug('tried to enqueue a message already '
                             'enqueued. messageid %s, self._messages %s',
                             messageid,
                             self._messages)

    def dequeue_message(self, msg):
        """Removes a message from the transmission queue if it exists.

        Rebuild the heap if necessary, but do not explicitly remove
        the entry from the heap.

        Args:
            msg (message): the message to remove.
        """
        with self._lock:
            self._messages.pop(msg.Identifier, None)
            self._times.pop(msg.Identifier, None)

            self._buildheap()

    @property
    def Head(self):
        """Returns the next message in the transmission queue and the time
        when it should be sent.
        """
        with self._lock:
            self._trimheap()
            if len(self._heap) == 0:
                return None

            (timetosend, messageid) = self._heap[0]
            assert messageid in self._messages
            assert messageid in self._times

            return (timetosend, self._messages[messageid])

    @property
    def Count(self):
        """Returns a count of the number of messages in the queue.
        """
        return len(self._times)

    @property
    def Messages(self):
        """Returns a list of the message identifiers in the queue, primarily
        used for debugging.
        """
        return self._times.keys()

    def _trimheap(self):
        """
        Remove entries in the heap that are no longer valid. Since the heap
        is not rebuilt when messages are dequeued, there may be invalid
        entries in the heap.
        """

        while True:
            # make sure we haven't emptied the heap
            if len(self._heap) == 0:
                return
            (timetosend, messageid) = self._heap[0]

            # and see if the pair in the heap holds the current tranmission
            # time for the message id
            if (messageid in self._times
                    and self._times[messageid] == timetosend):
                assert messageid in self._messages
                return

            heappop(self._heap)

    def _buildheap(self):
        """
        Rebuild the heap if necessary. This should only happen when
        a large number of messages have been dequeued
        """

        if 2 * len(self._times) < len(self._heap):
            self._heap = []
            for messageid, timetosend in self._times.iteritems():
                assert messageid in self._messages
                self._heap.append((timetosend, messageid))

            heapify(self._heap)
