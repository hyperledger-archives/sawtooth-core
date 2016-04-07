.. _block-label:

=================================================================
/block
=================================================================


Block IDs are always ordered from the newest committed block ID to the oldest.

.. http:get:: /block

   Returns a list of the committed block IDs.

   :query blockcount: The maximum number of blocks to return.

.. http:get:: /block/{block_id}

   Returns the contents of block `block_id`.

.. http:get:: /block/{block_id}/{key}

   Returns the value associated with key `key` within block `block_id`.



**Example request**:

.. sourcecode:: http

    GET /block HTTP/1.1
    Host: localhost:8800
    User-Agent: curl/7.43.0
    Accept: */*


**Example response**:

.. sourcecode:: http

    HTTP/1.1 200 OK
    Date: Fri, 19 Feb 2016 18:16:40 GMT
    Content-Length: 128
    Content-Type: application/json

    [
        "efaa886dc6b5b325",
        "4238a27a967a0cdb",
        "85ec88be3fdd404b",
        "b7351fa8d5a49dcf",
        "20c3a8dbffdd8c74",
        "3e15ef3909d2452e"
    ]

**Example**:

.. sourcecode:: console

    GET /block?blockcount=2

.. sourcecode:: javascript

    [
        "efaa886dc6b5b325",
         "4238a27a967a0cdb"
    ]

**Example**:

.. sourcecode:: console

    GET /block/85ec88be3fdd404b

.. sourcecode:: javascript

    {
        "Identifier": "85ec88be3fdd404b",
        "PreviousBlockID": "b7351fa8d5a49dcf",
        "Signature": "GyZOrdAA2212HYyKGvKlHBnkPAqOKY1XeQoIbsI6/4wDhY26FdffXLOgUpDMhpQhSKKwtGQBQL0uzpwcypKqbjQ=",
        "TransactionBlockType": "/Lottery/PoetTransactionBlock",
        "TransactionIDs": [
          "0102098777664ea4",
          "3c5f74a72486eedf",
          "fada0f0b22123857",
          "b3c5bd4cabf45a5b"
        ],
        "WaitCertificate": {
          "GlobalSignature": "3jqbnsfeyn7iwfkajwbvvkwfemy2525vtci42vakjgifhejy7t2a8mpeg7kykjrn9reiq443xpvzvqh7c2e4r7fgn5cvtnbvb7w42ts",
          "SerializedCert": "{ \"Duration\": 43.434298, \"LocalMean\": 37.200000, \"MinimumWaitTime\": 0.000000, \"PreviousBlockID\": \"b7351fa8d5a49dcf\", \"RequestTime\": 1455905328.460869 }"
        }
    }

**Example**:

.. sourcecode:: console

    GET /block/b33ce9f5d203bfc0/Signature


.. sourcecode:: javascript

    "HHMDpz0uFKXCQ6DcOx5WYW+fXHm6TeQTN9TNHhprn8djSUashJDI9IhI0xNFH3a1mfeDREskxRRE80dn1pb8V7Y="
