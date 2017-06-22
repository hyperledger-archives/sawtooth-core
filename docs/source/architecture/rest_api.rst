********
REST API
********

*Hyperledger Sawtooth* provides a pragmatic RESTish API for clients to interact
with a validator using common HTTP/JSON standards. It is an entirely separate
process, which once running, allows transactions to be submitted and blocks to
be read with a common language-neutral interface. As the validator is redesigned
and improved the REST API will grow with it, providing a consistent interface
that meets the needs of app developers into the future.

With that focus on app developers, the REST API treats the validator mostly as a
black box, submitting transactions and fetching the results. It is not the tool
for all validator communication. For example, it is not used by Transaction
Processors to communicate with a validator, or by one validator to talk to other
validators. For these and similar use cases, there is a more efficient and
robust, if somewhat more complicated, ZMQ/Protobuf interface.


Open API Specification
======================

The REST API is comprehensively documented using the
`OpenAPI specification <http://swagger.io/specification/>`_ (fka Swagger),
formatted as a YAML file. This documentation provides a single source of truth
that completely documents every implemented aspect of the API, is both human and
machine readable, and can be compiled by a variety of toolsets (including for
this Sphinx-based document). The spec file itself can be found
`here <https://github.com/hyperledger/sawtooth-core/blob/master/rest_api/sawtooth_rest_api/openapi.yaml>`_.


HTTP Status Codes
=================

In order to improve clarity and ease parsing, the REST API supports a limited
number of common HTTP status codes. Further granularity for parsing errors is
provided by specific :doc:`../rest_api/error_codes` in the JSON response
envelope itself (see below).

.. list-table::
   :widths: 4, 16, 60
   :header-rows: 1

   * - Code
     - Title
     - Description
   * - 200
     - OK
     - The requested resources were successfully fetched. They are included in
       the ``"data"`` property of the response envelope.
   * - 201
     - Created
     - The POSTed resources were submitted and created/committed successfully. A
       ``"link"`` is included to the resources.
   * - 202
     - Accepted
     - The POSTed resources were submitted to the validator, but are not yet
       committed. A ``"link"`` to check the *status* of the submitted resources
       is included. If told to wait for commit, but timed out, the status at the
       moment of timing out is also included in the ``"data"`` property.
   * - 400
     - Bad Request
     - Something in the client's request was malformed, and the request could
       not be completed.
   * - 404
     - Not Found
     - The request was well-formed, but there is no resource with the identifier
       specified.
   * - 500
     - Internal Server Error
     - Something is broken in the REST API or the validator. If consistently
       reproducable, a bug report should be submitted.
   * - 503
     - Service Unavailable
     - Indicates the REST API is unable to contact the validator.


Data Envelope
=============

The REST API uses a JSON envelope to send metadata back to clients in a way that
is simple to parse and easily customized. All successful requests will return
data in an envelope with at least one of four possible properties:

   * **data** - contains the actual resource or resources being fetched
   * **head** - id of the head block of the chain the resource was fetched
     from, this is particularly useful to know if an explicit *head* was not set
     in the original request
   * **link** - a link to the resources fetched with both *head* and
     paging parameters explicitly set, will always return the same resources
   * **paging** - information about how the resources were paginated, and how
     further pages can be fetched (see below)

*Example response envelope:*

.. code-block:: json

   {
     "data": [{"fetched": "resources"}],
     "head": "65cd...47dd",
     "link": "http://rest.api.domain/state?head=65cd...47dd"
   }


Pagination
----------
All endpoints that return lists of resources will automatically paginate
results, limited by default to 1000 resources. In order to specify what range of
resources to return, these endpoints take ``count`` and either ``min`` or
``max`` query parameters. They specify the total number of items to include, as
well as what the first or last item in the list should be. For convenience,
both *min* and *max* may refer to either an index or a resource id.

*Example paged request URL:*

.. code-block:: text

   http://rest.api.domain/blocks?count=100&min=200

Within the ``"paging"`` property of the response body there will be one or more
of these four values:

   * **start_index** - the index of the first item in the fetched list
   * **total_count** - the total number of resources available
   * **previous** - a url for the previous page, if any
   * **next** - a url for the next page, if any

*Example paging response:*

.. code-block:: json

   {
     "data": [{"fetched": "resources"}],
     "paging": {
       "start_index": 200,
       "total_count": 54321,
       "previous": "http://rest.api.domain/state?head=65cd...47dd&count=100&min=100",
       "next": "http://rest.api.domain/state?head=65cd...47dd&count=100&min=300"
     }
   }


Errors
------

If something goes wrong while processing a request, the REST API will send back
a response envelope with only one property: ``"error"``. That error will contain
three values which explain the problem that occured:

   * **code** - a machine parsable code specific to this particular error
   * **title** - a short human-readable headline for the error
   * **message** - a longer more detailed explanation of what went wrong

*Example error response:*

.. code-block:: json

   {
     "error": {
       "code": 30,
       "title": "Submitted Batches Invalid",
       "message": "The submitted BatchList is invalid. It was poorly formed, or has an invalid signature."
     }
   }

