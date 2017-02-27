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

.. _object_type_holding:

object-type: holding
====================

Attributes
----------

  object-id
    See :ref:`common_attributes`.

  object-type
    The string 'holding'.

  creator-id
    See :ref:`common_attributes`.

  ref-count:
    See :ref:`common_attributes`.

  owner-id
    The object-id of the organization which owns this holding.

  asset-type
    One of 'Currency' or 'Bond'.

  asset-id
    If asset-type is Bond, the asset-id will contain the object-id for
    that Bond.  For asset-type of Currency, this will be the string 'USD'.

  amount
    The current balance.

Example JSON
------------

Example 1:

.. code-block:: json

   {
       "object-id" : "<OBJECT_ID>",
       "object-type" : "holding",
       "creator-id": "<OBJECT_ID>",
       "ref-count": 1,
       "owner-id": "<OBJECT_ID>",
       "asset-type": "Currency",
       "asset-id": "USD",
       "amount": 100.00
   }

Example 2:

.. code-block:: json

   {
       "object-id" : "<OBJECT_ID>",
       "object-type" : "holding",
       "creator-id": "<OBJECT_ID>",
       "ref-count": 0,
       "owner-id": "<OBJECT_ID>",
       "asset-type": "Bond",
       "asset-id": "<OBJECT_ID>",
       "amount": 100.00
   }

Related Transaction Updates
---------------------------

- :ref:`update_create_holding`
