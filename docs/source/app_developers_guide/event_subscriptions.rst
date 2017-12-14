*********************
Subscribing to Events
*********************

As blocks are committed to the blockchain, an application developer
may want to receive information on events such as the creation of a new block,
switching to a new fork, or application-specific events defined by a
transaction family.

Client applications can subscribe to Hyperledger Sawtooth events
using ZMQ and Protobuf messages. The general process is:

1. Construct a subscription that includes the event type and any filters

#. Submit the event subscription as a message to the validator

#. Wait for a response from the validator

#. Start listening for events

For information on the architecture of events in Sawtooth, see
:doc:`/architecture/events_and_transactions_receipts`.

Requirements
============

To subscribe to Sawtooth events, a client application can use any language
that provides the following items:

- ZMQ library

- Protobuf library

In addition, the required Sawtooth protobuf messages must be compiled
for the chosen language.

This section uses Python examples to show the event-subscription procedure,
but the process is similar for any imperative programming language that meets
these requirements.

Constructing a Subscription
===========================

An event subscription consists of an event type (the name of the event)
and an optional list of filters for this event type.

Event Type
----------

Each Sawtooth event has an ``event_type`` field that is used to
determine how opaque data has been serialized and what
transparent attributes to expect.
An event is “in a subscription” if the event’s ``event_type`` field
matches the subscription’s ``event_type`` field, and the event matches
any filters that are in the event subscription.

The core Sawtooth events are prefixed with ``sawtooth/``:

- ``sawtooth/block-commit``

- ``sawtooth/state-delta``

Each transaction family can define its own events. The convention
is to prefix the event type with the name of the transaction family,
such as ``xo/create``.

Event Filters
-------------

An event subscription can include one or more event filters, which direct the
validator to include events of a given type based on the event's transparent
attributes. If multiple event filters are included in a subscription,
only events that pass all filters will be received.

An event filter consists of a key and a match string. Filters apply only to
the event attributes that have the same key as the filter. The filter's match
string is compared against the attribute's value according to the type of
event filter.

An event filter can either be a simple filter (an exact match to a string)
or a regex filter. In addition, the filter can specify the match type of
ANY (one or more) or ALL.  The following filters are supported:

- ``SIMPLE_ANY``

- ``SIMPLE_ALL``

- ``REGEX_ANY``

- ``REGEX_ALL``

For example filters, see :ref:`Events <events-reference-label>`.

Event Protobuf Message
----------------------

Event subscriptions are represented with the following protobuf messages,
which are defined in the ``events.proto`` file.

.. code-block:: python

    message EventSubscription {
      string event_type = 1;
      repeated EventFilter filters = 2;
    }

    message EventFilter {
      string key = 1;
      string match_string = 2;

      enum FilterType {
          FILTER_TYPE_UNSET = 0;
          SIMPLE_ANY = 1;
          SIMPLE_ALL = 2;
          REGEX_ANY  = 3;
          REGEX_ALL  = 4;
        }
        FilterType filter_type = 3;
    }

Example: Subscribing to State Deltas within a Namespace
-------------------------------------------------------

This example constructs an event subscription for state deltas
(a single change in state at a given address)
within the namespace ``"abcdef"``.

.. code-block:: python

    subscription = EventSubscription(
        event_type="sawtooth/state-delta",
        filters=[
            # Filter to only addresses in the "abcdef" namespace using a regex
            EventFilter(
                key="address",
                match_string="abcdef.*",
                filter_type=EventFilter.REGEX_ANY)
        ])

Submitting an Event Subscription
================================

After constructing a subscription, send the subscription request to the
validator. The following example connects to the validator's URL using ZMQ,
then submits the subscription request.

.. code-block:: python

    # Setup a connection to the validator
    ctx = zmq.Context()
    socket = ctx.socket(zmq.DEALER)
    socket.connect(url)

    # Construct the request
    request = ClientEventsSubscribeRequest(
        subscriptions=[subscription]).SerializeToString()

    # Construct the message wrapper
    correlation_id = "123" # This must be unique for all in-flight requests
    msg = Message(
        correlation_id=correlation_id,
        message_type=CLIENT_EVENTS_SUBSCRIBE_REQUEST,
        content=request)

    # Send the request
    socket.send_multipart([msg.SerializeToString()])

Receiving the Response
======================

