.. _mktplace-data-model-label:

-----------------------------------------------------------------
MarketPlace Data Model
-----------------------------------------------------------------

As with other transaction families built on the Sawtooth Lake platform,
the MarketPlace Transaction Family is defined by an ordered log of
transactions. The implicit data model underlying the transaction family
provides a means for understanding and enforcing consistency in the
transaction log. This section describes the data model.

Every object in the implicit data model is referenced by an identifier
equivalent to the identifier of the transaction used to create the
object. The transaction identifier is a SHA256 hash of the message
signature.

Note that the authoritative log of transactions and the cached state of
objects associated with the log can be retrieved through the
:ref:`web-api-index-label`.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Participant
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A participant object refers to an organization or an
individual. Conceptually, the participant object refers to the "owner"
of an asset. Participants can create assets (and asset types), own
assets, offer to exchange assets, and transfer ownership to another
participant.

The current model for a participant is very simple: it is a means of
capturing the information necessary to authorize transactions on assets
owned by the participant.

.. code-block:: javascript

    "Participant" :
    {
        "type" : "object",
        "properties" :
        {
            "address" :
            {
                "type" : "string",
                "format" :  "ADDRESS",
                "required" : true
            },

            "name" :
            {
                "type" : "string",
                "required" : false
            },

            "description" :
            {
                "type" : "object",
                "required" : false
            }
        }
    }

The properties of a Participant include:

:address:
   a unique derivation of the verifying key (public key)
   for the transaction used to register the participant; the address
   provides a means of verifying the identity of participants for
   future transaction verification and authorization

:name:
   a unique name for the participant chosen by the person or
   organization creating the participant, names are constructed from
   printable ascii characters with the exception of '/'

:description:
   an optional property for describing in human
   readable form who or what the participant represents

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Account
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An account object represents a collection of holdings and liabilities
with at most one holding for each asset and at most one liability for
each asset type. An account is useful primarily as a means of managing
asset aggregation.

.. code-block:: javascript

        "Account" :
        {
            "type" : "object",
            "properties" :
            {
                "name" :
                {
                    "type" : "string",
                    "required" : false
                },

                "description" :
                {
                    "type" : "string",
                    "required" : false
                },

                "creator" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "$ref" : "#Participant",
                    "required" : true
                }
            }
        }

The properties of a Account include:

:name:
   a unique name for the object chosen by the person or
   organization creating the participant, names are constructed from
   printable ascii characters and must begin with '/'

:description:
   an optional property for describing in human
   readable form who or what the object represents

:creator:
   the identifier of the participant who registered the
   account object

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssetType
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An AssetType is a descriptor for a class of Assets. The creator of an
AssetType is granted the right to create Assets of the type and assign
them to owners within a Holding. If the Restricted flag is True (it is
True by default), then the creator of the AssetType is the only
participant who can create Assets of that type. This would be
appropriate, for example, for controlling creation of private stock
certificates. If the Restricted flag is False, then any Participant can
create Assets of that type and assign ownership to a participant within
a Holding. This would be appropriate for broad asset types like "brown
eggs" where many Participants are likely to create Assets of the type.

.. code-block:: javascript

        "AssetType" :
        {
            "type" : "object",
            "properties" :
            {
                "name" :
                {
                    "type" : "string",
                    "required" : false
                },

                "description" :
                {
                    "type" : "string",
                    "required" : false
                },

                "creator" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "$ref" : "#Participant",
                    "required" : true
                },

                "restricted" :
                {
                    "type" : "boolean",
                    "default" : true,
                    "required" : false
                }
            }
        }

The properties of a AssetType include:

:name:
   a unique name for the object chosen by the person or
   organization creating the participant, names are constructed from
   printable ascii characters and must begin with '/'

:description:
   an optional property for describing in human
   readable form who or what the object represents

:creator:
   the identifier of the participant who registered the
   account object

:restricted:
   a flag to indicate whether the creator of the asset
   type (if the flag is True) or other participants (if the flag is
   False) can create assets of the type

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Asset
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An Asset is an instance of an Asset Type. It is intended to represent a
"thing" to which value and ownership can be ascribed. Assets may be
strictly intrinsic to the MarketPlace such as instances of a virtual
currency or MarketPlace tokens. Alternatively, assets may provide a
MarketPlace handle for digital or physical objects that exist outside of
the MarketPlace.

