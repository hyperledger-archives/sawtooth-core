*****************************************
State Delta Subscriptions via Web Sockets
*****************************************

As transactions are committed to the blockchain, an app developer may be
interested in receiving events related to the changes in state that result.
These events, `StateDeltaEvents`, include information about the advance of the
blockchain, as well as state changes that can be limited to specific address
spaces in the global state.

An application can subscribe to receive these events via a web socket, provided
by the REST API component.  For example, a single-page JavaScript application may
open a web socket connection and subscribe to a particular transaction family's
state values, using the incoming events to re-render portions of the display.

.. note::

   All examples here are written in JavaScript, and assumes the Sawtooth REST
   API is reachable at `localhost`.

Opening a Web Socket
====================

The application developer must first open a web socket. This is accomplished
by using standard means.  In the case of in-browser JavaScript:

.. code-block:: javascript

   let ws = new WebSocket('ws:localhost:8008/subscriptions')

If the REST API is running, it should trigger an event on the web socket's
`onopen` handler.

Subscribing to State Changes
============================

In order to subscribe to an address space in the global state, first a message
needs to be sent on the socket with the list of prefixes. It is a best-practice
to send this message as part of the web socket's `onopen` handler.

In the following example, we'll subscribe to changes in the XO family:

.. code-block:: javascript

  ws.onopen = () => {
    ws.send(JSON.stringify({
      'action': 'subscribe',
      'address_prefixes': ['5b7349']
    }))
  }

This message will begin the subscription of events as of the current block.  If
you are interested in the state prior to the point of subscription, you should
fetch the values of state via the REST API's `/state` endpoint.

Subscriptions may be changed by sending a subscribe message at later time while
the websocket is open.  It is up to the client to maintain the list of address
prefixes of interest.  Any subsequent subscriptions will overwrite this list.


Events
======

Once subscribed, events will be received via the web socket's `onmessage`
handler. The event data is a JSON string, which looks like the following:

.. code-block:: javascript

  {
    "block_num": 8,
    "block_id": "ab7cbc7a...",
    "previous_block_id": "d4b46c1c...",
    "state_changes": [
      {
        "type": "SET",
        "value": "oWZQdmxqcmsZU4w"=,
        "address": "1cf126613a..."
      },
      ...
    ]
  }

There is an entry in the `state_changes` array for each address that matches the
`address_prefixes` provided during the subscribe action.  The type is either
"SET" or "DELETE".  In the case of "SET" the value is base-64 encoded (like the
`/state` endpoint's response).  In the case of "DELETE", only the address is
provided. If you are using a transaction family that supports deletes, you'll
need to keep track of values via address, as well.

Missed Events
-------------

In the case where you have missed an event, a request can be sent via the web
socket for a particular block's changes.  You can use the `previous_block_id`
from the current event to request the previous block's events, for example.
Send the following message:

.. code-block:: javascript

  ws.send(JSON.stringify({
    'action': 'get_block_deltas',
    'block_id': 'd4b46c1c...',
    'address_prefixes': ['5b7349']
  }))

The event will be returned in the same manner as any other event, so it is
recommended that you push the events on to a stack before processing them.

If the block id does not exist, the following error will be returned:

.. code-block:: javascript

  {
    "error": "Must specify a block id"
  }

Unsubscribing
=============

To unsubscribe, you can either close the web socket, or if you want to
unsubscribe temporarily, you can send an unsubscribe action:

.. code-block:: javascript

  ws.send(JSON.stringify({
    'action': 'unsubscribe'
  }))


Errors and Warnings
===================

An open, subscribed web socket may receive the following errors and warnings:

* the validator is unavailable
* an unknown action was requested

If the validator is unavailable to the REST API process, a warning will be sent
in lieu of a state delta event:

.. code-block:: javascript

  {
    "warning": "Validator unavailable"
  }

If an unrecognized action is sent on to the server via the websocket, an error
message will be sent back:

.. code-block:: javascript

  {
    "error": "Unknown action \"bad_action\""
  }


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
