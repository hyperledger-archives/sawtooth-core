****************************
Address and Namespace Design
****************************

Hyperledger Sawtooth stores data in a Merkle-Radix tree. Data is stored in leaf
nodes, and each node is accessed using an addressing scheme that is composed of
35 bytes, represented as 70 hex characters. The recommended way to construct an
address is to use the hex-encoded hash values of the string or strings that
make up the address elements. However, the encoding of the address is
completely up to the transaction family defining the namespace, and does not
need to involve hashing. Hashing is a useful way to deterministically generate
likely non-colliding byte arrays of a fixed length.


Address Components
==================

An address begins with a namespace prefix of six hex characters representing
three bytes. The rest of the address, 32 bytes represented as 64 hex
characters, can be calculated in various ways. However, certain guidelines
should be followed when creating addresses, and specific requirements must be
met.


.. image:: ../images/address_namespace.*
   :width: 100%
   :align: center
   :alt: Address and Namespace Design

The address must be deterministic: that is, any validator or client that needs
to calculate the address must be able to calculate the same address, every
time, when given the same inputs.


Namespace Prefix
================

All data under a namespace prefix follows a consistent address and data
encoding/serialization scheme that is determined by the transaction family
which defines the namespace.


The namespace prefix consists of six hex characters, or three bytes.  An
example namespace prefix that utilizes the string making up the transaction
family namespace name to calculate the prefix is demonstrated by the following
Python code:


.. code-block:: python

	prefix = hashlib.sha256("example_txn_family_namespace".encode('utf-8')).hexdigest()[:6]


Alternatively, a namespace prefix can utilize an arbitrary scheme. The current
Settings transaction family uses a prefix of ‘000000’, for example.


Address Construction
====================

The rest of the address, or remaining 32 bytes (64 hex characters), must be
calculated using a defined deterministic encoding format. Each address within
a namespace should be unique, or the namespace consumers must be able to deal
with collisions in a deterministic way.

The addressing schema can be as simple or as complex as necessary, based on
the requirements of the transaction family.

Simple Example - IntegerKey
---------------------------

For a description of the IntegerKey Transaction family, 
see :doc:`/transaction_family_specifications/integerkey_transaction_family`.

The transaction family prefix is:

.. code-block:: python

	hashlib.sha512('intkey'.encode('utf-8')).hexdigest()[0:6]

This resolves to '1cf126'.

To store a value in the entry *Name*, the address would be
calculated like this:

.. code-block:: python

	address = "1cf126" + hashlib.sha512('name'.encode('utf-8')).hexdigest()[-64:]

A value could then be stored at this address, by constructing and sending a
transaction to a validator, where the transaction will be processed and
included in a block.

This address would also be used to retrieve the data.


More Complex Addressing Schemes
===============================

For a more complex example, let’s use a hypothetical transaction family which
stores information on different object types for a widget. The data on each
object type is keyed to  a unique object identifier.

* prefix = “my-transaction-family-namespace-example”
* object-type = “widget-type”
* unique-object-identifier = ”unique-widget-identifier”


Address construction
--------------------

Code Example:

.. code-block:: python

	>>> hashlib.sha256("my-transaction-family-namespace-example".encode('utf-8')).hexdigest()[:6] + hashlib.sha256("widget-type".encode('utf-8')).hexdigest()[:4] + hashlib.sha256("unique-widget-identifier".encode('utf-8')).hexdigest()[:60]
	'4ae1df0ad3ac05fdc7342c50d909d2331e296badb661416896f727131207db276a908e'

In this case, the address is composed partly of a hexdigest made of the
widget-type, and partly made up of the unique-widget-identifier. This encoding
scheme choice prevents collisions between data objects that have identical
identifiers, but which have different object types.

Since the addressing scheme is not mandated beyond the basic requirements,
there is a lot of flexibility. The example above is just an example. Your own
addressing schema should be designed with your transaction family’s
requirements in mind.

Settings Transaction Family Example
-----------------------------------

See the :doc:`/transaction_family_specifications/settings_transaction_family`
for another more complex addressing scheme.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
