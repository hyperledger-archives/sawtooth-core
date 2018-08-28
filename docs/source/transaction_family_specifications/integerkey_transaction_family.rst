*****************************
IntegerKey Transaction Family
*****************************

Overview
=========
The IntegerKey transaction family allows users to set, increment, and decrement
the value of entries stored in a state dictionary.

An IntegerKey family transaction request is defined by the following values:

* A verb which describes what action the transaction takes
* A name of the entry that is to be set or changed
* A value by which the entry will be set or changed

The 'set' verb is used to create new entries. The initial value of the entry will be
set to the value specified in the transaction request. The 'inc' and 'dec' verbs are
used to change the value of existing entries in the state dictionary.

State
=====
This section describes in detail how IntegerKey transaction information is stored
and addressed.

The address values of IntegerKey transaction family entries are stored in state as
a CBOR encoded dictionary, with the key being the *Name* and the value being an integer
*Value*.

.. code-block:: python

    cbor.dumps({
        # The name of the entry : The current value of the entry
        'Name':'Value'
    })

\ *Names* and *Values* must conform to the following rules:

* Valid *Names* are utf-8 encoded strings with a maximum of 20 characters
* Valid *Values* must be integers in the range of 0 through 2\ :sup:`32` - 1 (32-bit unsigned int)

Addressing
----------
IntegerKey data is stored in the state dictionary using addresses which are generated from the IntegerKey namespace prefix and the unique name of the IntegerKey entry. Addresses will adhere to the following format:

- Addresses must be a 70 character hexadecimal string
- The first 6 characters of the address are the first 6 characters of a sha512 hash of the IntegerKey namespace prefix: "intkey"
- The following 64 characters of the address are the last 64 characters of a sha512 hash of the entry *Name*

For example, an IntegerKey address could be generated as follows:

.. code-block:: pycon

    >>> hashlib.sha512('intkey'.encode('utf-8')).hexdigest()[0:6] + hashlib.sha512('name'.encode('utf-8')).hexdigest()[-64:]
    '1cf126cc488cca4cc3565a876f6040f8b73a7b92475be1d0b1bc453f6140fba7183b9a'

.. note:: Due to the possibility of hash collisions, there may be multiple *Names* in the state dictionary with the same address.

Transaction Payload
===================

IntegerKey transaction request payloads are defined by the following CBOR data format:

.. code-block:: python

    cbor.dumps({
        # Describes the action the transaction takes, either 'set', 'inc', or 'dec'
        'Verb': 'verb',

        # The variable name of the entry which is to be modified
        'Name': 'name',

        # The amount to set, increment, or decrement
        'Value': 1234,
    })

Transaction Header
==================

Inputs and Outputs
------------------

The inputs for IntegerKey family transactions must include:

* Address of the *Name* being changed or added


The outputs for IntegerKey family transactions must include:

* Address of the *Name* being changed or added

Dependencies
------------

* List of transaction *header_signatures* that are required dependencies
  and must be processed prior to processing this transaction

For example, the 'inc' and 'dec' transactions must list the initial 'set' transaction for the entry. If an 'inc' or 'dec' transaction is ordered before the corresponding 'set' transaction (without listing the 'set' transaction as a dependency), they will be considered invalid (because *Name* will not exist when they are processed).

Family
------
- family_name: "intkey"
- family_version: "1.0"

Execution
=========

The IntegerKey transaction processor receives a transaction request and a state dictionary.

If the payload of the transaction request is empty, the transaction is invalid.

The address for the transaction is generated using the algorithm stated in the Addressing
section of this document. If an encoding error occurs, the transaction is invalid.

The transaction request *Verb* \, *Name*\ , and *Value* are checked. If any of these values are
empty, the transaction is invalid. *Verb* must be either 'set', 'inc', or 'dec'.
*Name* must be a utf-8 encoded string with a maximum of 20 characters. *Value* must be
a 32-bit unsigned integer. If any of these checks fail, the transaction is invalid.

If the *Verb* is 'set', the state dictionary is checked to determine if the *Name* associated with the
transaction request already exists. If it does already exist, the transaction is invalid.
Otherwise the *Name* and *Value* are stored as a new entry in the state dictionary.

If the *Verb* is 'inc', the *Name* specified by the transaction request is checked determine
if the entry exists in the state dictionary. If the *Name* does not exist in the state dictionary,
it is an invalid transaction. Otherwise, we attempt to increment the *Value* in the state dictionary by the *Value* specified in the transaction request. If this incrementation would result in a value outside the range of 0 through 2\ :sup:`32` - 1 it is considered an invalid transaction. Otherwise, the *Value* in the state dictionary is incremented.

If the *Verb* is 'dec', the *Name* specified by the transaction request is checked determine
if the entry exists in the state dictionary. If the *Name* does not exist in the state dictionary, it is an invalid transaction. Otherwise, we attempt to decrement the *Value* in the state dictionary by the *Value* specified in the transaction request. If this decrementation would result in a value outside the range of 0 through 2\ :sup:`32` - 1, it is considered an invalid transaction. Otherwise, the *Value* in the state dictionary is decremented.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
