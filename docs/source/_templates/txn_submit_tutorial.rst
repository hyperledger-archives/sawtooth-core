************************************
Building and Submitting Transactions
************************************

The process of encoding information to be submitted to a distributed ledger is
generally non-trivial. A series of cryptographic safeguards are used to
confirm identity and data validity, and *Hyperledger Sawtooth* is no different.
SHA-512 hashes and secp256k1 signatures must be generated. Transaction and
Batch Protobufs must be created and serialized. The process can be somewhat
daunting, but this document will take Sawtooth client developers step by step
through the process using copious Python 3 examples.


Creating Private and Public Keys
================================

In order to sign your Transactions, you will need a 256-bit private key.
Sawtooth uses the secp256k1 ECDSA standard for signing, which means that almost
any set of 32 bytes is a valid key. A common way to generate one, is just to
generate a random set of bytes, and then use a secp256k1 library to ensure they
are valid.

For Python, the *secp256k1* module provides a *PrivateKey* handler class from
which we can generate the actual bytes to use for a key.

.. code-block:: python

    import secp256k1

    key_handler = secp256k1.PrivateKey()
    private_key_bytes = key_handler.private_key

.. note::

   This key is the **only** way to prove your identity on the blockchain. Any
   person possessing it will be able to sign Transactions using your identity,
   and there is no way to recover it if lost. It is very important that any
   private key is kept secret and secure.

In addition to a private key, you will need a shareable public key. It will be
generated from your private key, and can be used to confirm the private key was
used to sign a Transaction without exposing the private key itself. Your
secp256k1 library should be able to generate a public key, and Sawtooth will
expect it to be formatted as a hexadecimal string for distribution with a
Transaction.

.. code-block:: python

    public_key_bytes = key_handler.public_key.serialize()

    public_key_hex = public_key_bytes.hex()


{% include 'partials/encoding_your_payload.rst' %}


Building the Transaction
========================

*Transactions* are the basis for individual changes of state to the Sawtooth
blockchain. They are composed of a binary payload, a binary-encoded
*TransactionHeader* with some cryptographic safeguards and metadata about how
it should be handled, and a signature of that header. It would be worthwhile to
familiarize yourself with the information in
:doc:`/architecture/transactions_and_batches`, particularly the definition of
TransactionHeaders.


1. Create a SHA-512 Payload Hash
--------------------------------

However the payload was originally encoded, in order to confirm it has not been
tampered with, a hash of it must be included within the Transaction's header.
This hash should be created using the SHA-512 function, and then formatted as a
hexadecimal string.

.. code-block:: python

    from hashlib import sha512

    payload_sha512 = sha512(payload_bytes).hexdigest()


2. Create the TransactionHeader
-------------------------------

Transactions and their headers are built using the
`Google Protocol Buffer <https://developers.google.com/protocol-buffers/>`_
(or Protobuf) format. This allows data to be serialized and deserialized
consistently and efficiently across multiple platforms and multiple languages.
The Protobuf definition files are located in the
`/protos <https://github.com/hyperledger/sawtooth-core/tree/master/protos>`_
directory at the root level of the sawtooth-core repo. These files must first
be compiled into usable classes for your language (typically with the `protoc`
command). Then, serializing a *TransactionHeader* is just a matter of plugging
the right data into the right keys.

.. note::

   Generally, to compile Python Protobufs you would follow
   `these instructions <https://developers.google.com/protocol-buffers/docs/pythontutorial#compiling-your-protocol-buffers>`_
   to install Google's *Protobuf compiler* and manually compile Python
   classes however you like.

   This example will use classes from the *Sawtooth Python SDK*, which can be
   compiled by running the executable script ``bin/protogen``.

.. code-block:: python

    from random import randint
    from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader

    txn_header = TransactionHeader(
        batcher_public_key=public_key_hex,
        # If we had any dependencies, this is what it might look like:
        # dependencies=['540a6803971d1880ec73a96cb97815a95d374cbad5d865925e5aa0432fcf1931539afe10310c122c5eaae15df61236079abbf4f258889359c4d175516934484a'],
        family_name='intkey',
        family_version='1.0',
        inputs=['1cf1266e282c41be5e4254d8820772c5518a2c5a8c0c7f7eda19594a7eb539453e1ed7'],
        nonce=str(randint(0, 1000000000)),
        outputs=['1cf1266e282c41be5e4254d8820772c5518a2c5a8c0c7f7eda19594a7eb539453e1ed7'],
        payload_sha512=payload_sha512,
        signer_public_key=public_key_hex)

    txn_header_bytes = txn_header.SerializeToString()

.. note::

   Remember that *inputs* and *outputs* are state addresses that this
   Transaction is allowed to read from or write to, and *dependencies* are the
   *header signatures* of Transactions that must be committed before this one
   (see TransactionHeaders in :doc:`/architecture/transactions_and_batches`).
   The dependencies property will frequently be left empty, but generally at
   least one input and output must always be set, and those addresses must
   adhere to validation rules specific to your Transaction Family (in this
   case, `IntegerKey <../transaction_family_specifications
   /integerkey_transaction_family.html#addressing>`_).


3. Sign the Header
------------------

