=================================================================
/echo
=================================================================


.. http:post:: /echo

   The request is parsed into an object, re-serialized to JSON, and returned in the response.


**Example request**:

.. sourcecode:: http

    POST /echo HTTP/1.1
    Host: localhost:8800
    User-Agent: curl/7.43.0
    Accept: */*
    Content-Type: application/json
    Content-Length: 536

    {
      "Transaction": {
        "Dependencies": [],
        "Nonce": 1444777217.496317,
        "Signature": "HAy35m01U0SNVbCBDUS+EQ8ufC1x7d1V2IAwRRqDQX4UhdKr3YMIiiHCTLLPrRCbyDB1jpiaemfDNoznqvd1eS4=",
        "TransactionType": "/MarketPlaceTransaction",
        "Update": {
          "UpdateType": "/mktplace.transactions.ParticipantUpdate/Register",
          "Description": "MarketPlaceParticipant",
          "Name": "market"
        }
      },
      "__NONCE__": 1444777217.575749,
      "__SIGNATURE__": "HAFYXv9paHt/EQ35vQeR/TPbm48/maA0lKAav/u7kkl4womFuDh8emJRowoO0dHLfUEJO4NzlwxY3FpdwA9hDa4=",
      "__TYPE__": "/mktplace.transactions.MarketPlace/Transaction"
    }


**Example response**:

.. sourcecode:: http

    HTTP/1.1 200 OK
    Date: Mon, 22 Feb 2016 05:35:31 GMT
    Content-Length: 557
    Content-Type: application/json

    {
      "Transaction": {
        "Dependencies": [],
        "Nonce": 1444777217.496317,
        "Signature": "HAy35m01U0SNVbCBDUS+EQ8ufC1x7d1V2IAwRRqDQX4UhdKr3YMIiiHCTLLPrRCbyDB1jpiaemfDNoznqvd1eS4=",
        "TransactionType": "/MarketPlaceTransaction",
        "Update": {
          "Description": "MarketPlaceParticipant",
          "Name": "market",
          "UpdateType": "/mktplace.transactions.ParticipantUpdate/Register"
        }
      },
      "__NONCE__": 1444777217.575749,
      "__SIGNATURE__": "HAFYXv9paHt/EQ35vQeR/TPbm48/maA0lKAav/u7kkl4womFuDh8emJRowoO0dHLfUEJO4NzlwxY3FpdwA9hDa4=",
      "__TYPE__": "/mktplace.transactions.MarketPlace/Transaction"
    }