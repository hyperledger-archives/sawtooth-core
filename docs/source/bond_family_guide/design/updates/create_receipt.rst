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

.. _update_create_receipt:

CreateReceipt
==============

Attributes
----------

  ObjectId
    See 'object-id' in :ref:`object_type_receipt`.

    Optional

  PaymentType
    See 'payment-type' in :ref:`object_type_receipt`.

  BondId
    See 'bond-id' in :ref:`object_type_receipt`.

  PayeeId
    See 'payee-id' in :ref:`object_type_receipt`.

  CouponDate
    See 'coupon-date' in :ref:`object_type_receipt`.

    Optional

    Required if PaymentType is Coupon


JSON Examples
-------------

Example 1:

.. code-block:: json

   {
       "UpdateType": "CreateReceipt",
       "PaymentType": "Coupon",
       "BondId": "OBJECT_ID",
       "PayeeId": "OBJECT_ID",
       "CouponDate": "10/03/2015"
   }

check_valid()
-------------

The following checks are performed:

  - Check that all required attributes have been provided.
  - Check that all provided unique attributes do not exist in the store.
  - Check that PaymentType is either Coupon or Redemption
  - Check that the BondId reference a valid bond
  - Check that the PayeeId reference an organization and that it has holdings
    in the bond and USD Currency holding.
  - Check that the Payer has enough funds to pay and that if it is a Redemption
    they have the bond holding.
  - Check the date to see if it valid for the PaymentType. For Coupon, check
    that the date falls on a valid date for the coupon frequency of the bond.
    For Redemption, check that the date is after the bonds maturity date.

apply()
-------

Create a new object in the store with object-type of ‘receipt’. Also add the
'receipt' to the Payee's receipt list. Exchange the currency amount required
and, if it is a Redemption, return bonds to the issuer.

Increment the ref-count of the corresponding bond.