Once the TransactionHeader is created and serialized as a Protobuf binary, you
can use your private key to create an *ECDSA signature*. In order to generate a
signature the Sawtooth validator will accept, you must:

    * use the *secp256k1* elliptic curve
    * sign a *SHA-256* hash of the TransactionHeader binary
    * use a compact 64-byte signature
    * format the signature as a hexadecimal string

This is a fairly typical way to sign data, so depending on the language and
library you are using, some of these steps may be handled automatically.

.. code-block:: python

    key_handler = secp256k1.PrivateKey(private_key_bytes)

    # ecdsa_sign automatically generates a SHA-256 hash of the header bytes
    txn_signature = key_handler.ecdsa_sign(txn_header_bytes)
    txn_signature_bytes = key_handler.ecdsa_serialize_compact(txn_signature)
    txn_signature_hex = txn_signature_bytes.hex()


4. Create the Transaction
-------------------------

With the other pieces in place, constructing the Transaction instance should be
fairly straightforward. Create a *Transaction* class and use it to instantiate
the Transaction.

.. code-block:: python

    from sawtooth_sdk.protobuf.transaction_pb2 import Transaction

    txn = Transaction(
        header=txn_header_bytes,
        header_signature=txn_signature_hex,
        payload=payload_bytes)


5. (optional) Encode the Transaction(s)
---------------------------------------

If the same machine is creating Transactions and Batches there is no need to
encode the Transaction instances. However, in the use case where Transactions
are being batched externally, they must be serialized before being transmitted
to the batcher. Technically any encoding scheme could be used so long as the
batcher knows how to decode it, but Sawtooth does provide a *TransactionList*
Protobuf for this purpose. Simply wrap a set of Transactions in the
*transactions* property of a TransactionList and serialize it.

.. code-block:: python

    from sawtooth_sdk.protobuf.transaction_pb2 import TransactionList

    txnList = TransactionList(transactions=[txn])
    txnBytes = txnList.SerializeToString()


Building the Batch
==================

Once you have one or more Transaction instances ready, they must be wrapped in
a *Batch*. Batches are the atomic unit of change in Sawtooth's state. When a
Batch is submitted to a validator, each Transaction in it will be applied (in
order) or *no* Transactions will be applied. Even if a Transaction is not
dependent on any others, it cannot be submitted directly to the validator. It
must be wrapped in a Batch.


1. (optional) Decode the Transaction(s)
---------------------------------------

If the batcher is on a separate machine than the Transaction creator, any
Transactions will have been encoded as a binary and transmitted. If so, they
must be decoded before being wrapped in a batch. Here we assume you used a
*TransactionList* to serialize the Transactions.

.. code-block:: python

    txnList = TransactionList()
    txnList.ParseFromString(txnBytes)

    txn = txnList.transactions[0]


2. Create the BatchHeader
-------------------------

The process for creating a *BatchHeader* is very similar to a
TransactionHeader. Compile the *batch.proto* file, and then instantiate the
appropriate class with the appropriate values. This time, there
are just two properties: a *signer public_key*, and a set of *Transaction ids*.
Just like with a TransactionHeader, the signer public_key must have been generated
from the private key used to sign the Batch. The Transaction ids are a list of
the *header signatures* from the Transactions to be batched. They must be in
the same order as the Transactions themselves.

.. code-block:: python

    from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader

    batch_header = BatchHeader(
        signer_public_key=public_key_hex,
        transaction_ids=[txn.header_signature])

    batch_header_bytes = batch_header.SerializeToString()


3. Sign the Header
------------------

The process for signing a BatchHeader is identical to signing the
TransactionHeader. Create a SHA-256 hash of the header binary, use your
private key to create a 64-byte secp256k1 signature, and format that signature
as a hexadecimal string. As with signing a TransactionHeader, some of these
steps may be handled automatically by the library you are using.

.. code-block:: python

    batch_signature = key_handler.ecdsa_sign(batch_header_bytes)

    batch_signature_bytes = key_handler.ecdsa_serialize_compact(batch_signature)

    batch_signature_hex = batch_signature_bytes.hex()

.. note::

   The *batcher public_key* specified in every TransactionHeader must have been
   generated from the private key being used to sign the Batch, or validation
   will fail.


4. Create the Batch
-------------------

Creating a *Batch* also looks a lot like creating a Transaction. Just use the
compiled class to instantiate a new Batch with the proper data.

.. code-block:: python

    from sawtooth_sdk.protobuf.batch_pb2 import Batch

    batch = Batch(
        header=batch_header_bytes,
        header_signature=batch_signature_hex,
        transactions=[txn])


5. Encode the Batch(es)
-----------------------

In order to submit one or more Batches to a validator, they must be serialized
in a *BatchList* Protobuf. BatchLists have a single property, *batches*, which
should be set to one or more Batches. Unlike Transactions, where
TransactionList was a convenience, a Sawtooth validator will *only* accept
Batches that have been wrapped in a BatchList.

.. code-block:: python

    from sawtooth_sdk.protobuf.batch_pb2 import BatchList

    batch_list = BatchList(batches=[batch])
    batch_bytes = batch_list.SerializeToString()


{% include 'partials/submitting_to_validator.rst' %}

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
