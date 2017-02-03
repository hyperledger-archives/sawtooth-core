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

.. _update_update_participant:

UpdateParticipant
=================

Attributes
----------

  ObjectId
    See 'object-id' in :ref:`object_type_participant`.

  Username
    See 'username' in :ref:`object_type_participant`.

  FirmId
    See 'firm-id' in :ref:`object_type_participant`.

    Optional

JSON Example
------------

.. code-block:: json

   {
       "UpdateType": "CreateParticipant",
       "ObjectId": "OBJECT_ID",
       "Username": "tjsmith",
       "FirmId": "OBJECT_ID"
   }

check_valid()
-------------

Participants may only be modified by their creator, which can be verified
by comparing the key-id to the key used to sign the transaction.

The following checks are performed:

  - Authorization, as described above.
  - Check that all required attributes have been provided.
  - Check that all provided unique attributes do not exist in the store.
  - Check that FirmId, if specified, is a valid organization in the store.

apply()
-------

If FirmId was present and it is being modified or removed, then decrement
the ref-count for that organization.

If FirmId is being modified or added, then increment the ref-count for the
new organization being referenced.

Update the object with the fields provided, removing any optional fields if
they were not specified.