.. note::

   While the title or message of an error may change or be reworded over time,
   **the code is fixed**, and will always refer to the same error.


Query Parameters
================

Many routes support query parameters to help specify how a request to the
validator should be formed. Not every endpoint supports every query, and some
endpoints have their own parameters specific to just to them. Any queries
specific to a single endpoint are not listed here.

.. list-table::
   :widths: 8, 72

   * - **head**
     - The id of the block to use as the chain head. This is particularly
       useful to request older versions of state *(defaults to the latest chain
       head)*.
   * - **count**
     - For paging, specificies the number of resources to fetch *(defaults to
       1000)*.
   * - **min**
     - For paging, specifies the id or index of the first resource to fetch
       *(defaults to 0)*.
   * - **max**
     - For paging, specifies the id or index of the last resource to fetch. It
       would be used instead of *min*, not in the same query.
   * - **sort**
     - For endpoints that fetch lists of resources, specifies a key or keys to
       sort the list by. These key sorts can be modified with a few simple
       rules: nested keys can be dot-notated; `header.` may be omitted in the
       case of nested header keys; appending `.length` sorts by the length of
       the property; a minus-sign specifies descending order; multiple keys can
       be used if comma-separated. For example:
       `?sort=header.signer_pubkey,-transaction_ids.length`
   * - **wait**
     - For submission endpoints, instructs the REST API to wait until batches
       have been committed to the blockchain before responding to the client.
       Can be set to a positive integer to specify a timeout in seconds, or
       without any value to use the REST API's internal time out.


Endpoints
=========

The endpoints include RESTful references to resources stored in the Sawtooth
ledger that clients might be interested in, like blocks and transactions, as
well as RESTish metadata, like batch status.


Resource Endpoints
------------------
In order to fetch resources stored on chain or in the validator's state,
various resource routes are provided. As is typical with RESTful APIs, a ``GET``
request fetches one or many resources, depending on whether or not a particular
resource identifier was specifed (i.e. ``/resources`` vs ``/resources/{resource-
identifier}``).

   * **/blocks** - the actual blocks currently in the blockchain, referenced by
     id (aka ``header_signature``)
   * **/batches** - the batches stored on the blockchain, referenced by id
   * **/transactions** - the transactions stored on the blockchain, referenced
     by id
   * **/state** - the ledger state, stored on the merkel trie, referenced by
     leaf addresses


Submission Endpoints
--------------------
In order to submit transactions to a Sawtooth validator, they *must* be wrapped
in a batch. For that reason, submissions are sent to the ``/batches`` endpoint
and only that endpoint. Due to the asynchronous nature of blockchains, there is
a corresponding endpoint to check the status of submitted batches. Both requests
will accept the ``wait`` query parameter, allowing clients to receive a response
only once the batches are committed.

   * **/batches** - accepts a ``POST`` request with a body of a binary
     BatchList of batches to be submitted
   * **/batch_status** - fetches the committed status of one or more batches

     *Example batch status response:*

     .. code-block:: json

        [
          {
            "id": "89807bfc9089e37e00d87d97357de14cfbc455cd608438d426a625a30a0da9a31c406983803c4aa27e1f32a3ff61709e8ec4b56abbc553d7d330635b5d27029c",
            "status": "COMMITTED"
          },
          {
            "id": "c0c2075e708c04b34903c5374f65c9352f9dc9662f187e4bab0605aba3eb697e459bfa3a61a8050c428d1347d47a11b0cf81d481467a18cd48ab137001a5fa29",
            "status": "PENDING"
          }
        ]


Future Development
==================

Stats and Status Endpoints
--------------------------

In order to track the performance of the validator and the blockchain generally,
additional endpoints could be implemented to fetch metrics related to block
processing, peer to peer communication, system status, and more. These will
require significant design and development, both within the REST API, and within
the core validator code itself.


Configuration
-------------

At some point it may be useful to add some configuration options to the REST
API, such as:

   * Modify error verbosity to change detail and security sensitivity of error
     messages provided (i.e. whether or not to include the stack trace)
   * Enable or disable the stats and status endpoints


Authorization
-------------

The current intention is for the REST API to be a lightweight shim on top of the
internal ZMQ communications. From this perspective, the API offers no
authorization, simply passing through every request to the validator to be
authorized with signature verification or some other strategy defined by an
individual Transaction Processor.

However, that may be insufficient if the API needed to be deployed just for
certain authorized clients. In that use case, the best solution would be to
expand the REST API to handle the validation of *API keys*. In their most basic
form, these can be validated programmatically without any need for persistent
state stored on a database or elsewhere. However, more sophisticated
functionality, like blacklisting particular keys that are compromised, would
require some strategy for persistent storage.

.. note::

   While the REST API does not support any sort of authorization internally, it
   is entirely possible to put it behind a proxy that does. See:
   :doc:`/sysadmin_guide/rest_auth_proxy`
