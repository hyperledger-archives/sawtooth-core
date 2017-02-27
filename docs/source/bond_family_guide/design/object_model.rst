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

************
Object Model
************

.. _object_store:

ObjectStore
===========

All objects are stored using the ObjectStore.  Each object in the ObjectStore
has an attribute object-type and an object-id.  Each type of object
(organization, participant, bond, etc.) has an object-type associated with it.
Each object has an object-id, which is a sha256 hex digest.

ObjectStore is backed by a key/value database.  The storage key used is the
object-id, with the value being the object data.

For each object-type, the ObjectStore maintains a list of indexes associated
with it.  So, for example, the 'bond' object-type has an 'isin' index which
can be used to lookup bonds by their 'isin' attribute.

.. note::

   The object-id is a 64 character string.  In the sections that follow,
   we represent that string with OBJECT_ID for documentation purposes (the
   long string would often fall off the right side of the page).  The
   object-id would never actually be set to the string literal
   'OBJECT_ID'.

.. _common_attributes:

Common Attributes
=================

The following attributes are commonly used:

  creator-id
    The identifier of the signing key on the transaction which created the
    object.  In some instances, this is used to control authorization on
    operations associated with the object.

  object-id
    The object's unique identifer, a 64-character string, as described in
    :ref:`object_store`.

    Indexed, Unique

  ref-count
    The number of other objects referencing this object.  This is used
    primarily to determine if the object can be safely deleted.


Object Types
============

.. toctree::
   :maxdepth: 1

   object_model/bond.rst
   object_model/holding.rst
   object_model/order.rst
   object_model/organization.rst
   object_model/participant.rst
   object_model/quote.rst
   object_model/receipt.rst
   object_model/settlement.rst
