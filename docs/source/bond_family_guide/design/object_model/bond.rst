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

.. _object_type_bond:

object-type: bond
=================


Attributes
----------

  object-id
    See :ref:`common_attributes`.

  object-type
    The string 'bond'.

  creator-id
    See :ref:`common_attributes`.

  ref-count
    See :ref:`common_attributes`.

  issuer
    The ticker symbol of the organization which issued the bond.

  cusip
    An identifier for this bond.  Used for US Treasury bonds.

    See: https://en.wikipedia.org/wiki/CUSIP

    Indexed, Unique, Optional (one of isin or cusip must be set)

  isin
    And identifier for this bond.  Used for corporate bonds.

    See: https://en.wikipedia.org/wiki/International_Securities_Identification_Number

    Indexed, Unique, Optional (one of isin or cusip must be set)

  corporate-debt-ratings
    A key/value map of rating agency to rating.  This is used for
    display purposes only.

  coupon-benchmark
    The benchmark interest rate index to use to determine the rate which
    will be added to coupon-rate.  If set, must be the string 'Libor'.

    Required if coupon-type is 'Floating'

  coupon-rate
    The yearly rate of interest paid in coupons.

    See: https://en.wikipedia.org/wiki/Coupon_(bond)

  coupon-type
    Either 'Fixed' or 'Floating'.  If fixed, the coupon-rate is used as-is.
    If floating, the interest rate is calculated by adding coupon-rate to
    the rate looked up using the benchmark index (Libor).

  coupon-frequency
	Options are limited to 'Quarterly', 'Monthly', or 'Daily' for the purposes of
	this PoC. There is significant complexity to coupon frequency and day
	counting in the real market. We will simplify this to first of the quarter,
	first of the month, or days.

  first-coupon-date
    The date the first coupon can be paid for the bond. This should align
    with the start of a quarter for coupon-frequency of 'Quarterly', the
    start of a month for coupon-frequency of 'Monthly', or any day for
    'Daily'. Format: MM/DD/YYYY.

  maturity-date
    The date on which the bond becomes worth it's face value and can be
    redeemed.  Format: MM/DD/YYYY.

  face-value
    The par-value of the bond, to be paid upon maturity.

  first-settlement-date
    For display only.

    Optional

Example JSON
------------

.. code-block:: json

   {
       "object-id" : "<OBJECT_ID>",
       "object-type" : "bond",
       "creator-id": "<OBJECT_ID>",
       "ref-count": 1,
       "issuer" : "T",
       "isin" : "US00206RDA77",
       "cusip" : "00206RDA7",
       "amount-outstanding" : 2250000000,
       "corporate-debt-ratings" : {
           "Fitch" : "BBB",
           "Moodys" : "Ba3",
           "S&P" : "BBB-"
       },
       "coupon-benchmark" : "ThreeMonth",
       "coupon-rate" : 0.015,
       "coupon-type" : "Floating",
       "coupon-frequency" : "Quarterly",
       "first-settlement-date" : "01/11/2012",
       "first-coupon-date" : "03/31/2012",
       "maturity-date" : "01/11/2022",
       "face-value": 1000
    }

Related Transaction Updates
---------------------------
- :ref:`update_create_bond`