.. code-block:: javascript

        "Asset" :
        {
            "type" : "object",
            "properties" :
            {
                "name" :
                {
                    "type" : "string",
                    "required" : false
                },

                "description" :
                {
                    "type" : "string",
                    "required" : false
                },

                "creator" :
                {
                    "format" : "IDENTIFIER",
                    "$ref" : "#Participant",
                    "required" : true
                },

                "asset-type" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "$ref" : "#AssetType",
                    "required" : true
                },

                "restricted" :
                {
                    "type" : "boolean",
                    "default" : true,
                    "required" : false
                },

                "consumable" :
                {
                    "type" : "boolean",
                    "default" : true,
                    "required" : false
                },

                "divisible" :
                {
                    "type" : "boolean",
                    "default" : false,
                    "required" : false
                }
            }
        }

The properties of a Asset include:

:name:
   a unique name for the object chosen by the person or
   organization creating the participant, names are constructed from
   printable ascii characters and must begin with '/'

:description:
   an optional property for describing in human
   readable form who or what the object represents

:creator:
   the identifier of the participant who registered the
   account object

:asset-type:
   the identifier of the asset type from which the
   asset was created

:restricted:
   a flag to indicate whether the creator of the asset
   (if the flag is True) or other participants (if the flag is
   False) can create Holdings for the asset with non-zero counts

:consumable:
   a flag to indicate whether assets are transferred
   (if the flag is True) or copied (if the flag is False); Holdings
   with non-consumable assets always have an instance count of zero
   or one since a non-consumable asset can be copied infinitely

:divisible:
   a flag to indicate whether fractional portions of
   assets are acceptable (if the flag is True)

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Holding
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A Holding object represents ownership of a collection of asset
instances and controls the right to transfer assets to a new owner. Any
participant can create an empty (i.e. the instance-count property is 0)
holding for any asset. An empty Holding represents a container into
which assets may be transferred. To create a holding with instance-count
greater than 0, the creator of the holding must be the creator of the
asset or the asset must be non-restricted.

.. code-block:: javascript

        "Holding" :
        {
            "type" : "object",
            "properties" :
            {
                "name" :
                {
                    "type" : "string",
                    "required" : false
                },

                "description" :
                {
                    "type" : "string",
                    "required" : false
                },

                "creator" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "$ref" : "#Participant",
                    "required" : true
                },

                "account" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "$ref" : "#Account",
                    "required" : true
                },

                "asset" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "$ref" : "#Asset",
                    "required" : true
                },

                "instance-count" :
                {
                    "type" : integer,
                    "required" : true
                }
            }
        }

The properties of a Holding include:

:name:
   a unique name for the object chosen by the person or
   organization creating the participant, names are constructed from
   printable ascii characters and must begin with '/'

:description:
   an optional property for describing in human
   readable form who or what the object represents

:creator:
   the identifier of the participant who registered the
   account object

:account:
   the identifier of the account used to scope the holding

:asset:
   the identifier of the asset that is held

:instance-count:
   the number of instances of the asset being held

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Liability
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Like a Holding, a Liability represents ownership though in the case of a
Liability ownership is of a debt or financial obligation. Where a
Holding captures ownership of specific asset instances, a Liability
captures a promise or guarantee for future ownership transfer of a
specific kind of asset.

.. code-block:: javascript

        "Liability" :
        {
            "type" : "object",
            "properties" :
            {
                "name" :
                {
                    "type" : "string",
                    "required" : false
                },

                "description" :
                {
                    "type" : "string",
                    "required" : false
                },

                "creator" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "$ref" : "#Participant",
                    "required" : true
                },

                "account" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "$ref" : "#Account",
                    "required" : true
                },

                "asset-type" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "$ref" : "#AssetType",
                    "required" : true
                },

                "instance-count" :
                {
                    "type" : integer,
                    "required" : true
                },

                "guarantor" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "$ref" : "#Participant",
                    "required" : true
                }
            }
        }

The properties of a Liability include:

:name:
   a unique name for the object chosen by the person or
   organization creating the participant, names are constructed from
   printable ascii characters and must begin with '/'

:description:
   an optional property for describing in human
   readable form who or what the object represents

:creator:
   the identifier of the participant who registered the
   account object

:account:
   the identifier of the account used to scope the holding

:asset-type:
   the identifier of the asset types

:instance-count:
   the number of instances of the asset being held

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ExchangeOffer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An ExchangeOffer represents an offer to exchange assets or liabilities
of one type for assets or liabilities of another type. Assets or
liabilities are received into an input holding or liability. The ratio
expresses the number of assets to be transferred out for every one that
is transferred in.

