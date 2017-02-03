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

.. _object_type_participant:

object-type: participant
========================

Attributes
----------

  object-id
    See :ref:`common_attributes`.

  object-type
    The string 'participant'.

  creator-id
    See :ref:`common_attributes`.

  key-id
    The public identifier derived from the key used by this participant to sign
    messages.  In other systems such as bitcoin, where this might be used as a
    destination, the key-id is also called the 'address' or 'wallet address'.

    Indexed, Unique

  username
    The username of the participant.

    Indexed, Unique

  firm-id
    The object-id of the participant's organization.

    Optional

Example JSON
------------

.. code-block:: json

   {
       "object-id": "<OBJECT_ID>",
       "object-type" : "participant",
       "creator-id": "<OBJECT_ID>",
       "key-id": "<KEY_ID>",
       "username" : "tjsmith",
       "firm-id" : "<OBJECT_ID>"
   }

Related Transaction Updates
---------------------------

- :ref:`update_create_participant`
- :ref:`update_update_participant`
