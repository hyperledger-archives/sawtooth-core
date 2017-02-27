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

.. _update_delete_organization:

DeleteOrganization
==================

Attributes
----------

  ObjectId
    See 'object-id' in :ref:`object_type_organization`.
  
JSON Examples
-------------

.. code-block:: json

   {
       "UpdateType": "DeleteOrganization",
       "ObjectId": "OBJECT_ID"
   }

check_valid()
-------------

Only the participant set in the creator-id attribute may delete an
organization.  Also, the organization must have ref-count of 0, indicating
that no other items are using the organization.

The following checks are performed:

  - Authorization, as specified above.
  - Verify that ref-count is 0.

apply()
-------

Remove the organization from the store.
