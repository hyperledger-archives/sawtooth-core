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

.. _object_type_order:

object-type: order
==================

Attributes
----------

  object-id
    See :ref:`common_attributes`.

  object-type
    The string 'order'.

  creator-id
    See :ref:`common_attributes`.

  action
    Either 'Buy' or 'Sell'.

  order-type
    Either 'Market' or 'Limit'.

  firm-id
    The organization the order is on behalf of. This should be the
    organization the creator of the order belongs to.

  cusip
    An identifier for the bond.

    See :ref:`object_type_bond`.

    Optional (one of isin or cusip must be set)

  isin
    An identifier for the bond.

    See :ref:`object_type_bond`.

    See: https://en.wikipedia.org/wiki/International_Securities_Identification_Number

    Optional (one of isin or cusip must be set)

  limit-price
    The maximum price the ordering firm is willing to pay for
    a bond or the minimum price they are willing to sell,
    depending on whether this is a buy or sell order.

    Optional (if order-type is "Limit", one of limit-price or
    limit-yield must be set. if order-type is "Market", this
    field should not be set)

  limit-yield
    The minumum yield at which the ordering firm is willing to
    buy a bond a bond or the maximum yield at which they are
    willing to sell, depending on whether this is a buy or sell order.

    Optional (if order-type is "Limit", one of limit-price or
    limit-yield must be set. if order-type is "Market", this
    field should not be set)

  quantity
    The quantity the firm wishes to buy or sell in USD as a multiple
    of the bond's par value. A 'round lot' for bonds is typically
    $100,000 against a par value of $1,000 per unit.

  quote-id
    The quote which is matched to this order.

    Optional (this is set on order quote matching as an update)

  status
    One of 'Open', 'Matched', or 'Settled'.

    'Open' means that the order has been created in the system and
    is waiting to be matched to a quote.

    'Matched' means that the order has been matched up with a quote
    which represents the highest sell price or lowest buy price
    which matches the requested quantity.

    'Settled' means that the counterparties had sufficient assets
    in their holdings to settle the trade and that asset transfer
    has occurred.

  timestamp
    The time that the quote is created in relation to the current clock.


Example JSON
------------

Buy Market example:

.. code-block:: json

   {
       "object-id": "OBJECT_ID",
       "object-type": "order",
       "creator-id": "OBJECT_ID",
       "firm-id": "OBJECT_ID",
       "order-type": "Market",
       "action": "Buy",
       "isin": "US00206RDA77",
       "quantity": 100000,
       "quote-id": "OBJECT_ID",
       "status": "Matched",
       "timestamp" : 1469045984.965841
   }

Sell Limit Price example:

.. code-block:: json

   {
       "object-id": "OBJECT_ID",
       "object-type": "order",
       "creator-id": "OBJECT_ID",
       "firm-id": "OBJECT_ID",
       "order-type": "Limit",
       "action": "Sell",
       "isin": "US00206RDA77",
       "limit-price": 100.859375,
       "quantity": 100000,
       "status": "Open",
       "timestamp" : 1469045984.965841
    }


Related Transaction Updates
---------------------------

- :ref:`update_create_order`
