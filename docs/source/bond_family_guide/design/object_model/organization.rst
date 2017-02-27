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

.. _object_type_organization:

object-type: organization
=========================

Attributes
----------

  object-id
    See :ref:`common_attributes`.

  object-type
    The string 'organization'.
 
  creator-id
    See :ref:`common_attributes`.

  ref-count
      See :ref:`common_attributes`.

  name
    The name of the organization.

    Unique, Indexed

  industry
    The industry of the organization.

    Optional

  ticker
    The stock market ticker symbol associated with the organization.

    Unique, Indexed, Optional 
 
  pricing-source
    A four-letter code representing the identity of the organization for the
    purpose of providing quotes to the market. This is not the same as the
    ticker symbol. This is only relevant for organizations which are acting as
    'market makers' on the trading system 
 
    Unique, Indexed, Optional 

  authorization
    A list of hashes, each has containing the keys 'participant-id' and
    'role'.  The value of participant-id is the object-id of an object
    of object-type 'participant'.  Roles grant permissions for a participant
    to act on behalf of the organization in some capacity.  Valid roles are:
    marketmaker, trader.

    Optional

Example JSON
------------

Example 1:

.. code-block:: json

   { 
       "object-id": "<OBJECT_ID>",
       "object-type": "organization",
       "creator-id": "<OBJECT_ID>",
       "ref-count": 0,
       "name": "Bank of Terra Incognita",
       "pricing-source": "AVCD"
   }

Example 2:

.. code-block:: json

   {
       "object-id": "<OBJECT_ID>",
       "object-type": "organization",
       "creator-id": "<OBJECT_ID>",
       "ref-count": 2,
       "name": "United States Treasury",
       "industry": "Government",
       "ticker": "T",
       "authorization": {
           "participant-id": "<OBJECT_ID>",
           "role": "marketmaker"
       }
   }

Related Transaction Updates
---------------------------

- :ref:`update_create_organization`
- :ref:`update_update_organization`
- :ref:`update_update_organization_authorization`
- :ref:`update_delete_organization`

