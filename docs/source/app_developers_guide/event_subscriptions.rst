*********************
Subscribing to Events
*********************

As blocks are committed to the blockchain, an application developer may want to
receive information on events such as the creation of a new block or switching
to a new fork. This includes application-specific events that are defined by a
custom transaction family.

Hyperledger Sawtooth supports creating and broadcasting events. Event
subscription allows an application to perform the following functions:

* Subscribe to events that occur related to the blockchain

* Communicate information about transaction execution back to clients without
  storing that data in state

* Perform event catch-up to gather information about state changes from a
  specific point on the blockchain

An application can react immediately to each event or store event data for
later processing and analysis. For example, a `state delta processor` could
store state data in a reporting database for analysis and processing, which
provides access to state information without the delay of requesting state data
from the validator. For examples, see the `Sawtooth Supply Chain
<https://github.com/hyperledger/sawtooth-supply-chain>`_
or `Sawtooth Marketplace <https://github.com/hyperledger/sawtooth-marketplace>`_
repository.

This section describes the structure of events and event subscriptions, then
explains how to use the validator's `ZeroMQ <http://zeromq.org>`_ messaging
protocol (also called ZMQ or 0MQ) to subscribe to events.

.. note::

   Web applications can also subscribe to events with a web socket connection to
   the REST API, but there are several limitations for this method. For more
   information, see :doc:`web_socket_event_subscription`.


.. toctree::
   :maxdepth: 2

   about_events.rst
   about_event_subscriptions.rst
   zmq_event_subscription.rst
   web_socket_event_subscription.rst


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
