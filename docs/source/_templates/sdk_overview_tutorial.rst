{% set short_lang = 'python' %}
{% if language == 'JavaScript' %}
    {% set short_lang = 'js' %}
{% elif language == 'Go' %}
    {% set short_lang = 'go' %}
{% elif language == 'Rust' %}
    {% set short_lang = 'rust' %}
{% endif %}

{% set lowercase_lang = 'python' %}
{% if language == 'JavaScript' %}
    {% set lowercase_lang = 'javascript' %}
{% elif language == 'Go' %}
    {% set lowercase_lang = 'go' %}
{% elif language == 'Rust' %}
    {% set lowercase_lang = 'rust' %}
{% endif %}

Overview
========

This tutorial shows how to use the Sawtooth {{ language }} SDK to develop a
simple application (also called a transaction family).
A transaction family includes these components:

* A **transaction processor** to define the business logic for your application.
  The transaction processor is responsible for registering with the validator,
  handling transaction payloads and associated metadata, and getting/setting
  state as needed.

* A **data model** to record and store data.

* A **client** to handle the client logic for your application.
  The client is responsible for creating and signing transactions, combining
  those transactions into batches, and submitting them to the validator. The
  client can post batches through the REST API or connect directly to the
  validator via `ZeroMQ <http://zeromq.org>`_.

The client and transaction processor must use the same data model,
serialization/encoding method, and addressing scheme.

In this tutorial, you will construct a transaction handler that implements XO,
a distributed version of the two-player game
`tic-tac-toe <https://en.wikipedia.org/wiki/Tic-tac-toe>`_.

{% if language == 'Python' %}

This tutorial also describes how a client can use the {{ language }} SDK
to create transactions and submit them as :term:`Sawtooth batches<Batch>`.

{% elif language == 'JavaScript' %}

This tutorial also describes how a client can use the {{ language }} SDK
to create transactions and submit them as :term:`Sawtooth batches<Batch>`.

{% endif %}

.. note::

   This tutorial demonstrates the relevant concepts for a Sawtooth transaction
   processor and client, but does not create a complete implementation.


{% if language == 'Rust' %}

   For a full Rust implementation of the XO transaction family, see
   ``/{project}/sawtooth-core/sdk/examples/xo_{{ lowercase_lang }}/``.

{% elif language == 'Go' %}

   For a full Go implementation of the XO transaction family, see
   `https://github.com/hyperledger/sawtooth-sdk-go/tree/master/examples/xo_go
   <https://github.com/hyperledger/sawtooth-sdk-go/tree/master/examples/xo_go>`_.

{% elif language == 'Java' %}

   For a full Java implementation of the XO transaction family, see
   `https://github.com/hyperledger/sawtooth-sdk-java/tree/master/examples/xo_java
   <https://github.com/hyperledger/sawtooth-sdk-java/tree/master/examples/xo_java>`_.

{% elif language == 'JavaScript' %}

   For a full JavaScript implementation of the XO transaction family, see
   `https://github.com/hyperledger/sawtooth-sdk-javascript/tree/master/examples/xo
   <https://github.com/hyperledger/sawtooth-sdk-javascript/tree/master/examples/xo>`_.

{% else %}

   For a full Python implementation of the XO transaction family, see
   ``/{project}/sawtooth-core/sdk/examples/xo_{{ lowercase_lang }}/``.

{% endif %}



.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