.. code-block:: javascript

        "ExchangeOffer" :
        {
            "type" : "object",
            "properties" :
            {
                "name" :
                {
                    "type" : "string",
                    "required" : false
                },

                "description" :
                {
                    "type" : "string",
                    "required" : false
                },

                "creator" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "$ref" : "#Participant",
                    "required" : true
                },

                "input" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "oneOf" : [
                        { "$ref" : "#Liability"},
                        { "$ref" : "#Holding" }
                    ],
                    "required" : true
                },

                "output" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "oneOf" : [
                        { "$ref" : "#Liability"},
                        { "$ref" : "#Holding" }
                    ],
                    "required" : true
                },

                "ratio" :
                {
                    "type" : float,
                    "required" : true
                },

                "minimum" :
                {
                    "type" : int,
                    "required" : false
                },

                "maximum" :
                {
                    "type" : int,
                    "required" : false
                },

                "execution" :
                {
                    "type" : "string",
                    "oneOf" : [ "ExecuteOnce", "ExecuteOncePerParticipant", "Any" ],
                    "required" : false
                }
            }
        }

The properties of an ExchangeOffer include:

:name:
   a unique name for the object chosen by the person or
   organization creating the participant, names are constructed from
   printable ascii characters and must begin with '/'

:description:
   an optional property for describing in human
   readable form who or what the object represents

:creator:
   the identifier of the participant who registered the
   account object

:input:
   a Holding or Liability into which "payment" is made, this
   defines the kind of asset that will be received by the creator of
   the offer

:output:
   a Holding or Liability from which goods will be
   transferred, this defines the kind of asset that will be given by
   the creator of the offer, the creator of the offer must be the
   same as the creator of the holding or liability

:ratio:
   the number of instances to transfer from the output
   holding for each instance deposited into the input holding

:minimum:
   the smallest number of acceptable instances that can be
   transferred into the input holding for the offer to be valid

:maximum:
   the largest number of acceptable instances that can
   be transferred into the input holding in one transaction for the
   offer to be valid

:execution:
   a modifier that defines additional conditions for
   execution of the offer, it may have one of the following values:

   ExecuteOncePerParticipant
      the offer may be executed by a participant at most one time

   ExecuteOnce
      the offer may be executed at most one time

   Any
      the offer may be executed as often as appropriate

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
SellOffer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A SellOffer is identical to an ExchangeOffer except that assets must be
transferred out from a Holding.

.. code-block:: javascript

        "SellOffer" :
        {
            "type" : "object",
            "properties" :
            {
                "name" :
                {
                    "type" : "string",
                    "required" : false
                },

                "description" :
                {
                    "type" : "string",
                    "required" : false
                },

                "creator" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "$ref" : "#Participant",
                    "required" : true
                },

                "input" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "oneOf" : [
                        { "$ref" : "#Liability"},
                        { "$ref" : "#Holding" }
                    ],
                    "required" : true
                },

                "output" :
                {
                    "type" : "string",
                    "format" : "IDENTIFIER",
                    "$ref" : "#Holding",
                    "required" : true
                },

                "ratio" :
                {
                    "type" : float,
                    "required" : true
                },

                "minimum" :
                {
                    "type" : int,
                    "required" : false
                },

                "maximum" :
                {
                    "type" : int,
                    "required" : false
                },

                "execution" :
                {
                    "type" : "string",
                    "oneOf" : [ "ExecuteOnce", "ExecuteOncePerParticipant", "Any" ],
                    "required" : false
                }
            }
        }

The properties of a SellOffer include:

:name:
   a unique name for the object chosen by the person or
   organization creating the participant, names are constructed from
   printable ascii characters and must begin with '/'

:description:
   an optional property for describing in human
   readable form who or what the object represents

:creator:
   the identifier of the participant who registered the
   account object

:input:
   a Holding or Liability into which "payment" is made, this
   defines the kind of asset that will be received by the creator of
   the offer

:output:
   a Holding from which goods will be transferred, this
   defines the kind of asset that will be given by the creator of the
   offer, the creator of the offer must be the same as the creator of
   the holding

:ratio:
   the number of instances to transfer from the output
   holding for each instance deposited into the input holding

:minimum:
   the smallest number of acceptable instances that can be
   transferred into the input holding for the offer to be valid

:maximum:
   the largest number of acceptable instances that can
   be transferred into the input holding in one transaction for the
   offer to be valid

:execution:
   a modifier that defines additional conditions for
   execution of the offer, it may have one of the following values:

   :ExecuteOncePerParticipant:
      the offer may be executed by a
      participant at most one time

   :ExecuteOnce:
      the offer may be executed at most one time

   :Any:
      the offer may be executed as often as appropriate
