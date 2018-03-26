*********************
About Sawtooth Events
*********************

Sawtooth events occur when blocks are committed --- that is, the validator
broadcasts events when a commit operation succeeds --- and are not persisted in
state. Each transaction family can define the events that are appropriate for
its business logic.

An event has three parts:

* Event type (the name of the event)
* Opaque payload whose structure is defined by the event type
* List of attributes

An attribute is a key-value pair that contains transparent metadata about the
event. The key is the name of the attribute, and the value is the specific
contents for that key. The same key can be used for multiple attributes in an
event.

It is important to define meaningful event attributes, so that the attributes
can be used to filter event subscriptions. Note that although attributes are not
required, an event filter cannot operate on an event without attributes. For
more information, see :doc:`about_event_subscriptions`.

Events are represented with the following protobuf message:

.. code-block:: protobuf

   message Event {
     // Used to subscribe to events and servers as a hint for how to deserialize
     // event_data and what pairs to expect in attributes.
     string event_type = 1;

     // Transparent data defined by the event_type.
     message Attribute {
       string key = 1;
       string value = 2;
     }
     repeated Attribute attributes = 2;

     // Opaque data defined by the event_type.
     bytes  data = 3;
   }

The ``event_type`` field (the name of the event) is used to determine how opaque
(application-specific) data has been serialized and what transparent event
attributes to expect.

For more information, see
:doc:`/architecture/events_and_transactions_receipts`.


Event Namespace
===============

By convention, event names use the transaction family as a prefix, such as
``xo/create`` for a create event from the XO transaction family.

Core Sawtooth events are prefixed with ``sawtooth/``. The core events are:

  * ``sawtooth/block-commit``

  * ``sawtooth/state-delta``

sawtooth/block-commit
---------------------

A ``sawtooth/block-commit`` event occurs when a block is committed. This event
contains information about the block, such as the block ID, block number, state
root hash, and previous block ID. It has the following structure:

.. code-block:: protobuf

   Event {
     event_type = "sawtooth/block-commit",
     attributes = [
       Attribute { key = "block_id", value = "abc...123" },
       Attribute { key = "block_num", value = "523" },
       Attribute { key = "state_root_hash", value = "def...456" },
       Attribute { key = "previous_block_id", value = "acf...146" },
     ],
   }

sawtooth/state-delta
--------------------

A ``sawtooth/state-delta`` occurs when a block is committed. This event contains
all state changes that occurred at a given address for that block. This event
has the following structure:

.. code-block:: python

     Event {
       event_type = "sawtooth/state-delta",
       attributes = [Attribute { key = "address", value = "abc...def" }],
       event_data = <bytes>
     }

Note that the addresses that match the filter are in the attributes. Changed
values are part of the event data.


Example: An Application-specific Event
======================================

The XO transaction family could define an ``xo/create`` event that is sent when
a game has been created. The following examples show a simple ``xo/create``
event in several languages.

Python example:

   .. code-block:: python

      context.add_event(
          "xo/create", {
              'name': name,
              'creator': signer_public_key
      })

Go example:

   .. code-block:: go

    attributes := make([]processor.Attribute, 2)
    attributes = append(attributes, processor.Attribute{
      Key:   "name",
      Value: name,
    })
    attributes = append(attributes, processor.Attribute(
      Key:   "creator",
      Value: signer_public_key,
    })
    var empty []byte
    context.AddEvent(
      "xo/create",
      attributes,
      empty)

JavaScript example:

   .. code-block:: javascript

      context.addEvent(
        'xo/create',
        [['name', name], ['creator', signer_public_key]],
        null)


Rust example:

   .. code-block:: rust

      context.add_event(
        "xo/create".to_string(),
        vec![("name".to_string(), name), ("creator".to_string(), signer_public_key)],
        vec![].as_slice())


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
