-----------------------------------------------------------------
MarketPlace Messages
-----------------------------------------------------------------

MarketPlace ledger clients can send messages to validators through an
HTTP/POST interface. Messages are JSON-encoded for example:

.. code-block:: javascript

    {
      "Transaction": {
        "Dependencies": [],
        "Nonce": 1444777217.496317,
        "Signature": "HAy35m01U0SNVbCBDUS+EQ8ufC1x7d1V2IAwRRqDQX4UhdKr3YMIiiHCTLLPrRCbyDB1jpiaemfDNoznqvd1eS4=",
        "TransactionType": "/MarketPlaceTransaction",
        "Update": {
          "UpdateType": "/mktplace.transactions.ParticipantUpdate/Register"
          "Description": "MarketPlace Participant",
          "Name": "market",
        }
      },
      "__NONCE__": 1444777217.575749,
      "__SIGNATURE__": "HAFYXv9paHt/EQ35vQeR/TPbm48/maA0lKAav/u7kkl4womFuDh8emJRowoO0dHLfUEJO4NzlwxY3FpdwA9hDa4=",
      "__TYPE__": "/mktplace.transactions.MarketPlace/Transaction"
    }

Messages contain one of the :ref:`mktplace-transactions-label` and three
additional fields:

:__NONCE__:
   random float used to ensure the message signature is unique;
   we use the python representation of wall clock time

:__TYPE__:
    the type of message; for all MarketPlace transactions the
    message type is
    "/mktplace.transactions.MarketPlace/Transaction"

:__SIGNATURE__:
   the message signature is computed using all fields in
   the message except for the __SIGNATURE__ field.

