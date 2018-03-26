********************************
Using ZMQ to Subscribe to Events
********************************

Client applications can subscribe to Hyperledger Sawtooth events using the
validator's `ZMQ <http://zeromq.org>`_ messaging protocol. The general
subscription process is as follows:

#. Construct a subscription that includes the event type and optional filters
   (zero or more).

#. Submit the event subscription as a message to the validator.

#. Wait for a response from the validator.

#. Start listening for events.

This section summarizes event subscriptions, then explains the procedure for
event subscription. It also describes the following operations:

* Correlating events to blocks
* Requesting event catch-up
* Unsubscribing to events

.. note::

   This procedure uses Python examples to show how to subscribe to events. The
   process is similar for any imperative programming language that meets these
   requirements. A client application can use any language that provides a ZMQ
   library and a protobuf library. In addition, the required Sawtooth protobuf
   messages must be compiled for the chosen language.

The following steps assume that the XO transaction family has a ``create`` event
that is sent when a game has been created, as in this example:

.. code-block:: python

     context.add_event(
         "xo/create", {
             'name': name,
             'creator': signer_public_key
     })


Step 1: Construct a Subscription
================================

An application can use the ``EventSubscription`` protobuf message to construct
an event subscription. For example, in the ``sawtooth`` namespace, the
application could subscribe to either a ``block-commit`` or ``state-delta``
event (or both) in the ``sawtooth`` namespace, using either a ``SIMPLE`` or
``REGEX`` filter.

The following example constructs an event subscription for state-delta events
(changes in state) with a ``REGEX_ANY`` filter for events from the XO
transaction family.

.. code-block:: python

    subscription = EventSubscription(
        event_type="sawtooth/state-delta",
        filters=[
            # Filter to only addresses in the "xo" namespace using a regex
            EventFilter(
                key="address",
                match_string="5b7349.*",
                filter_type=EventFilter.REGEX_ANY)
        ])

Note that the match string specifies the ``xo`` namespace as ``5b7349``, because
the namespace is determined by
``hashlib.sha512('xo'.encode("utf-8")).hexdigest()[0:6]``. For more information,
see "Addressing" in the Go, Javascript, or Python SDK tutorial:

* Go: :doc:`/_autogen/sdk_TP_tutorial_go`
* JavaScript: :doc:`/_autogen/sdk_TP_tutorial_js`
* Python: :doc:`/_autogen/sdk_TP_tutorial_python`


Step 2: Submit the Event Subscription
=====================================

After constructing a subscription, submit the subscription request to the
validator. The following example connects to the validator using ZMQ, then
submits the subscription request.

.. code-block:: python

    # Setup a connection to the validator
    ctx = zmq.Context()
    socket = ctx.socket(zmq.DEALER)
    socket.connect(url)

    # Construct the request
    request = ClientEventsSubscribeRequest(
        subscriptions=[subscription]).SerializeToString()

    # Construct the message wrapper
    correlation_id = "123" # This must be unique for all in-process requests
    msg = Message(
        correlation_id=correlation_id,
        message_type=CLIENT_EVENTS_SUBSCRIBE_REQUEST,
        content=request)

    # Send the request
    socket.send_multipart([msg.SerializeToString()])

.. note::

   For information about ``ClientEventsSubscribeRequest``, see
   :doc:`about_event_subscriptions`.


Step 3: Receiving the Response
==============================

After submitting the subscription request, wait for a response from the
validator. The validator will return a response indicating whether the
subscription was successful.

The following example receives the response and verifies the status.

.. code-block:: python

    # Receive the response
    resp = socket.recv_multipart()[-1]

    # Parse the message wrapper
    msg = Message()
    msg.ParseFromString(resp)

    # Validate the response type
    if msg.message_type != CLIENT_EVENTS_SUBSCRIBE_RESPONSE:
        print("Unexpected message type")
        return

    # Parse the response
    response = ClientEventsSubscribeResponse()
    response.ParseFromString(msg.content)

    # Validate the response status
    if response.status != ClientEventsSubscribeResponse.OK:
      print("Subscription failed: {}".format(response.response_message))
      return


Step 4: Listening for Events
============================

After the event subscription request has been sent and accepted, events will
arrive on the ZMQ socket. The application must start listening for these events.

.. note::

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
          return

      # Parse the response
      events = EventList()
      events.ParseFromString(msg.content)

      for event in events:
        print(event)


.. _correlate-events-to-blocks-label:

Correlating Events to Blocks
============================

An event originates from a specific block. That is, an event is sent to the
subscriber only when the block is committed and state is updated. As a result,
events can be treated as output from processing and committing blocks.

An application can subscribe to both ``sawtooth/block-commit`` and
``sawtooth/state-delta`` events to match state changes with the block
in which the changes occurred.

All lists of ``block-commit`` events received from the validator will contain
only a single ``block-commit`` event for the block that the events came from.

.. important::

   For forking networks, we recommend subscribing to ``block-commit`` events
   in order to watch for network forks and react appropriately. Without
   a subscription to ``block-commit`` events, there is no way to determine
   whether a fork has occurred.

   In addition, the best practice is to wait to react to these events until a
   number of blocks have been committed on the given fork. This provides some
   confidence that you won't need to revert those changes because you switched
   to a different fork.


.. _event-catch-up-label:

Requesting Event Catch-Up
=========================

An event subscription can request "event catch-up" information on all historical
events that have occurred since the creation of a specific block or blocks.

The ``ClientEventsSubscribeRequest`` protobuf message takes a list of block IDs
(``last_known_block_ids``), which can be used to provide the last block ID that
a client has seen. If blocks have been committed after that block, the missed
events will be sent in the order they would have occurred.

.. note::

   Block IDs are available in ``sawtooth/block-commit`` events. In order to
   correlate event catch-up information, the application must subscribe to
   ``sawtooth/block-commit`` events, as described in the previous section.

The validator performs the following actions to bring the client up to date:

#. Filters the list to include only the blocks on the current chain

#. Sorts the list by block number

#. Sends historical events from all blocks since the most recent block,
   one block at a time

.. note::

   The subscription fails if no blocks on the current chain are sent.

The following example submits a subscription request that includes event
catch-up.

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
    correlation_id = "123" # This must be unique for all in-process requests
    msg = Message(
        correlation_id=correlation_id,
        message_type=CLIENT_EVENTS_SUBSCRIBE_REQUEST,
        content=request)

    # Send the request
    socket.send_multipart([msg.SerializeToString()])

If a fork occurred in a missed event, one or more known block IDs may be
"gone". In this case, use the information in
:ref:`correlate-events-to-blocks-label` to determine the current state of the
blockchain.


Unsubscribing to Events
=======================

To unsubscribe to events, send a ``ClientEventsUnsubscribeRequest`` with no
arguments, wait for the response, then close the ZMQ socket.

This example submits an unsubscribe request.

.. code-block:: python

    # Construct the request
    request = ClientEventsUnsubscribeRequest()

    # Construct the message wrapper
    correlation_id = "123" # This must be unique for all in-process requests
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
