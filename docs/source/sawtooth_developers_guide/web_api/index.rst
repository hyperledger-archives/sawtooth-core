.. _web-api-index-label:

**************************
Distributed Ledger Web API
**************************

A validator supports a Web API allowing for access to blocks, transactions
and state storage. It also enables sending transactions to the network.

For the query APIs, if the `Accept` header is "application/cbor",
the response will be encoded using `CBOR <http://cbor.io/>`_.
If the `Accept` header is missing or has any other value,
the response will be encoded using `JSON <http://www.json.org/>`_.

If the response is encoded using JSON, the response can be "pretty printed"
by adding a "p" parameter to the URL, for example:

.. http:get:: /block?p=1

   Returns a list of the committed block IDs, which will be pretty-printed
   if the response is encoded in JSON.

.. note::

   The example responses given in this
   document are pretty printed even without the "p" query parameter
   for clarity.

Contents:

.. toctree::
   :maxdepth: 2

   store
   block
   transaction
   initiate
   forward
   echo
