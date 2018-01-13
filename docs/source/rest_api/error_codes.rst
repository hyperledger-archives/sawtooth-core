***************
Error Responses
***************

When the REST API encounters a problem, or receives notification that the
validator has encountered a problem, it will notify clients with both an
appropriate HTTP status code and a more detailed JSON response.


HTTP Status Codes
=================

.. list-table::
   :widths: 4, 16, 60
   :header-rows: 1

   * - Code
     - Title
     - Description
   * - 400
     - Bad Request
     - The request was malformed in some way, and will need to be modified
       before resubmitting. The accompanying JSON response will have more
       details.
   * - 404
     - Not Found
     - The request was well formed, but the specified identifier did not
       correspond to any resource in the validator. Returned by endpoints which
       fetch a single resource. Endpoints which return lists of resources will
       simply return an empty list.
   * - 500
     - Internal Server Error
     - Something is broken internally in the REST API or the validator. This may
       be a bug; if it is reproducible, the bug should be reported.
   * - 503
     - Service Unavailable
     - The REST API is unable to communicate with the validator. It may be down.
       You should try your request later.


JSON Response
=============

In the case of an error, rather than a *data* property, the JSON response will
include a single *error* property with three values:

   * *code* (integer) - a machine readable error code
   * *title* (string) - a short headline for the error
   * *message* (string) - a longer, human-readable description of what went wrong

.. note::

   While the title and message may change in the future, the error code
   will **not** change; it is fixed and will always refer to this particular
   problem.


Example JSON Response
---------------------

.. code-block:: json

   {
     "error": {
       "code": 30,
       "title": "Submitted Batches Invalid",
       "message": "The submitted BatchList is invalid. It was poorly formed or has an invalid signature."
     }
   }


Error Codes and Descriptions
============================

.. list-table::
   :widths: 4, 16, 60
   :header-rows: 1

   * - Code
     - Title
     - Description
   * - 10
     - Unknown Validator Error
     - An unknown error occurred with the validator while processing the
       request. This may be a bug; if it is reproducible, the bug should be
       reported.
   * - 15
     - Validator Not Ready
     - The validator has no genesis block, and so cannot be queried. Wait for
       genesis to be completed and resubmit. If you are running the validator,
       ensure it was set up properly.
   * - 17
     - Validator Timed Out
     - The request timed out while waiting for a response from the validator. It
       may not be running, or may have encountered an internal error. The
       request may not have been processed.
   * - 18
     - Validator Disconnected
     - The validator sent a disconnect signal while processing the response, and
       is no longer available. Try your request again later.
   * - 20
     - Invalid Validator Response
     - The validator sent back a response which was not serialized properly
       and could not be decoded. There may be a problem with the validator.
   * - 21
     - Invalid Resource Header
     - The validator sent back a resource with a header that could not be
       decoded. There may be a problem with the validator, or the data may
       have been corrupted.
   * - 27
     - Unable to Fetch Statuses
     - The validator should always return some status for every batch
       requested. An unknown error caused statuses to be missing, and should be
       reported.
   * - 30
     - Submitted Batches Invalid
     - The submitted BatchList failed initial validation by the validator. It
       may have a bad signature or be poorly formed.
   * - 31
     - Unable to Accept Batches
     - The validator cannot currently accept more batches due to a full queue.
       Please submit your request again.
   * - 34
     - No Batches Submitted
     - The BatchList Protobuf submitted was empty and contained no batches. All
       submissions to the validator must include at least one batch.
   * - 35
     - Protobuf Not Decodable
     - The REST API was unable to decode the submitted Protobuf binary. It is
       poorly formed, and has not been submitted to the validator.
   * - 42
     - Wrong Content Type (submit batches)
     - POST requests to submit a BatchList must have a 'Content-Type' header of
       'application/octet-stream'.
   * - 43
     - Wrong Content Type (fetch statuses)
     - If using a POST request to fetch batch statuses, the 'Content-Type'
       header must be 'application/json'.
   * - 46
     - Bad Status Request
     - The body of the POST request to fetch batch statuses was poorly formed.
       It must be a JSON formatted array of string-formatted batch ids, with at
       least one id.
   * - 50
     - Head Not Found
     - A 'head' query parameter was used, but the block id specified does not
       correspond to any block in the validator.
   * - 53
     - Invalid Count Query
     - The 'count' query parameter must be a positive, non-zero integer.
   * - 54
     - Invalid Paging Query
     - The validator rejected the paging request submitted. One or more of the
       'min', 'max', or 'count' query parameters were invalid or out of range.
   * - 57
     - Invalid Sort Query
     - The validator rejected the sort request submitted. Most likely one of
       the keys specified was not found in the resources sorted.
   * - 60
     - Invalid Resource Id
     - A submitted block, batch, or transaction id was invalid. All such
       resources are identified by 128 character hex-strings.
   * - 62
     - Invalid State Address
     - The state address submitted was invalid. Returned when attempting to
       fetch a particular "leaf" from the state tree. When fetching specific
       state data, the full 70-character address must be used.
   * - 66
     - Id Query Invalid or Missing
     - If using a GET request to fetch batch statuses, an 'id' query parameter
       must be specified, with a comma-separated list of at least one batch id.
   * - 70
     - Block Not Found
     - There is no block with the id specified in the blockchain.
   * - 71
     - Batch Not Found
     - There is no batch with the id specified in the blockchain.
   * - 72
     - Transaction Not Found
     - There is no transaction with the id specified in the blockchain.
   * - 75
     - State Not Found
     - There is no state data at the address specified.
   * - 80
     - Transaction Receipt Not Found
     - There is no transaction receipt for the transaction id specified in the
       receipt store.
   * - 81
     - Wrong Content Type
     - Requests for transaction receipts sent as a POST must have a
       'Content-Type' header of 'application/json'.
   * - 82
     - Bad Receipts Request
     - Requests for transaction receipts sent as a POST must have a JSON
       formatted body with an array of at least one id string.
   * - 83
     - Id Query Invalid or Missing
     - Requests for transaction receipts sent as a GET request must have an 'id'
       query parameter with a comma-separated list of at least one transaction
       id.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
