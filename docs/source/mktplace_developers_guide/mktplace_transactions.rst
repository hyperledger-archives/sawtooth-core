.. _mktplace-transactions-label:

-----------------------------------------------------------------
MarketPlace Transactions
-----------------------------------------------------------------

All MarketPlace transactions have the following fields:

:Dependencies:
   a list of transaction identifiers that must be
   committed to the log before this transaction is committed

:Nonce:
   a uniquifier for the transaction, we use a wallclock time
   stamp though any float value will suffice; it is the creator of the
   transaction that is responsible for choosing a value that will result
   in unique signatures.

:Signature:
   the signature of the transaction content only; the
   signature of the transaction is computed over the CBOR encoding of
   the transaction with keys sorted alphabetically

:TransactionType:
   the name of the transaction family, all MarketPlace
   transactions use "/MarketPlaceTransaction" as the TransactionType.

:Update:
   information about the actual change that will be applied to
   the MarketPlace ledger.


There are no optional fields in MarketPlace transactions. A value must
be specified for every field for the purposes of consistency in
signing. The MarketPlace Client API provides a simple means for filling
in reasonable default values, but other clients must ensure that the
serialized object contains values for all specified fields.

-----------------------------------------------------------------
MarketPlace Transaction Updates
-----------------------------------------------------------------

The Update object contains an UpdateType field that describes the change
to be applied to the ledger. There are three basic types of updates. The
first to add or remove objects from the ledger:

:Register:
   Create a new object. All register updates have a name and
   description field. The name field must be unique for a particular
   creator. All updates except the update used to register a new
   participant must have a creator field that containts the participant
   identifier for the player creating the object.

:Unregister:
   Destroy an existing object. Unregister updates all
   contain one field, the object identifier of the object to destroy.

The final type of update, Exchange, transfers the balance from one
holding/liability object to another through a series of offers.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Register Participant
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: javascript

        "Update" :
        {
          "UpdateType": "/mktplace.transactions.ParticipantUpdate/Register"
          "Description": "MarketPlace Participant",
          "Name": "market",
        }



^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Register Account
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The fields for account registration include:

:CreatorID:
   the identifier for the participant requesting creation of
   the new object

.. code-block:: javascript

        "Update" :
        {
          "CreatorID": "1b452fc363a3e024",
          "Description": "",
          "Name": "/private/account",
          "UpdateType": "/mktplace.transactions.AccountUpdate/Register"
        }

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Register Asset Type
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The fields for asset type registration include:

:CreatorID:
   The identifier for the participant requesting creation of
   the new object

.. code-block:: javascript

        "Update":
        {
          "CreatorID": "1b452fc363a3e024",
          "Description": "Currency asset type",
          "Name": "/asset-type/currency",
          "UpdateType": "/mktplace.transactions.AssetTypeUpdate/Register"
        }

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Register Asset
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The fields for asset registration include:

:CreatorID:
   The identifier for the participant requesting creation of
   the new object

:AssetTypeID:
   The identifier for the asset type, the only participant
   allowed to create an asset with the type is the participant who
   created the type


.. code-block:: javascript

        "Update":
        {
          "AssetTypeID": "77dfddc9936745fc",
          "CreatorID": "1b452fc363a3e024",
          "Description": "",
          "Name": "/asset/currency/mikel",
          "UpdateType": "/mktplace.transactions.AssetUpdate/Register"
        }

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Register Holding
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The fields for holding registration include:

:CreatorID:
   The identifier for the participant requesting creation of
   the new object

:AssetID:
   The identifier for the asset stored in the holding

:Count:
   The number of assets stored in the holding

:AccountID:
   The identifier for the account used to manage the holding

.. code-block:: javascript

        "Update":
        {
          "AssetID": "b6bdf0368de9855a",
          "Count": 1000000,
          "CreatorID": "1b452fc363a3e024",
          "Description": "",
          "Name": "/private/holding/currency/mikel",
          "UpdateType": "/mktplace.transactions.HoldingUpdate/Register",
          "AccountID": "bb3613256325c35a"
        }

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Register Liability
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The fields for liability registration include:

:CreatorID:
   The identifier for the participant requesting creation of
   the new object

:AssetTypeID:
   The identifier for the asset stored in the holding

:Count:
   The number of assets stored in the holding

:AccountID:
   The identifier for the account used to manage the holding

:GuarantorID:
   The identifier for the participant who guarantees the
   liability

.. code-block:: javascript

        "Update":
        {
          "AssetTypeID": "b6bdf0368de9855a",
          "Count": 1000000,
          "GuarantorID": "1b452fc363a3e024",
          "CreatorID": "1b452fc363a3e024",
          "Description": "",
          "Name": "/private/holding/currency/mikel",
          "UpdateType": "/mktplace.transactions.LiabilityUpdate/Register",
          "AccountID": "bb3613256325c35a"
        }

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Register ExchangeOffer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The fields for registration of a SellOffer include:

