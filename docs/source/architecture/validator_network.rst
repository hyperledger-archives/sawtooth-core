*****************
Validator Network
*****************

The network layer is responsible for communication between validators in a
Sawtooth network, including performing initial connectivity, peer discovery,
and message handling. Upon startup, validator instances begin listening on a
specified interface and port for incoming connections. Upon connection and
peering, validators exchange messages with each other based on the rules of a
gossip or epidemic [#f1]_ protocol.

A primary design goal is to keep the network layer as self-contained as
possible. For example, the network layer should not need knowledge of the
payload of application messages, nor should it need application-layer provided
data to connect to peers or to build out the connectivity of the network.
Conversely, the application should not need to understand implementation
details of the network in order to send and receive messages.

Services
========

The choice of 0MQ provides considerable flexibility in both available
connectivity patterns and the underlying capabilities of the transport layer
(IPv4, IPv6, etc.)

We have adopted the 0MQ Asynchronous Client/Server Pattern [#f2]_ which consists
of a 0MQ ROUTER socket on the server side which listens on a provided
endpoint, with a number of connected 0MQ DEALER sockets as the connected
clients. The 0MQ guide describes the features of this pattern as follows:

- Clients connect to the server and send requests.
- For each request, the server sends 0 or more replies.
- Clients can send multiple requests without waiting for a reply.
- Servers can send multiple replies without waiting for new requests.


.. figure:: ../images/multiple_dealer_to_router.*
   :width: 50%
   :align: center
   :alt: Multiple dealer to router diagram

   Multiple DEALER to ROUTER socket pattern


|

States
======

We define three states related to the connection between any two validator
nodes:

- Unconnected
- Connected - A connection is a required prerequisite for peering.
- Peered - A bidirectional relationship that forms the base case for
  application level message passing (gossip).


Wire Protocol
=============
We have standardized on protobuf serialization for any structured messages that
need to be passed over the network. All payloads to or from the application
layer are treated as opaque.

CONNECT

Connect is the mechanism for initiating the connection to the remote node.
Connect performs a basic 0MQ DEALER->ROUTER connection to the remote node and
exchanges identity information for the purpose of supporting a two-way
conversation. Connections sit atop 0MQ sockets and allow the DEALER/ROUTER
conversation.

PING

Ping messages allow for keep alive between ROUTER and DEALER sockets.

PEER

Peer requests establish a bidirectional peering relationship between the two
nodes. A Peer request can be rejected by the remote node. If a peer request is
rejected, the expectation is that a node attempts to connect with other
nodes in the network via some strategy until the peering minimum connectivity
threshold for that node is reached. If possible, the bi-directional
relationship occurs over the already established 0MQ socket between
DEALER and ROUTER.

GET_PEERS

Returns a list of peers of a given node. This can be performed in a basic
Connected state and does not require peering to have occurred. The intent is to
allow a node attempting to reach its minimum connectivity peering threshold to
build a view of active candidate peers via a neighbor of neighbors approach.

BROADCAST(MSG)

Transmits an application message to the network following a 'gossipy' pattern.
This does not guarantee 100% delivery of the message to the whole network, but
based on the gossip parameters, nearly complete delivery is likely. A node
only accepts messages for broadcast/forwarding from peers.

SEND(NODE, MSG)

Attempts to send a message to a particular node over the bidirectional 0MQ
connection. Delivery is not guaranteed. If a node has reason to believe that
delivery to the destination node is impossible, it can return an error response.
A node only accepts a message for sending from peer nodes.

REQUEST(MSG)

A request is a special type of broadcast message that can be examined and
replied to, rather than forwarded. The intent is for the application layer to
construct a message payload which can be examined by a special request handler
and replied to, rather than forwarded on to connected peers. If the application
layer reports that the request can’t be satisfied, the message will be
forwarded to peers per the rules of a standard broadcast message. A node
only accepts request messages from peer nodes.

UNPEER

Breaks the peering relationship between nodes. This may occur in several
scenarios, for example a node leaving the network (nodes may also silently
leave the network, in which case their departure will be detected by the
failure of the ping/keepalive). An unpeer request does not necessarily imply a
disconnect.

DISCONNECT

Breaks the wire protocol connection to the remote node. Informs the ROUTER end
to clean up the connection.

Peer Discovery
==============

A bidirectional peering via a neighbor of neighbors approach gives reliable
connectivity (messages delivered to all nodes >99% of the time based on random
construction of the network).

Peer connections are established by collecting a suitable population of
candidate peers through successive CONNECT/GET_PEERS calls
(neighbors of neighbors). The connecting validator then selects a candidate
peer randomly from the list and attempts to connect and peer with it. If this
succeeds, and the connecting validator has reached minimum connectivity, the
process halts. If minimum connectivity has not yet been reached, the validator
continues attempting to connect to new candidate peers, refreshing its view of
the neighbors of neighbors if it exhausts candidates.

.. figure:: ../images/bidirectional_peering.*
   :width: 75%
   :align: center
   :alt: Output of bidirectional peering with targeted connectivity of 4.

   Output of bidirectional peering with targeted connectivity of 4.

|

The network component continues to perform a peer search if its number of
peers is less than the minimum connectivity. The network component rejects
peering attempts if its number of peers is equal to or greater than the maximum
connectivity. Even if maximum peer connections is reached, a network service
should still accept and respond to a reasonable number of connections (for the
purposes of other node topology build outs, etc.)

Related Components
==================
.. figure:: ../images/related_components.*
   :width: 75%
   :align: center
   :alt: Related Components Diagram.

|

Message Delivery
================

The network delivers application messages (payloads received via BROADCAST
or SEND) to the application layer. The network also performs a basic
validation of messages prior to forwarding by calling a handler in the Message
Validation component.

When the network receives a REQUEST message, it calls a provided handler
(a "Responder”, for example) to determine if the request can be
satisfied. If so, the expectation is that the application layer generates a
SEND message with a response that satisfies the request. In this condition, the
network layer does not continue to propagate the REQUEST message to the network.

In the case where a node could not satisfy the request, the node stores who
it received the request from and BROADCASTs the request on to its peers. If that
node receives a SEND message with the response to the request, it forwards
the SEND message back to the original requester.

The network accepts application payloads for BROADCAST, SEND, and REQUEST
from the application layer.

Network Layer Security
======================

0MQ includes a TLS [#f3]_ like certificate exchange mechanism and protocol
encryption capability which is transparent to the socket implementation.
Support for socket level encryption is currently implemented with
server keys being read from the validator.toml config file. For each client,
ephemeral certificates are generated on connect. If the server key pair is not
configured, network communications between validators will not be authenticated
or encrypted.

.. rubric:: Footnotes

.. [#f1] http://web.mit.edu/devavrat/www/GossipBook.pdf
.. [#f2] http://zguide.zeromq.org/php:chapter3#toc19
.. [#f3] https://github.com/zeromq/pyzmq/blob/master/examples/security/ironhouse.py
