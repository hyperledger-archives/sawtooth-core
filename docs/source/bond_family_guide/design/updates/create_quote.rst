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

.. _update_create_quote:

CreateQuote
===========

Attributes
----------

  ObjectId
    See 'object-id' in :ref:`object_type_quote`.

    Optional

  Firm
    See 'firm' in :ref:`object_type_quote`.

  Cusip
    See 'cusip' in :ref:`object_type_quote`.

    Optional

  Isin
    See 'isin' in :ref:`object_type_quote`.

    Optional

  AskPrice
    See 'ask-price' in :ref:`object_type_quote`.

  AskQty
    See 'ask-qty' in :ref:`object_type_quote`.

  BuyPrice
    See 'buy-price' in :ref:`object_type_quote`.

  BuyQty
    See 'buy-qty' in :ref:`object_type_quote`.


JSON Examples
-------------

.. code-block:: json

   {
       "UpdateType": "CreateQuote",
       "Firm": "SCGV",
       "Isin": "US00206RDA77",
       "BidPrice": "98-05.875",
       "BidQty": 25000,
       "AskPrice": "98-06.875",
       "AskQty": 25000
   }

check_valid()
-------------

CreateQuote may only be submitted by a 'marketmaker' (as defined in
the organization's authorized list) for the Firm listed on the
quote.

The following checks are performed:

  - Check that all required attributes have been provided.
  - Check that all provided unique attributes do not exist in the store.
  - Check that Firm is a valid object-id of type organization.
  - Check that one of Cusip or Isin is provided, and points to a
    valid bond.  If both are provided, they must point to the same
    bond.
  - Authorization checks, as defined above.

apply()
-------

Create a new object in the store with object-type of ‘quote’.

Increment the ref-count of the corresponding organization.