The validator will return a response indicating whether the subscription
was successful. The following example receives the response and verifies
the status.

.. code-block:: python

    # Receive the response
    resp = socket.recv_multipart()[-1]

    # Parse the message wrapper
    msg = Message()
    msg.ParseFromString(resp)

    # Validate the response type
    if msg.message_type != CLIENT_EVENTS_SUBSCRIBE_RESPONSE:
        print("Unexpected message type")

    # Parse the response
    response = ClientEventsSubscribeResponse()
    response.ParseFromString(msg.content)

    # Validate the response status
    if response.status != ClientEventsSubscribeResponse.OK:
      print("Subscription failed: {}".format(response.response_message))

Listening for Events
====================

If the event subscription was successful, events are sent to the subscriber.
In order to limit network traffic, individual events are wrapped in an
event list message before being sent.

The following example listens for events and prints them indefinitely.

.. code-block:: python

    while True:
      resp = socket.recv_multipart()[-1]

      # Parse the message wrapper
      msg = Message()
      msg.ParseFromString(resp)

      # Validate the response type
      if msg.message_type != CLIENT_EVENTS:
          print("Unexpected message type")

      # Parse the response
      events = EventList()
      events.ParseFromString(msg.content)

      for event in events:
        print(event)

Correlating Events to Blocks
============================

All events originate from some block and are only sent to the subscriber
once the block is committed and state is updated. As a result, events can be
treated as output from processing and committing blocks.

To match an event with the block it originated from, subscribe to the
``block-commit`` event. All lists of events received from the validator will
contain a ``block-commit`` event for the block that the events came from.

.. Note::

  For forking networks, we recommend subscribing to ``block-commit`` events
  in order to watch for network forks and react appropriately. Without
  a subscription to ``block-commit`` events, there is no way to determine
  whether a fork has occurred.

Requesting Event Catch-Up
=========================

An event subscription can request "event catch-up" information on all
historical events that have occurred since the creation of a specific
block or blocks.

To use this feature, set the ``last_known_block_ids`` field in the
``ClientEventsSubscribeRequest`` to a list of known block ids.
The validator will bring the client up to date by doing the following:

- Filter the list to include only the blocks on the current chain

- Sort the list by block number

- Send historical events from all blocks since the most recent block,
  one block at a time

If no blocks on the current chain are sent, the subscription will fail.

The following example submits a subscription request that includes
event catch-up.

.. code-block:: python

    # Setup a connection to the validator
    ctx = zmq.Context()
    socket = ctx.socket(zmq.DEALER)
    socket.connect(url)

    # Construct the request
    request = ClientEventSubscribeRequest(
        subscriptions=[subscription],
        last_known_block_ids=['000…', 'beef…'])

    # Construct the message wrapper
    correlation_id = "123" # This must be unique for all "in-flight requests
    msg = Message(
        correlation_id=correlation_id,
        message_type=CLIENT_EVENTS_SUBSCRIBE_REQUEST,
        content=request)

    # Send the request
    socket.send_multipart([msg.SerializeToString()])

Unsubscribing to Events
=======================

To unsubscribe to events, send a unsubscribe request with no arguments,
then close the ZMQ socket.

This example submits an unsubscribe request.

.. code-block:: python

    # Construct the request
    request = ClientEventsUnsubscribeRequest()

    # Construct the message wrapper
    correlation_id = "123" # This must be unique for all "in-flight requests
    msg = Message(
        correlation_id=correlation_id,
        message_type=CLIENT_EVENTS_UNSUBSCRIBE_REQUEST,
        content=request)

    # Send the request
    socket.send_multipart([msg.SerializeToString()])

The following example receives the validator's response to an unsubscribe
request, verifies the status, and closes the ZMQ connection.

.. code-block:: python

    # Receive the response
    resp = socket.recv_multipart()[-1]

    # Parse the message wrapper
    msg = Message()
    msg.ParseFromString(resp)

    # Validate the response type
    if msg.message_type != CLIENT_EVENTS_UNSUBSCRIBE_RESPONSE:
        print("Unexpected message type")

    # Parse the response
    response = ClientEventsUnsubscribeResponse()
    response.ParseFromString(msg.content)

    # Validate the response status
    if response.status != ClientEventsUnsubscribeResponse.OK:
      print("Unsubscription failed: {}".format(response.response_message))

    # Close the connection to the validator
    socket.close()

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
