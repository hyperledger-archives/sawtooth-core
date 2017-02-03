..
   Copyright 2017 Intel Corporation

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

.. _object_type_quote:

object-type: quote
==================


Attributes
----------

  object-id
    See :ref:`common_attributes`.

  object-type
    The string 'quote'.

  creator-id
    See :ref:`common_attributes`.

  firm
    The pricing source of the organization associated with this quote.

  cusip
    An identifier for the bond.

    See :ref:`object_type_bond`.

    Optional (one of ison or cusip must be set)

  isin
    And identifier for this bond.

    See :ref:`object_type_bond`.

    See: https://en.wikipedia.org/wiki/International_Securities_Identification_Number

    Optional (one of ison or cusip must be set)

  ask-price
    The minimum price for which the firm is willing to sell the bond.

  ask-qty
    The maximum quantity the firm is willing to sell.

  bid-price
    The maximum price the firm is willing to pay to buy this bond.

  bid-qty
    The maximum quantity the firm is willing to buy.

  timestamp
    The time that the quote is created in relation to the current clock.

  status
    One of 'Open' or 'Closed'.

    Quotes are 'Open' if they have sufficient remaining buy and
    sell quantities and have not been explicitly cancelled.

    Quotes move to 'Closed' status if they can no longer fulfill
    a round-lot order (buy or sell quantity < 100000) or if they
    are explicitly cancelled by an authorized member of the firm
    associated with the quote.

Example JSON
------------

.. code-block:: json

   {
       "object-id" : "OBJECT_ID",
       "object-type" : "quote",
       "creator-id": "OBJECT_ID",
       "firm" : "SCGV",
       "isin" : "US00206RDA77",
       "ask-price" : "101-06 7/8",
       "ask-qty" : 1000000,
       "bid-price" : "101-05 7/8",
       "bid-qty" : 1000000,
       "timestamp" : 1469045984.965841,
       "status" : "Open"
    }

Related Transaction Updates
---------------------------
- :ref:`update_create_quote`
