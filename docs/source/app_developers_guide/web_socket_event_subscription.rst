*****************************************
About Web Sockets and Event Subscriptions
*****************************************

Applications can subscribe to events by using a web socket connection to the
REST API, but there are several limitations:

* Only Sawtooth block-commit and state-delta events are supported.

* You cannot specify a single event type or use filters to fine-tune the
  results. A web socket subscription returns all events.

* Event catch-up is not available.

We recommend using ZMQ for event subscription, as described in
:doc:`zmq_event_subscription`.

For information on using web sockets, see
:doc:`../rest_api/state_delta_websockets`.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
