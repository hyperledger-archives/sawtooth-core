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

.. _update_create_bond:

CreateBond
==================

Attributes
----------

  ObjectId
    See 'object-id' in :ref:`object_type_bond`.

    Optional

  Issuer
    See 'issuer' in :ref:`object_type_bond`.

  Isin
    See 'isin' in :ref:`object_type_bond`.

    Optional

  Cusip
    See 'cusip' in :ref:`object_type_bond`.

    Optional

  CorporateDebtRatings
    See 'corporate-debt-ratings' in :ref:`object_type_bond`.

  FirstSettlementDate
    See 'first-settlement-date' in :ref:`object_type_bond`.

    Optional

  FirstCouponDate
    See 'first-coupon-date' in :ref:`object_type_bond`.

  AmountOutstanding
    See 'amount-outstanding' in :ref:`object_type_bond`.

  MaturityDate
    See 'maturity-date' in :ref:`object_type_bond`.

  CouponType
    See 'coupon-type' in :ref:`object_type_bond`.

  CouponRate
    See 'coupon-rate' in :ref:`object_type_bond`.

  CouponFrequency
    See 'coupon-frequency' in :ref:`object_type_bond`.

  CouponBenchmark
    See 'coupon-benchmark' in :ref:`object_type_bond`.

    Optional

  FaceValue
    See 'face-value' in :ref:`object_type_bond`.

JSON Examples
-------------

Example 1:

.. code-block:: json

  {
      "UpdateType": "CreateBond",
      "ObjectId": "OBJECT_ID",
      "Issuer": "T",
      "Isin": "US00206RDA77",
      "Cusip": "00206RDA7",
      "AmountOutstanding": 2250000000,
      "CorporateDebtRatings" : {
          "Fitch" : "BBB",
          "Moodys" : "Ba3",
          "S&P" : "BBB-"
      },
      "CouponBenchmark" : "Libor",
      "CouponRate" : 0.015,
      "CouponType" : "Floating",
      "CouponFrequency" : "Quarterly",
      "FirstSettlementDate" : "01/11/2012",
      "FirstCouponDate": "04/01/2012",
      "MaturityDate" : "01/11/2022",
      "FaceValue": 1000
   }

check_valid()
-------------

The following checks are performed:

  - Check that all required attributes have been provided.
  - Check that all provided unique attributes do not exist in the store.
  - Check that Issuer is a valid organization.
  - Check that at least one of Isin or Cusip is provided. Also check that there
    is no other bond with those Isin or Cusip.
  - Check that the Coupon Type is either Fixed or Floating. If it is Floating,
    the Coupon Benchmark must be set to one of the following Libor benchmarks:
    Overnight, OneWeek, OneMonth, TwoMonth, ThreeMonth, SixMonth, or OneYear.
  - Check the Maturity date is in the format MM/DD/YYYY.
  - Check that the CouponFrequency is one of 'Quarterly', 'Monthly', or 'Daily'
  - Check that the FirstCouponDate is in the format MM/DD/YYYY.


apply()
-------

Create a new object in the store with object-type of ‘bond’.
