******************************************************
Building and Submitting Transactions ({{ language }})
******************************************************

The process of encoding information to be submitted to a distributed ledger is
generally non-trivial. A series of cryptographic safeguards are used to
confirm identity and data validity, and *Hyperledger Sawtooth* is no different.
SHA-512 hashes and secp256k1 signatures must be generated. Transaction and
Batch Protobufs must be created and serialized. The process can be somewhat
daunting, but this document will take Sawtooth client developers step by step
through the process using copious {{ language }} examples.

{% macro link_sdk(short_lang) %}

.. note::

   This document goes through building and submitting Transactions manually in
   order to explain the complete process. If your goal is just to write a
   functioning client, the {{ language }} SDK considerably simplifies the task.
   Check out :doc:`sdk_submit_tutorial_{{short_lang}}`.

{% endmacro %}

{# Only include note if there is an SDK for the language #}
{% if language == 'JavaScript' %}
    {{ link_sdk('js') }}
{% endif %}


Creating Private and Public Keys
================================

In order to sign your Transactions, you will need a 256-bit private key.
Sawtooth uses the secp256k1 ECSDA standard for signing, which means that almost
any set of 32 bytes is a valid key.

{% if language == 'JavaScript' %}

A common way to generate one is to create a random set of bytes, and then use a
secp256k1 library to ensure they are valid.

.. code-block:: javascript

    const crypto = require('crypto')
    const secp256k1 = require('secp256k1')

    let privateKeyBytes

    do {
        privateKeyBytes = crypto.randomBytes(32)
    } while (!secp256k1.privateKeyVerify(privateKeyBytes))

{% else %}
{# Python 3 code should be the default #}

The Python *secp256k1* module provides a *PrivateKey* handler class from which
we can generate the actual bytes to use for a key.

.. code-block:: python

    import secp256k1

    key_handler = secp256k1.PrivateKey()
    private_key_bytes = key_handler.private_key

{% endif %}

.. note::

   This key is the **only** way to prove your identity on the blockchain. Any
   person possessing it will be able to sign Transactions using your identity,
   and there is no way to recover it if lost. It is very important that any
   private key is kept secret and secure.

In addition to a private key, you will need a shareable public key generated
from the private key. It should be encoded as a hexadecimal string, to
distribute with the Transaction and confirm that its signature is valid.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const publicKeyBytes = secp256k1.publicKeyCreate(privateKeyBytes)

    const publicKeyHex = publicKeyBytes.toString('hex')

{% else %}

.. code-block:: python

    public_key_bytes = key_handler.pubkey.serialize()

    public_key_hex = public_key_bytes.hex()

{% endif %}


{% include 'partials/encoding_your_payload.rst' %}


Building the Transaction
========================

*Transactions* are the basis for individual changes of state to the Sawtooth
blockchain. They are composed of a binary payload, a binary-encoded
*TransactionHeader* with some cryptographic safeguards and metadata about how it
should be handled, and a signature of that header. It would be worthwhile to
familiarize yourself with the information in
:doc:`/architecture/transactions_and_batches`, particularly the definition of
TransactionHeaders.


1. Create a SHA-512 Payload Hash
--------------------------------

However the payload was originally encoded, in order to confirm it has not been
tampered with, a hash of it must be included within the Transaction's header.
This hash should be created using the SHA-512 function, and then formatted as a
hexadecimal string.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    let hasher = crypto.createHash('sha512')

    const payloadSha512 = hasher.update(payloadBytes).digest('hex')

{% else %}

.. code-block:: python

    from hashlib import sha512

    payload_sha512 = sha512(payload_bytes).hexdigest()

{% endif %}


2. Build the TransactionHeader
------------------------------

Transactions and their headers are built using
`Google Protocol Buffer <https://developers.google.com/protocol-buffers/>`_
(or Protobuf) format. This allows data to be serialized and deserialzed
consistently and efficiently across multiple platforms and multiple languages.
The Protobuf definition files are located in the
`/protos <https://github.com/hyperledger/sawtooth-core/tree/master/protos>`_
directory at the root level of the sawtooth-core repo. These files will have to
first be compiled into usable {{ language }} classes. Then, serializing a
*TransactionHeader* is just a matter of plugging the right data into the right
keys.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const protobuf = require('protobufjs')

    const txnRoot = protobuf.loadSync('sawtooth-core/protos/transaction.proto')
    const TransactionHeader = txnRoot.lookup('TransactionHeader')

    const txnHeaderBytes = TransactionHeader.encode({
        batcherPubkey: publicKeyHex,
        dependencies: [],
        familyName: 'intkey',
        familyVersion: '1.0',
        inputs: ['1cf12650d858e0985ecc7f60418aaf0cc5ab587f42c2570a884095a9e8ccacd0f6545c'],
        nonce: Math.random().toString(36),
        outputs: ['1cf12650d858e0985ecc7f60418aaf0cc5ab587f42c2570a884095a9e8ccacd0f6545c'],
        payloadEncoding: 'application/cbor',
        payloadSha512: payloadSha512,
        signerPubkey: publicKeyHex
    }).finish()

{% else %}

.. note::

   Follow
   `these instructions <https://developers.google.com/protocol-buffers/docs/pythontutorial#compiling-your-protocol-buffers>`_
   to install Google's *protobuf compiler* for Python, and manually compile
   Protobuf classes from the core definition files.

   The example code here assumes you will instead use classes from the
   *Sawtooth Python SDK*, which can be compiled by running the executable script
   ``bin/protogen``.

.. code-block:: python

    from random import randint
    from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader

    txn_header = TransactionHeader(
        batcher_pubkey=public_key_hex,
        dependencies=['540a6803971d1880ec73a96cb97815a95d374cbad5d865925e5aa0432fcf1931539afe10310c122c5eaae15df61236079abbf4f258889359c4d175516934484a'],
        family_name='intkey',
        family_version='1.0',
        inputs=['1cf12650d858e0985ecc7f60418aaf0cc5ab587f42c2570a884095a9e8ccacd0f6545c'],
        nonce=str(randint(0, 1000000000)),
        outputs=['1cf12650d858e0985ecc7f60418aaf0cc5ab587f42c2570a884095a9e8ccacd0f6545c'],
        payload_encoding='application/cbor',
        payload_sha512=payload_sha512,
        signer_pubkey=public_key_hex)

    txn_header_bytes = txn_header.SerializeToString()

{% endif %}

.. note::

   Remember that *inputs* and *outputs* are state addresses that this
   Transaction is allowed to read from or write to, and *dependencies* are the
   *header signatures* of Transactions that must be committed before ours (see
   TransactionHeaders in :doc:`/architecture/transactions_and_batches`). The
   dependencies property will frequently be left empty, but generally at least
   one input and output must always be set.


3. Sign the Header
------------------

Once the TransactionHeader is created and serialized as a Protobuf binary, you
can use your private key to create a secp256k1 signature. If not handled
automatically by your signing library, you may need to generate a SHA-256 hash
of the header bytes as well, as that is technically what gets signed. The
signature itself should be formatted as a hexedecimal string for transmission.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    hasher = crypto.createHash('sha256')
    const txnHeaderHash = hasher.update(txnHeaderBytes).digest()

    const txnSigBytes = secp256k1.sign(txnHeaderHash, privateKeyBytes).signature
    const txnSignatureHex = txnSigBytes.toString('hex')

{% else %}

.. code-block:: python

    key_handler = secp256k1.PrivateKey(private_key_bytes)

    # No need to manually generate a SHA-256 hash in Python
    txn_signature = key_handler.ecdsa_sign(txn_header_bytes)
    txn_signature_bytes = key_handler.ecdsa_serialize_compact(txn_signature)
    txn_signature_hex = txn_signature_bytes.hex()

{% endif %}


4. Create the Transaction
-------------------------

With the other pieces in place, constructing the Transaction instance should be
fairly straightforward. Create a *Transaction* class and use it to instantiate
the Transaction.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const Transaction = txnRoot.lookup('Transaction')

    const txn = Transaction.create({
        header: txnHeaderBytes,
        headerSignature: txnSignatureHex,
        payload: payloadBytes
    })

{% else %}

.. code-block:: python

    from sawtooth_sdk.protobuf.transaction_pb2 import Transaction

    txn = Transaction(
        header=txn_header_bytes,
        header_signature=txn_signature_hex,
        payload=payload_bytes)

{% endif %}


5. (optional) Encode the Transaction(s)
---------------------------------------

If the same machine is creating Transactions and Batches there is no need to
encode the Transaction instances. However, in the use case where Transactions
are being batched externally, they must be serialized before being transmitted
to the batcher. Technically any encoding scheme could be used so long as the
batcher knows how to decode it, but Sawtooth does provide a *TransactionList*
Protobuf for this purpose. Simply wrap a set of Transactions in the
*transactions* property of a TransactionList and serialize it.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const TransactionList = txnRoot.lookup('TransactionList')

    const txnBytes = TransactionList.encode({
        transactions: [txn]
    }).finish()

{% else %}

.. code-block:: python

    from sawtooth_sdk.protobuf.transaction_pb2 import TransactionList

    txnList = TransactionList(transactions=[txn])
    txnBytes = txnList.SerializeToString()

{% endif %}


Building the Batch
==================

Once you have one or more Transaction instances ready, they must be wrapped in a
*Batch*. Batches are the atomic unit of change in Sawtooth's state. When a Batch
is submitted to a validator, each Transaction in it will be applied (in order)
or *no* Transactions will be applied. Even if your Transactions are not
dependent on any others, they cannot be submitted directly to the validator.
They must all be wrapped in a Batch.


1. (optional) Decode the Transaction(s)
---------------------------------------

If the batcher is on a separate machine than the Transaction creator, any
Transactions will have been encoded as a binary and transmitted. If so, they
must be decoded before being wrapped in a batch.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const txnList = TransactionList.decode(txnBytes)

    const txn = txnList.transactions[0]

{% else %}

.. code-block:: python

    txnList = TransactionList()
    txnList.ParseFromString(txnBytes)

    txn = txnList.transactions[0]

{% endif %}


2. Create the BatchHeader
-------------------------

The process for creating a *BatchHeader* is very similar to a TransactionHeader.
Compile the *batch.proto* file, and then instantiate the appropriate
{{ language }} class with the appropriate values. This time, there are just two
properties: a *signer pubkey*, and a set of *Transaction ids*. Just like with a
TransactionHeader, the signer pubkey must have been generated from the private
key used to sign the Batch. The Transaction ids are a list of the
*header signatures* from the Transactions to be batched. They must be in the
same order as the Transactions themselves.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const batchRoot = protobuf.loadSync('sawtooth-core/protos/batch.proto')
    const BatchHeader = batchRoot.lookup('BatchHeader')

    const batchHeaderBytes = BatchHeader.encode({
        signerPubkey: publicKeyHex,
        transactionIds: [txn.headerSignature]
    }).finish()

{% else %}

.. code-block:: python

    from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader

    batch_header = BatchHeader(
        signer_pubkey=public_key_hex,
        transaction_ids=[txn.header_signature])

    batch_header_bytes = batch_header.SerializeToString()

{% endif %}


3. Sign the Header
------------------

The process for signing a BatchHeader is identical to signing the
TransactionHeader. Create a SHA-256 hash of the the header binary if necessary,
and then use your private key to create a secp256k1 signature.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    hasher = crypto.createHash('sha256')
    const batchHeaderHash = hasher.update(batchHeaderBytes).digest()

    const batchSigBytes = secp256k1.sign(batchHeaderHash, privateKeyBytes).signature
    const batchSignatureHex = batchSigBytes.toString('hex')

{% else %}

.. code-block:: python

    batch_signature = key_handler.ecdsa_sign(batch_header_bytes)

    batch_signature_bytes = key_handler.ecdsa_serialize_compact(batch_signature)

    batch_signature_hex = batch_signature_bytes.hex()

{% endif %}

.. note::

   The *batcher pubkey* specified in every TransactionHeader must have been
   generated from the private key being used to sign the Batch, or validation
   will fail.


4. Create the Batch
-------------------

Creating a *Batch* also looks a lot like creating a Transaction. Just use the
compiled class to instantiate a new Batch with the proper data.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const Batch = batchRoot.lookup('Batch')

    const batch = Batch.create({
        header: batchHeaderBytes,
        headerSignature: batchSignatureHex,
        transactions: [txn]
    })

{% else %}

.. code-block:: python

    from sawtooth_sdk.protobuf.batch_pb2 import Batch

    batch = Batch(
        header=batch_header_bytes,
        header_signature=batch_signature_hex,
        transactions=[txn])

{% endif %}


5. Encode the Batch(es)
-----------------------

In order to submit one or more Batches to a validator, they must be serialized
in a *BatchList* Protobuf. BatchLists have a single property, *batches*, which
should be set to one or more Batches.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const BatchList = batchRoot.lookup('BatchList')

    const batchBytes = BatchList.encode({
        batches: [batch]
    }).finish()

{% else %}

.. code-block:: python

    from sawtooth_sdk.protobuf.batch_pb2 import BatchList

    batch_list = BatchList(batches=[batch])
    batch_bytes = batch_list.SerializeToString()

{% endif %}


{% include 'partials/submitting_to_validator.rst' %}
