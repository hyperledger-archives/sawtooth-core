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

.. _update_create_participant:

CreateParticipant
=================

Attributes
----------

  ObjectId
    See 'object-id' in :ref:`object_type_participant`.

    Optional

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

The following checks are performed:

  - Check that all required attributes have been provided.
  - Check that all provided unique attributes do not exist in the store.
  - Check that FirmId, if specified, is a valid organization in the store.

Anyone is allowed to create participants, so no checks are done for
authorization (other than the uniqueness of the key-id as specified
above).

apply()
-------

Create a new object in the store of object-type of 'participant'.

The 'key-id' field must be initialized to the identifier associated with
the key used to sign the transaction message.  The 'creator-id' should
be set to the same as 'object-id' (this is a special case for participant,
which is always self-created).

For the FirmId, if specified, update the ref-count of the corresponding
organization.
