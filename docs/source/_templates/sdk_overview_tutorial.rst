{% set short_lang = 'python' %}
{% if language == 'JavaScript' %}
    {% set short_lang = 'js' %}
{% elif language == 'Go' %}
    {% set short_lang = 'go' %}
{% endif %}

{% set lowercase_lang = 'python' %}
{% if language == 'JavaScript' %}
    {% set lowercase_lang = 'javascript' %}
{% elif language == 'Go' %}
    {% set lowercase_lang = 'go' %}
{% endif %}

This tutorial describes how to create a Hyperledger Sawtooth transaction
processor using the Sawtooth {{ language }} SDK.
In this tutorial, you will construct a transaction handler that implements a
distributed version of the two-player game
`tic-tac-toe <https://en.wikipedia.org/wiki/Tic-tac-toe>`_.

This tutorial also describes how a client can use the {{ language }} SDK
to create transactions and submit them as :term:`Sawtooth batches<Batch>`.

.. note::

   This tutorial demonstrates the relevant concepts for a Sawtooth transaction
   processor and client, but does not  create a complete implementation.

   * For a full implementation of the tic-tac-toe transaction family, see
     ``/project/sawtooth-core/sdk/examples/xo_{{ lowercase_lang }}/``.

   * For full implementations in other languages, see
     ``https://github.com/hyperledger/sawtooth-core/tree/master/sdk/examples``.

Prerequisites
=============

 * A working Sawtooth development environment, as described in
   :doc:`/app_developers_guide/installing_sawtooth`

 * Familiarity with the basic Sawtooth concepts introduced in
   :doc:`/app_developers_guide/installing_sawtooth`

 * Understanding of the Sawtooth transaction and batch data structures as
   described in :doc:`/architecture/transactions_and_batches`

{% if language == 'Python' %}

 * Python 3, version 3.5 or higher

{% endif %}


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
