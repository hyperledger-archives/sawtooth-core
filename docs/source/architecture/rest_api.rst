********
REST API
********

Hyperledger Sawtooth provides a REST API (see the :doc:`../rest_api`) that
allows clients to interact with a validator using common HTTP/JSON standards.
It is a pragmatic RESTful API that provides a language-neutral interface for
submitting transactions and reading blocks.

The Sawtooth REST API is intended only as a simple interface for client use. The
validator and transaction processors use a ZMQ/Protobuf interface
that is more efficient and robust, as well as slightly more complicated.
Note that clients also have the option of using the ZMQ/Protobuf interface to
communicate with the validator.

The REST API is a lightweight layer on top of Sawtooth's internal ZMQ
communication. As a result, the API offers no authorization. It simply passes
every request to the validator to be authorized with signature verification
or another strategy that is defined by a transaction processor.

The REST API process runs as a separate process, rather than as part of the
validator process. It treats the validator as a black box, simply submitting
transactions and fetching the results.

Response Envelope
=================

The REST API uses a JSON envelope to send metadata back to clients in a way that
is simple to parse and easily customized. All successful requests return data
in an envelope that may include the requested resource, chain head ID, a link
to the requested resource, and paging information (described below).

The JSON response envelope also includes the details needed to parse errors. For
more information, see the :doc:`../rest_api/error_codes`.

Pagination
==========

The API endpoints include RESTful references to resources stored in the Sawtooth
ledger that clients might be interested in, like blocks and transactions, as
well as RESTful metadata like batch status.

All endpoints that return lists of resources will automatically paginate the
results, up to a default limit of 100 resources.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
