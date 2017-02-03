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

.. _update_create_order:

CreateOrder
===========

Attributes
----------

  ObjectId
    See 'object-id' in :ref:`object_type_order`.

    Optional

  Action
    See 'action' in :ref:`object_type_order`.

  OrderType
    See 'order-type' in :ref:`object_type_order`.

  FirmId
    See 'firm-id' in :ref:`object_type_order`.

  Cusip
    See 'cusip' in :ref:`object_type_order`.

    Optional

  Isin
    See 'isin' in :ref:`object_type_order`.

    Optional

  Quantity
    See 'quantity' in :ref:`object_type_order`.

  Status
    See 'status' in :ref:`object_type_order`.

  LimitPrice
    See 'limit-price' in :ref:`object_type_order`.

  LimitYield
    See 'limit-yield' in :ref:`object_type_order`.

JSON Examples
-------------

Example 1:

.. code-block:: json

   {
       "UpdateType": "CreateOrder",
       "Action": "Buy",
       "OrderType": "Limit",
       "FirmId": "OBJECT_ID",
       "Isin": "US00206RDA77",
       "Quantity": 1000,
       "LimitPrice": "98-05.875",
       "LimitYield": 0.015
   }

Example 2:

.. code-block:: json

   {
       "UpdateType": "CreateOrder",
       "Action": "Sell",
       "OrderType": "Market",
       "FirmId": "OBJECT_ID",
       "Isin": "US00206RDA77",
       "Quantity": 1000
   }

check_valid()
-------------

The following checks are performed:

  - Check that all required attributes have been provided.
  - Check that all provided unique attributes do not exist in the store.
  - Check that FirmId is a valid object-id of type organization.
  - Check that one of Cusip or Isin is provided, and points to a
    valid bond.  If both are provided, they must point to the same
    bond.

apply()
-------

Create a new object in the store with object-type of ‘order’.  The
default for status should be set to 'Open'.

Increment the ref-count of the corresponding organization and bonds.
