***************************
Transaction Family Overview
***************************

Sawtooth separates the application level from the core system level with
transaction families, which allows application developers to write in the
languages of their choice. Each application defines the custom transaction
families for its unique requirements.

A transaction family includes these components:

* A transaction processor to define the business logic for your application
* A data model to record and store data
* A client to handle the client logic for your application

The transaction processor is responsible for registering with the validator,
providing a transaction handler with an apply method and a transaction handler
class for metadata, and getting/setting state as needed.

The client is responsible for creating and signing transactions, combining
those transactions into batches, and submitting them to the validator. The
client can post batches through the REST API or connect directly to the
validator via `ZeroMQ <http://zeromq.org>`_.

The client and transaction processor must use the same data model,
serialization/encoding method, and addressing scheme.

See :doc:`../transaction_family_specifications` for a list of example
transaction families. Sawtooth provides these examples to serve as models for
low-level functions (such as maintaining chain-wide settings and storing
on-chain permissions) and for specific applications such as performance analysis
and storing block information.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