:CreatorID:
   The identifier for the participant requesting creation of
   the new object

:InputID:
   The identifier for the holding (or liability) into which
   assets will be transferred (e.g. the holding where payment is
   received)

:OutputID:
   The identifier for the holding (or liability) from which
   assets will be tranferred (e.g. the holding for assets being
   purchased)

:Ratio:
   The number of output assets transferred per input asset

:Minimum:
   the smallest number of acceptable instances that can be
   transferred into the input holding for the offer to be valid,
   minimum must strictly be smaller than maximum

:Maximum:
   the largest number of acceptable instances that can
   be transferred into the input holding in one transaction for the
   offer to be valid, maximum must strictly be larger than minimum

:Execution:
   a modifier that defines additional conditions for
   execution of the offer, it may have one of the following values:

   :ExecuteOncePerParticipant:
      the offer may be executed by a participant at most one time

   :ExecuteOnce:
      the offer may be executed at most one time

   :Any:
      the offer may be executed as often as appropriate

.. code-block:: javascript

        "Update":
        {
          "CreatorID": "5863bd0527ca2143",
          "Description": "",
          "InputID": "53434b20963cb525",
          "Name": "/offer/buyback/bills",
          "OutputID": "cc007e32955254a7",
          "Ratio": 93,
          "Execution": "Any",
          "Maximum": 1000000000,
          "Minimum": 1,
          "UpdateType": "/mktplace.transactions.ExchangeOfferUpdate/Register"
        }

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Register SellOffer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The fields for registration of a SellOffer include:

:CreatorID:
   The identifier for the participant requesting creation of
   the new object

:InputID:
   The identifier for the holding (or liability) into which
   assets will be transferred (e.g. the holding where payment is
   received)

:OutputID:
   The identifier for the holding from which assets will be
   tranferred (e.g. the holding for assets being purchased)

:Ratio:
   The number of output assets transferred per input asset

:Minimum:
   the smallest number of acceptable instances that can be
   transferred into the input holding for the offer to be valid,
   minimum must strictly be smaller than maximum

:Maximum:
   the largest number of acceptable instances that can
   be transferred into the input holding in one transaction for the
   offer to be valid, maximum must strictly be larger than minimum

:Execution:
   a modifier that defines additional conditions for
   execution of the offer, it may have one of the following values:

   :ExecuteOncePerParticipant:
      the offer may be executed by a participant at most one time

   :ExecuteOnce:
      the offer may be executed at most one time

   :Any:
      the offer may be executed as often as appropriate

.. code-block:: javascript

        "Update":
        {
          "CreatorID": "5863bd0527ca2143",
          "Description": "",
          "InputID": "53434b20963cb525",
          "Name": "/offer/buyback/bills",
          "OutputID": "cc007e32955254a7",
          "Ratio": 93,
          "Execution": "Any",
          "Maximum": 1000000000,
          "Minimum": 1,
          "UpdateType": "/mktplace.transactions.SellOfferUpdate/Register"
        }

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Unregister All Objects
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The fields used to unregister an object are consistent across all object
types and include:

:CreatorID:
   The identifier for the participant requesting creation of
   the new object

:ObjectID:
   The identifier for the object to unregister

.. code-block:: javascript

        "Update":
        {
          "CreatorID": "5863bd0527ca2143",
          "ObjectID": "ad8d6a71827e9be0",
          "UpdateType": "/mktplace.transactions.SellOfferUpdate/Unregister"
        }


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Exchange
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The exchange update transfers balances between holdings. The exchange
starts from an initial holding/liability and passes through a specified
series of sell offers until the final transfer is made. Asset types must
be consistent across each transfer.

:InitialLiabilityID:
   the identifier for the initial holding/liability
   from which assets are transferred (e.g. from which payment is made)

:FinalLiabilityID:
   the identifier for the holding/liability into which
   assets are ultimately transferred (e.g. the holding where goods
   purchased are placed)

:InitialCount:
   the number of assets to transfer out of the initial
   liability (e.g. the amount paid)

:OfferIDList:
   a list of identifiers for sell offers that will be
   applied in order to tranfer assets.

.. code-block:: javascript

        "Update":
        {
          "FinalLiabilityID": "8a67d29135306115",
          "InitialCount": 10,
          "InitialLiabilityID": "84272ffad75a8043",
          "OfferIDList": [],
          "UpdateType": "/mktplace.transactions.ExchangeUpdate/Exchange"
        }

