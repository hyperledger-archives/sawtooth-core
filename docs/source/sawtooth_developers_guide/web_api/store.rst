=================================================================
/store
=================================================================

.. http:get:: /store

   Returns a list of all of the store names.

.. http:get:: /store/{tf_name}

   Returns a list of keys within `tf_name`. The "tf" is short for Transaction
   Family.

.. http:get:: /store/{tf_name}/*

   Returns a dump of all the keys and values within `tf_name`.

.. http:get:: /store/{tf_name}/{key}

   Returns the value associated with key `key` within store `tf_name`.

   :query blockid: Uses the version of the store resulting from the commitment
                   of block `blockid`. When omitted, defaults to the version
                   of the store associated with the last committed block.

**Example request**:

.. sourcecode:: http

      GET /store HTTP/1.1
      Host: localhost:8800
      User-Agent: curl/7.43.0
      Accept: */*


**Example response**:

.. sourcecode:: http

      HTTP/1.1 200 OK
      Date: Fri, 19 Feb 2016 02:34:33 GMT
      Content-Length: 85
      Content-Type: application/json

      [
        "/IntegerKeyTransaction",
        "/EndpointRegistryTransaction",
        "/MarketPlaceTransaction"
      ]


**Example**:

.. sourcecode:: console

    GET /store/IntegerKeyTransaction

.. sourcecode:: javascript

    [
        "SYM3",
        "SYM2",
        "SYM1",
        "SYM0"
    ]

**Example**:

.. sourcecode:: console

    GET /store/IntegerKeyTransaction/*

.. sourcecode:: javascript

    {
        "SYM0": 5,
        "SYM1": 4,
        "SYM2": 1,
        "SYM3": 2
    }


**Example**:

.. sourcecode:: console

    GET /store/IntegerKeyTransaction/SYM1

.. sourcecode:: javascript

    4

**Example**:

.. sourcecode:: console

    GET /store/IntegerKeyTransaction/*?blockid=1f8fc8250cd26fb3

.. sourcecode:: javascript

    {"SYM0": 0}

Note that after block `1f8fc8250cd26fb3` was committed, the
`IntegerKeyTransaction` store only contained the SYM0 key. The "SYM1",
"SYM2" and "SYM3" keys were added in later blocks.

.. note::

   The block id was obtained by using the block API (see :ref:`block-label`).








