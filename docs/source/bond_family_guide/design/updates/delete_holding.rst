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

.. _update_delete_holding:

DeleteHolding
=============

Attributes
----------

  ObjectId
    See 'object-id' in :ref:`object_type_holding`.

JSON Examples
-------------

.. code-block:: json

   {
       "UpdateType": "DeleteHolding",
       "ObjectId": "OBJECT_ID"
   }

check_valid()
-------------

Only a participant who has an admin role for the organization referenced
by the owner-id on the holding may delete a holding.

Also, the holding must have ref-count of 0, indicating that no other items
are using the holding.

The following checks are performed:

  - Authorization, as specified above.
  - Verify that ref-count is 0.

apply()
-------

Remove the holding from the store.

Decrement the owner's ref count and the asset's ref count (if the
AssetType of this holding is "Bond").
