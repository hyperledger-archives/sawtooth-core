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

.. _update_update_organization_authorization:

UpdateOrganizationAuthorization
===============================

Attributes
----------

  ObjectId
    See 'object-id' in :ref:`object_type_organization`.

  Action
    One of 'add' or 'remove'.  If set to 'add, then this is a request
    to add an entry to the list; if it is remove, then it is a request
    to remove an entry.

  ParticipantId
    See 'authorization' in :ref:`object_type_organization`.

  Role
    See 'authorization' in :ref:`object_type_organization`.


JSON Examples
-------------

Example 1:

.. code-block:: json

   {
       "UpdateType": "UpdateOrganizationAuthorization",
       "ObjectId": "OBJECT_ID",
       "Action": "add",
       "ParticipantId": "OBJECT_ID",
       "Role": "marketmaker",
   }

Example 2:

.. code-block:: json

   {
       "UpdateType": "UpdateOrganizationAuthorization",
       "ObjectId": "OBJECT_ID",
       "Action": "remove",
       "ParticipantId": "OBJECT_ID",
       "Role": "marketmaker",
   }

check_valid()
-------------

Any participant is allowed to add/remove themselves from the authorization
list.  Only the organization's creator may add/remove other participants.

The following checks are performed:

  - Authorization, as described above.
  - Check that all required attributes have been provided.
  - If it is an add, check that the requested (participant-id, role) is not
    already set for this organization (it is an error to set it twice).
  - If it is a remove, check that the (participant-id, role) already exists
    (it is an error to remove an entry that does not exist).
  - Verify that Role is one of the allowed valid string (see definition of
    organization).

apply()
-------

If adding, increment the ref-count for the associated participant object.

If removing, decrement the ref-count for the associated participant object.

Add or remove the (participant-id, role) from the authorization list.
