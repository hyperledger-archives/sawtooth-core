*********************
Subscribing to Events
*********************

Subscribing to **Hyperledger Sawtooth** events using ZMQ and Protobuf messages
is relatively straightforward. See the
:doc:`events architecture documentation</architecture/events_and_transactions_receipts>`
for more information on the structure of events.


Requirements
============

Subscribing to Sawtooth events can be done in any language, provided the
following are available.

- A ZMQ library
- A Protobuf library
- The compiled Sawtooth protobuf messages for the chosen language

The following examples will be provided in Python, but the process should be
similar for any imperative language.


Constructing a Subscription
===========================

Before submitting any messages to a validator, we must first specify the events
of interest by constructing one or more event subscriptions. Event subscriptions
consist of two parts:

1. The event type, which is the name of the event of interest.
2. A list of filters for this event type.

Event Type
----------

All events within Sawtooth have an ``event_type`` field which is used to
determine how opaque data has been serialized and what transparent attributes to
expect. This event type is unique across the network. For example, block commit
events have the event type ``"sawtooth/block-commit"``.

Event Filters
-------------

Event filters can be included in a subscription instruct the validator to filter
events of a given type based on its transparent attributes. If multiple event
filters are included in a subscription, only events that pass all filters will
be received.

Event filters consist of a key and a match string. Filters only apply to event
attributes that have the same key as the filter. When applying a filter to an
attribute, the filter's match string is compared against the attribute's value
according to the type of event filter.

If the filter is a ``SIMPLE`` filter, the event passes if the attribute's value
is identical to the filter's match string. If the filter is a ``REGEX`` filter,
the event passes if the attribute's value matches the regex stored in the
filter's match string.

Since events can have multiple attributes with the same key, all the existing
filters can operate in two modes: ``ANY`` and ``ALL``. In ``ANY`` mode, an event
passes the filter if **any** of the attributes in the event with the same key as
the filter pass. In ``ALL`` mode, an event passes the filter if and only if
**all** of the attributes in the event with the same key as the filter pass.

Event subscriptions are represented with the following protobuf messages, which
are defined in the ``events.proto`` file::

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

The following example constructs an event subscription for state deltas within
the namespace ```"abcdef"``:

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

Once subscriptions have been constructed for the events of interest, an event
subscription request can be sent to the validator. The following example
connects to the validator using ZMQ and then submits the subscription request:

.. code-block:: python

    # Setup a connection to the validator
    ctx = zmq.Context()
    socket = ctx.socket(zmq.DEALER)
    socket.connect(url)

    # Construct the request
    request = ClientEventsSubscribeRequest(
        subscriptions=[subscription]).SerializeToString()

    # Construct the message wrapper
    correlation_id = "123" # This must be unique for all "in-flight requests
    msg = Message(
        correlation_id=correlation_id,
        message_type=CLIENT_EVENTS_SUBSCRIBE_REQUEST,
        content=request)

    # Send the request
    socket.send_multipart([msg.SerializeToString()])

After sending the request, the validator will return a response indicating
whether or not the subscription was successful. The following example receives
the response and verifies the status:

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

If the event subscription was successful, events will begin to be published to
the connection. In order to limit network traffic, individual events are wrapped
in an event list message prior to being sent. The following example listens for
events and prints them indefinitely:

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
----------------------------

Events are only created and published on block boundaries and can be treated as
an output from processing and committing blocks. Therefore, events can
be correlated with block they originated from by including a block commit
subscription when subscribing. If a block commit subscription is included, then
all lists of events received from the validator, will contain a block commit
event for the block the events came from.

.. warning::

    In forking networks, it is recommended that subscribers always include a
    block commit subscription with the subscription request. This way the
    subscriber can monitor for forks on the network and react appropriately.
    Without a block commit subscription, there is no way to determine whether
    a fork has occurred.

Event Catch-Up
--------------

When subscribing to events, it is also possible to request that all historical
events since some known block be sent upon successful subscription. To use this
feature, set the ``last_known_block_ids`` field in the
``ClientEventsSubscribeRequest`` to a list of known block ids. This validator
will filter this list to only include blocks on the current chain, sort it by
block number, and then send historical events from all blocks since the most
recent block. If no blocks on the current chain are sent, the subscription will
fail.
