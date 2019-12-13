*************************
About Event Subscriptions
*************************

An application can use event subscriptions to tell the validator to supply
information about changes to the blockchain.

An event subscription consists of an event type (the name of the event) and an
optional list of filters for this event type. If an event is in one of your
subscriptions, you will receive the event when the validator broadcasts it.

An event is “in a subscription” if the event’s ``event_type`` field matches the
subscription’s ``event_type`` field, and the event matches any filters that are
in the event subscription. If multiple filters are included in a single
subscription, only events that pass *all* filters will be received.
Note, however, that you can have have multiple subscriptions at a time, so you
will receive all events that pass the filter or filters in each subscription.


Event Filters
=============

An event filter operates on event attributes. A filter specifies an attribute
key, a "match string", and a filter type.

  * The attribute key specifies the event attribute that you are interested in,
    such as ``address`` or ``block_id``.

  * The match string is used to compare against the event's attribute value, as
    identified by the attribute key.

  * The filter type (simple or regular expression) determines the rules for
    comparing the match string to the event's attribute value.

The filter type can either be ``SIMPLE`` (an exact match to the specified
string) or ``REGEX`` (a match using a regular expression). In addition, the
filter type specifies ``ANY`` (match one or more) or ``ALL`` (must match all).
The following filter types are supported:

* ``SIMPLE_ANY``:
  The filter's "match string" must match at least one of the
  event's attribute values. For example, this filter type with the match string
  "``abc``" would succeed for a single event with the following attributes,
  because it matches the attribute value ``abc``.

  .. code-block:: none

     Attribute(key="address",value="abc")
     Attribute(key="address",value="def")

* ``SIMPLE_ALL``:
  The filter's "match string" must match all of the event's attribute values.
  This filter type with the match string "``abc``" would fail with the previous
  example, because it does not match all the attribute values.

* ``REGEX_ANY``:
  The filter's regular expression must evaluate to a match for at least one of
  the event's attribute values. For example, this filter type with the match
  string "``ab.``" would succeed for a single event with the following
  attributes, because it matches the attribute value ``abc``.

  .. code-block:: none

     Attribute(key="address",value="abc")
     Attribute(key="address",value="abbbc")
     Attribute(key="address",value="def")

* ``REGEX_ALL``:
  The filter's regular expression must evaluate to a match for all of the
  event's attribute values. This filter type with the match string "``ab.``"
  would fail with the previous example, because it doesn't match all three
  attribute values above. The match string ``[ad][be]*[cf]`` would succeed.


Event Subscription Protobuf
===========================

Event subscriptions are submitted and serviced over a ZMQ socket using the
validator's messaging protocol.

An event subscription is represented with the following protobuf messages, which
are defined in ``sawtooth-core/protos/events.proto``.

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

A ``ClientEventsSubscribeRequest`` envelope is used to submit subscription
requests and receive the responses.

.. code-block:: protobuf

  message ClientEventsSubscribeRequest {
      repeated EventSubscription subscriptions = 1;
      // The block id (or ids, if trying to walk back a fork) the subscriber last
      // received events on. It can be set to empty if it has not yet received the
      // genesis block.
      repeated string last_known_block_ids = 2;
  }

The validator responds with a ``ClientEventsSubscribeResponse`` message that
specifies whether the subscription was successful.

.. code-block:: protobuf

  message ClientEventsSubscribeResponse {
      enum Status {
           OK = 0;
           INVALID_FILTER = 1;
           UNKNOWN_BLOCK = 2;
      }
      Status status = 1;
      // Additional information about the response status
      string response_message = 2;
  }

When subscribing to events, an application can optionally request "event
catch-up" by sending a list of block IDs along with the subscription. For more
information, see :ref:`event-catch-up-label`.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
