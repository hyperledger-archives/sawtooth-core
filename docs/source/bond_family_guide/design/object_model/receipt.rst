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

.. _object_type_receipt:

object-type: receipt
====================

Attributes
----------

  object-id
    See :ref:`common_attributes`.

  object-type
    The string 'receipt'.

  creator-id
    See :ref:`common_attributes`.

  bond-id
    The object-id of the bond for which this payment occurred.

  payee-id
    The object-id of the organization to which the payment was paid.

  payment-type
    One of 'Coupon' or 'Redemption'.

  coupon-date
    The date of the coupon.  This is the date that it became due.

    Format: MM/DD/YYYY

    Required if payment-type is 'Coupon'.

  amount
    The amount paid.

  timestamp
    The time that the receipt is created in relation to the current clock.

Example JSON
------------

Coupon example:

.. code-block:: json

   {
       "object-id" : "OBJECT_ID",
       "object-type" : "receipt",
       "creator-id": "OBJECT_ID",
       "bond-id": "OBJECT_ID",
       "payee-id": "OBJECT_ID",
       "payment-type": "Coupon",
       "coupon-date": "10/03/2015",
       "amount": 100.00,
       "timestamp" : 1469045984.965841
   }

Bond redemption example:

.. code-block:: json

   {
       "object-id" : "OBJECT_ID",
       "object-type" : "holding",
       "creator-id": "OBJECT_ID",
       "bond-id": "OBJECT_ID",
       "payee-id": "OBJECT_ID",
       "payment-type": "Redemption",
       "amount": 1000.00,
       "timestamp" : 1469045984.965841
   }

Related Transaction Updates
---------------------------

- :ref:`update_create_receipt`
