Validator Web API
=================

A validator supports a Web API allowing for access to blocks, transactions, the
state storage and the market place. It also enables sending transactions to the network.

For the query APIs, if the `Accept` header is "appliaction/cbor", the response will be
encoded using CBOR. If the `Accept` header is missing or has any other value, the response will be
encoded using JSON.

If the response is encoded using JSON, the response can be "pretty printed" by adding a "p" paramter to
the URL, for example:

.. http:get:: /block?p=1

   Returns a list of the committed block IDs, which will be pretty-printed if the response is
   encoded in JSON. The example responses given in this document are pretty printed even without
   the "p" query parameter for clarity.


Contents:

.. toctree::
   :maxdepth: 2

   store
   block
   transaction
   market
   initiate
   forward
   echo
