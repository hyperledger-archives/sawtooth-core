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

.. _object_type_settlement:

object-type: settlement
=======================

Attributes
----------

  object-id
    See :ref:`common_attributes`.

  object-type
    The string 'settlement'.

  creator-id
    See :ref:`common_attributes`.

  order-id
    The object-id of the order which is being settled.

  ordering-firm-id
    The object-id of the firm on whose behalf the order was entered.

  quoting-firm-id
    The object-id of the firm that supplied the quote matched with the
    order.

  order-bond-holding-id
    The object-id of the bond holding of the ordering firm.

  order-currency-holding-id
    The object-id of the currency holding of the ordering firm.

  quote-bond-holding-id
    The object-id of the bond holding of the quoting firm.

  quote-currency-holding-id
    The object-id of the currency holding of the quoting firm.

  action
    Either 'Buy' or 'Sell'. This is from the perspective of the ordering
    firm.

  bond-quantity
    The quantity of bonds that are transferred.

  currency-amount
    The amount of cash that is transferred. This is calculated by
    determining the number of units of the bond and multiplying by
    the matched quote's asking price (in case of a "Buy" action) or
    the matched quote's bid price (in case of a "Sell" action).


Example JSON
------------

.. code-block:: json

   {
       "object-id" : "OBJECT_ID",
       "object-type" : "settlement",
       "creator-id": "OBJECT_ID",
       "order-id": "OBJECT_ID",
       "ordering-firm-id": "OBJECT_ID",
       "quoting-firm-id": "OBJECT_ID",
       "order-bond-holding-id": "OBJECT_ID",
       "order-currency-holding-id": "OBJECT_ID",
       "quote-bond-holding-id": "OBJECT_ID",
       "quote-currency-holding-id": "OBJECT_ID",
       "action": "Buy",
       "bond-quantity": 100000,
       "currency-amount": 109300
   }

Related Transaction Updates
---------------------------

- :ref:`update_create_settlement`
