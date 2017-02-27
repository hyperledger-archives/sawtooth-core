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

.. _update_create_organization:

CreateOrganization
==================

Attributes
----------

  ObjectId
    See 'object-id' in :ref:`object_type_organization`.

    Optional

  Name
    See 'name' in :ref:`object_type_organization`.

  Industry
    See 'industry' in :ref:`object_type_organization`.

    Optional

  Ticker
    See 'ticker' in :ref:`object_type_organization`.

    Optional

  PricingSource
    See 'pricing-source' in :ref:`object_type_organization`.

    Optional

  Authorization
    See 'authorization' in :ref:`object_type_organization`.

    The keys for the hashes contained in the list are 'ParticipantId' and
    'Role', which are mapped to 'participant-id' and 'role' when creating
    the object.

    Optional
  
JSON Examples
-------------

Example 1:

.. code-block:: json

   {
       "UpdateType": "CreateOrganization",
       "Name": "United States Treasury",
       "Industry": "Government",
       "Ticker": "T"
   }

Example 2:

.. code-block:: json

   {
       "UpdateType": "CreateOrganization",
       "ObjectId": "OBJECT_ID",
       "Name": "Bank of Terra Incognita",
       "PricingSource": "AVCD",
       "Authorization": [ {
           "ParticipantId": "OBJECT_ID",
           "Role": "marketmaker"
       } ]
   }

check_valid()
-------------

The following checks are performed:

  - Check that all required attributes have been provided.
  - Check that all provided unique attributes do not exist in the store.
  - Check that Authorization list contains a list of dict()
    objects containing only the keys ParticipantId and Role.  Both
    keys must exist.
  - Check that all ParticipantIds given in the Authorization list
    exist in the store.
  - Check that PricingSource, if provided, is a four-character string.
  - Check that all Roles given in the Authorization list are one of the
    valid strings allowed.

Anyone is allowed to create organizations, so no checks are done for
authorization.

apply()
-------

Create a new object in the store with object-type of ‘organization’.

For each Authorization item, increment the ref-count of the corresponding
participant.
