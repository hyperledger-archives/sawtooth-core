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

.. _update_create_settlement:

CreateSettlement
================

Attributes
----------

  ObjectId
    See 'object-id' in :ref:`object_type_settlement`.

    Optional

  OrderId
    See 'order-id' in :ref:`object_type_settlement`.

JSON Examples
-------------

Example:

.. code-block:: json

   {
       "UpdateType": "CreateSettlement",
       "ObjectId": "OBJECT_ID",
       "OrderId": "OBJECT_ID"
   }

check_valid()
-------------

The following checks are performed:

  - Check that all required attributes have been provided.
  - Check that all provided unique attributes do not exist in the store.
  - Check that OrderID references a valid order.
  - Check that the status of the order is 'Matched'.
  - Check that the bond and currency holdings of both the ordering
    and quoting organizations exist and have sufficient quantities to
    settle the trade.

Anyone is allowed to create a settlement, so no checks are done for
authorization.

apply()
-------

Create a new object in the store with object-type of ‘settlement’.
See :ref:`object_type_settlement`.

When a settlement is created, increment the order's ref count, and
the ref counts of the referenced objects in the settlement object
type, including: the ordering and quoting firm organizations, and the
bond and currency holdings for each organization.

Perform the exchange of the bond and currency holding quantities between
the specified holdings based on whether the action is 'Buy' or 'Sell'
(from the ordering firm's perspective).

Update the status of the referenced order to 'Settled'.
