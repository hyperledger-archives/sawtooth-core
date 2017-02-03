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

.. _update_update_organization:

UpdateOrganization
==================

Attributes
----------

  ObjectId
    See 'object-id' in :ref:`object_type_organization`.

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

JSON Examples
-------------

Example 1:

.. code-block:: json

   {
       "UpdateType": "UpdateOrganization",
       "ObjectId": "OBJECT_ID",
       "Name": "United States Treasury",
       "Industry": "Government",
       "Ticker": "T"
   }

Example 2:

.. code-block:: json

   {
       "UpdateType": "UpdateOrganization",
       "ObjectId": "OBJECT_ID",
       "Name": "Bank of Terra Incognita",
       "PricingSource": "AVCD"
   }

check_valid()
-------------

Only the participant set in the creator-id is allowed to update an
organization using UpdateOrganization.  Compare the participant's
key-id against the key used to sign the transaction.

The following checks are performed:

  - Authorization, as described above.
  - Check that all required attributes have been provided.
  - Check that all provided unique attributes do not exist in the store.
  - Check that PricingSource, if provided, is a four-character string.

apply()
-------

Update the new object to match the new data, including removing fields
that are not specified.  Note that the authorization attribute should be left
as-is, since there that is handled with the UpdateOrganizationAuthorization
update type.
