************************************
Building and Submitting Transactions
************************************

The process of encoding information to be submitted to a distributed ledger is
generally non-trivial. A series of cryptographic safeguards are used to
confirm identity and data validity. *Hyperledger Sawtooth* is no different, but
the {{ language }} SDK does provide client functionality that abstracts away
most of these details, and greatly simplifies the process of making changes to
the blockchain.


Creating a Private Key
======================

In order to confirm your identity and sign the information you send to the
validator, you will need a 256-bit key. Sawtooth uses the secp256k1 ECSDA
standard for signing, which means that almost any set of 32 bytes is a valid
key, and it is fairly simple to generate this using the SDK's *signer* module.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const {signer} = require('sawtooth-sdk')

    const privateKey = signer.makePrivateKey()

{% else %}

{# Python 3 code should be the default #}

.. code-block::  python

    from sawtooth_signing.secp256k1_signer import generate_privkey

    private_key = privkey = generate_privkey(privkey_format='bytes')


{% endif %}

.. note::

   This key is the **only** way to prove your identity on the blockchain. Any
   person possessing it will be able to sign Transactions using your identity,
   and there is no way to recover it if lost. It is very important that any
   private key is kept secret and secure.


{% include 'partials/encoding_your_payload.rst' %}

.. note::

   This process can be simplified somewhat by offloading some of the work to
   the *payload encoder* of a *TransactionEncoder* (see below).


Building the Transaction
========================

*Transactions* are the basis for individual changes of state to the Sawtooth
blockchain. They are composed of a binary payload, a binary-encoded
*TransactionHeader* with some cryptographic safeguards and metadata about how
it should be handled, and a signature of that header. It would be worthwhile
to familiarize yourself with the information in
:doc:`/architecture/transactions_and_batches`, particularly the definition of
TransactionHeaders.


1. Create an Encoder
--------------------

A *TransactionEncoder* stores your private key, and (optionally) default
TransactionHeader values and a function to encode each payload. Once
instantiated, multiple Transactions can be created using these common elements,
and without any explicit hashing or signing. You will never need to specify the
*nonce*, *signer pubkey*, or *payload Sha512* properties of a TransactionHeader,
as the SDK will generate these automatically. You will only need to set a
*batcher pubkey* if a different private key will be used to sign Batches containing
these Transactions (see below).


{% if language == 'JavaScript' %}

.. code-block:: javascript

    const {TransactionEncoder} = require('sawtooth-sdk')

    const encoder = new TransactionEncoder(privateKey, {
        // We don't want a batcher pubkey or dependencies for our example,
        // but this is what setting them might look like:
        // batcherPubkey: '02d260a46457a064733153e09840c322bee1dff34445d7d49e19e60abd18fd0758',
        // dependencies: ['540a6803971d1880ec73a96cb97815a95d374cbad5d865925e5aa0432fcf1931539afe10310c122c5eaae15df61236079abbf4f258889359c4d175516934484a'],
        familyName: 'intkey',
        familyVersion: '1.0',
        inputs: ['1cf126'],
        outputs: ['1cf126'],
        payloadEncoding: 'application/cbor',
        payloadEncoder: cbor.encode
    })

{% else %}

.. code-block::  python

    from sawtooth_sdk.client.encoding import TransactionEncoder

    encoder = TransactionEncoder(
        private_key,
        # We don't want a batcher pubkey or dependencies for our example,
        # but this is what setting them might look like:
        # batcherPubkey='02d260a46457a064733153e09840c322bee1dff34445d7d49e19e60abd18fd0758',
        # dependencies=['540a6803971d1880ec73a96cb97815a95d374cbad5d865925e5aa0432fcf1931539afe10310c122c5eaae15df61236079abbf4f258889359c4d175516934484a'],
        payload_encoder=cbor.dumps,
        family_name='intkey',
        family_version='1.0',
        inputs=['1cf1266e282c41be5e4254d8820772c5518a2c5a8c0c7f7eda19594a7eb539453e1ed7'],
        outputs=['1cf1266e282c41be5e4254d8820772c5518a2c5a8c0c7f7eda19594a7eb539453e1ed7']
        payload_encoding='application/cbor')

{% endif %}

.. note::

   Remember that a *batcher pubkey* is the hex public key matching the private
   key that will later be used to sign a Transaction's Batch, and
   *dependencies* are the *header signatures* of Transactions that must be
   committed before this one (see *TransactionHeaders* in
   :doc:`/architecture/transactions_and_batches`).

   Although possible, it would be unusual to set these properties when
   creating a *TransactionEncoder*. The default batcher pubkey will be valid
   as long as the Transactions and Batches are signed by the same key, and
   dependencies are typically different from Transaction to Transaction.


2. Create the Transaction
-------------------------

If all of the necessary header defaults were set in the TransactionEncoder, a
Transaction can be created simply by calling the *create* method and passing
it a payload. If a *payload encoder* function was set, it will be run with the
payload as its one argument. The payload encoder can do any work you like to
format the payload, but in the end it what it returns *must* be binary
encoded.

Optionally, you may pass in header properties in order to override any defaults on for an individual Transaction.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const txn = encoder.create(payload, {
        inputs: ['1cf1266e282c41be5e4254d8820772c5518a2c5a8c0c7f7eda19594a7eb539453e1ed7'],
        outputs: ['1cf1266e282c41be5e4254d8820772c5518a2c5a8c0c7f7eda19594a7eb539453e1ed7']
    })

    const txn2 = encoder.create({
        Verb: 'inc',
        Name: 'foo',
        Value: 1
    })

{% else %}

.. code-block::  python

    txn = encoder.create(
        payload,
        inputs=['1cf12663ae9d398142a7d84c49b73ba2f667c8d377ceb7832db69b1a416133562ea496'],
        outputs=['1cf12663ae9d398142a7d84c49b73ba2f667c8d377ceb7832db69b1a416133562ea496'])

    txn2 = encoder.create({
        'Verb': 'inc',
        'Name': 'foo',
        'Value': 1})

{% endif %}

.. note::

   Remember that *inputs* and *outputs* are the state addresses a Transaction
   is allowed to read from or write to. When initializing our
   *TransactionEncoder* we used only the six character IntKey prefix, allowing
   Transactions which don't specify inputs/outputs to access any IntKey
   address. With ``txn`` above, we referenced the specific address where the
   value of  ``'foo'`` is stored. Whenever possible, specific addresses should
   be used, as this will allow the validator to better schedule Transaction
   processing.

   Note that the methods for assigning and validating addresses are entirely up
   to the Transaction Processor. In the case of IntKey, there are `specific
   rules to generate valid addresses <../transaction_family_specifications
   /integerkey_transaction_family.html#addressing>`_, which must be followed or
   Transactions will be rejected. You will need to know and follow the
   addressing rules for whichever Transaction Family you are working with.


3. (optional) Encode the Transaction(s)
---------------------------------------

If the same machine is creating Transactions and Batches there is no need to
encode the Transaction instances. However, in the use case where Transactions
are being batched externally, they must be serialized before being transmitted
to the batcher. The {{ language }} SDK offers two options for this. One or more
Transactions can be combined into a serialized *TransactionList* using the
*encode* method, or if only serializing a single Transaction, creation and
encoding can done in a single step with *createEncoded*.

{% if language == 'JavaScript' %}

.. code-block:: javascript

    const txnBytes = encoder.encode([txn, txn2])

    const txnBytes2 = encoder.createEncoded({
        Verb: 'dec',
        Name: 'foo',
        Value: 3
    })

{% else %}

.. code-block:: python

    txn_bytes = encoder.encode([txn, txn2])

    txn_bytes2 = encoder.create_encoded({
        'Verb': 'dec',
        'Name': 'foo',
        'Value': 3})

{% endif %}


Building the Batch
==================

Once you have one or more Transaction instances ready, they must be wrapped in a
*Batch*. Batches are the atomic unit of change in Sawtooth's state. When a Batch
is submitted to a validator each Transaction in it will be applied (in order),
or *no* Transactions will be applied. Even if your Transactions are not
dependent on any others, they cannot be submitted directly to the validator.
They must all be wrapped in a Batch.


1. Create an Encoder
--------------------

Similar to the TransactionEncoder, there is a *BatchEncoder* for making Batches.
As Batches are much simpler than Transactions, the only argument to pass during
instantiation is the private key to sign the Batches with.


{% if language == 'JavaScript' %}

.. code-block:: javascript

    const {BatchEncoder} = require('sawtooth-sdk')

    const batcher = new BatchEncoder(privateKey)

{% else %}

.. code-block:: python

    from sawtooth_sdk.client.encoding import BatchEncoder

    batcher = BatchEncoder(private_key)

{% endif %}


2. Create the Batch
-------------------

Using the SDK, creating a Batch is as simple as calling the *create* method and
passing it one or more Transactions. If serialized, there is no need to
decode them first. In addition to Transaction instances, the BatchEncoder can
handle TransactionLists encoded as both raw binaries and url-safe base64
strings.


{% if language == 'JavaScript' %}

.. code-block:: javascript

    const batch = batcher.create(txn)

    const batch2 = batcher.create([txn, txn2])

    const batch3 = batcher.create(txnBytes)


{% else %}

.. code-block:: python

    batch = batcher.create(txn)

    batch2 = batcher.create([txn, txn2])

    batch3 = batcher.create(txn_bytes)

{% endif %}


3. Encode the Batch(es) in a BatchList
--------------------------------------

Like the TransactionEncoder, BatchEncoders have both *encode* and
*createEncoded* methods for serializing Batches in a BatchList. If encoding
multiple Batches in one BatchList, they must be created individually first, and
then encoded. If only wrapping one Batch per BatchList, creating and encoding
can happen in one step.


{% if language == 'JavaScript' %}

.. code-block:: javascript

    const batchBytes = batcher.encode([batch, batch2, batch3])

    const batchBytes2 = batcher.createEncoded(txn)

{% else %}

.. code-block:: python

    batch_bytes = batcher.encode([batch, batch2, batch3])

    batch_bytes2 = batcher.create_encoded(txn)

{% endif %}

.. note::

   Note, if the transaction creator is using a different private key than the
   batcher, the *batcher pubkey* must have been specified for every Transaction,
   and must have been generated from the private key being used to sign the
   Batch, or validation will fail.


{% include 'partials/submitting_to_validator.rst' %}
