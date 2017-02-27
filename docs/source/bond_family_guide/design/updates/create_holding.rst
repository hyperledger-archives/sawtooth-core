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

.. _update_create_holding:

CreateHolding
=============

Attributes
----------

  ObjectId
    See 'object-id' in :ref:`object_type_holding`.

    Optional

  OwnerID
    See 'owner-id' in :ref:`object_type_holding`.

  AssetType
    See 'asset-type' in :ref:`object_type_holding`.

  AssetID
    See 'asset-id' in :ref:`object_type_holding`.

  Amount
    See 'amount' in :ref:`object_type_holding`.

JSON Examples
-------------

Example 1:

.. code-block:: json

   {
       "UpdateType": "CreateHolding",
       "ObjectId": "OBJECT_ID",
       "OwnerId": "OBJECT_ID",
       "AssetType": "Currency",
       "AssetID": "USD",
       "Amount" : 1000000
   }

Example 2:

.. code-block:: json

   {
       "UpdateType": "CreateHolding",
       "ObjectId": "OBJECT_ID",
       "OwnerId": "OBJECT_ID",
       "AssetType": "Bond",
       "AssetID": "OBJECT_ID",
       "Amount" : 100
   }

check_valid()
-------------

The following checks are performed:

  - Check that all required attributes have been provided.
  - Check that all provided unique attributes do not exist in the store.
  - Check that OwnerID references a valid organization.
  - Check that AssetType is either "Currency" or "Bond".
  - If AssetType is "Currency", check that AssetID is "USD".
  - If AssetType is "Bond", check that AssetID references a valid bond.
  - Check that the referenced OwnerID does not already contain a Holding
    with an identical AssetType, AssetID combination. For example, if the
    organization already has a Currency holding in USD or a Bond holding
    for a given Bond object, then the new CreateHolding transaction should
    be considered invalid.

Anyone is allowed to create holdings, so no checks are done for
authorization.

For the purposes of the proof of concept, the check_valid()
method should additionally enforce that currency amounts should equal
$1B USD and Bond quantities should equal 1000 units on creation.

apply()
-------

Create a new object in the store with object-type of ‘holding’.

When a holding is created, increment the owner's ref count and the asset's
ref count (if the AssetType is "Bond"). Add the holding's object-id to
the owner's holdings list.
