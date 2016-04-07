=================================================================
/transaction
=================================================================


Transaction IDs are always ordered from the newest committed transaction ID
to the oldest.

.. http:get:: /transaction

   Returns a list of the committed transaction IDs.

   :query blockcount: Returns the transaction IDs from up to
       `blockcount` blocks.

.. http:get:: /transaction/{transaction_id}

   Returns the contents of transaction `transaction_id`.

.. http:head:: /transaction/{transaction_id}

   The HTTP response code indicates the status of transaction `transaction_id`.

   :statuscode 200: The transaction exists and has been committed.
   :statuscode 302: The transaction exists but has not been committed.
   :statuscode 404: The transaction does not exist.

.. http:get:: /transaction/{transaction_id}/{key}

   Returns the value associated with key `key` within transaction
   `transaction_id`.


**Example request**:

.. sourcecode:: http

    GET /transaction HTTP/1.1
    Host: localhost:8800
    User-Agent: curl/7.43.0
    Accept: */*

**Example response**:

.. sourcecode:: http

    HTTP/1.1 200 OK
    Date: Fri, 19 Feb 2016 19:29:29 GMT
    Content-Length: 317
    Content-Type: application/json

    [
        "7d0cb57cdaa34ee0",
        "6f747d9cb173921f",
        "87fdf8ee10bee691",
        "9a403d328f2da810",
        "74048866a4983941",
        "01eee862b6a10ebc",
        "1e79d167c62bbc44",
        "d422d8793210714f",
        "1f48c06a715c8e11",
        "70931019ed499b2e",
        "f74872b90cbf5e7f",
        "92c5bdc786e90e1b",
        "91e5e24562e45c33",
        "6e6f0bc13ffb4b61",
        "c6d2c9bd05fd648d"
    ]


**Example**:

.. sourcecode:: console

    GET /transaction?blockcount=1

.. sourcecode:: javascript

    [
        "92c5bdc786e90e1b",
        "91e5e24562e45c33",
        "6e6f0bc13ffb4b61",
        "c6d2c9bd05fd648d"
    ]

**Example**:

.. sourcecode:: http

    HEAD /transaction/1e79d167c62bbc44 HTTP/1.1
    Host: localhost:8800
    User-Agent: curl/7.43.0
    Accept: */*

.. sourcecode:: http

    HTTP/1.1 200 OK
    Date: Fri, 19 Feb 2016 19:34:37 GMT


**Example**:

.. sourcecode:: console

    GET /transaction/1e79d167c62bbc44


.. sourcecode:: javascript

    {
      "Dependencies": [],
      "Identifier": "1e79d167c62bbc44",
      "InBlock": "32ec280dab040d00",
      "Nonce": 1455906424.223023,
      "Signature": "HAHOQuBLeMy7tAKnOHfSepg2pPBSwDrJRKWTXj4Znuy3Hbgq1VcvA23odR1b2RU27ssTVLksCDcVOod+z8408yg=",
      "Status": 2,
      "TransactionType": "/IntegerKeyTransaction",
      "Updates": [
        {
          "Name": "SYM1",
          "Value": 0,
          "Verb": "set"
        }
      ]
    }

**Example**:

.. sourcecode:: console

    GET /transaction/1e79d167c62bbc44/InBlock

.. sourcecode:: javascript

    "32ec280dab040d00"
