************************
Transactions and Batches
************************

Modifications to state are performed by creating and applying transactions.  A
client creates a transaction and submits it to the validator.  The validator
applies the transaction which causes a change to state.

Transactions are always wrapped inside of a batch.  All transactions within a
batch are committed to state together or not at all.  Thus, batches are the
atomic unit of state change.

The overall structure of batches and transactions includes Batch, BatchHeader,
Transaction, and TransactionHeader:

.. image:: ../images/arch_batch_and_transaction.*
   :width: 80%
   :align: center
   :alt: Transaction and batch entity diagram

Transaction Data Structure
==========================

Transactions are serialized using Protocol Buffers.  They consist of two
message types:

.. literalinclude:: ../../../protos/transaction.proto
   :language: protobuf
   :caption: File: protos/transaction.proto
   :linenos:

Header, Signature, and Public Keys
----------------------------------

The Transaction header field is a serialized version of a TransactionHeader.
The header is signed by the signer's private key (not sent with the
transaction) and the resulting signature is stored in header_signature.  The
header is present in the serialized form so that the exact bytes can be
verified against the signature upon receipt of the Transaction.

The verification process verifies that the key in signer_public_key signed the
header bytes resulting in header_signature.

The batcher_public_key field must match the public key used to sign the batch in
which this transaction is contained.

The resulting serialized document is signed with the transactor's private
ECDSA key using the secp256k1 curve.

The validator expects a 64 byte "compact" signature. This is a concatenation
of the R and S fields of the signature. Some libraries will include an
additional header byte, recovery ID field, or provide DER encoded signatures.
Sawtooth will reject the signature if it is anything other than 64 bytes.

.. note::

   The original header bytes as constructed from the sender are used
   for verification of the signature.  It is not considered good practice to
   de-serialize the header (for example, to a Python object) and then
   re-serialize the header with the intent to produce the same byte sequence as
   the original.  Serialization can be sensitive to programming language or
   library, and any deviation would produce a sequence that would not match the
   signature; thus, best practice is to always use the original header bytes for
   verification.

Transaction Family
------------------

In Hyperledger Sawtooth, the set of possible transactions are defined by an
extensible system called transaction families.  Defining and implementing a new
transaction family adds to the taxonomy of available transactions which can be
applied. For example, in the language-specific tutorials that show you how to
write your own transaction family (see the :doc:`/app_developers_guide`), we
define a transaction family called "xo" which defines a set of transactions for
playing tic-tac-toe.

In addition to the name of the transaction family (family_name), each
transaction specifies a family version string (family_version).  The version
string enables upgrading a transaction family while coordinating the nodes
in the network to upgrade.

Dependencies and Input/Output Addresses
---------------------------------------

Transactions can depend upon other transactions, which is to say a dependent
transaction cannot be applied prior to the transaction upon which it depends.

The dependencies field of a transaction allows explicitly specifying the
transactions which must be applied prior to the current transaction.  Explicit
dependencies are useful in situations where transactions have dependencies but
can not be placed in the same batch (for example, if the transactions are
submitted at different times).

To assist in parallel scheduling operations, the inputs and outputs fields of a
transaction contain state addresses.  The scheduler determines the implicit
dependencies between transactions based on interaction with state.  The
addresses may be fully qualified leaf-node addresses or partial prefix
addresses.  Input addresses are read from the state and output addresses are
written to state.  While they are specified by the client, input and output
declarations on the transaction are enforced during transaction execution.
Partial addresses work as wildcards and allow transactions to specify parts of
the tree instead of just leaf nodes.

Payload
-------

The payload is used during transaction execution as a way to convey the change
which should be applied to state.  Only the transaction family processing the
transaction will deserialize the payload; to all other components of the
system, payload is just a sequence of bytes.

The payload_sha512 field contains a SHA-512 hash of the payload bytes.  As part
of the header, payload_sha512 is signed and later verified, while the payload
field is not.  To verify the payload field matches the header, a SHA-512 of the
payload field can be compared to payload_sha512.

Nonce
-----

The nonce field contains a random string generated by the client.  With the
nonce present, if two transactions otherwise contain the same fields, the nonce
ensures they will generate different header signatures.

Batch Data Structure
====================

Batches are also serialized using Protocol Buffers.  They consist of two
message types:

.. literalinclude:: ../../../protos/batch.proto
   :language: protobuf
   :caption: File: protos/batch.proto
   :linenos:

Header, Signature, and Public Keys
----------------------------------

Following the pattern presented in Transaction, the Batch header field is a
serialized version of a BatchHeader.  The header is signed by the signer's
private key (not sent with the batch) and the resulting signature is stored in
header_signature.  The header is present in the serialized form so that the
exact bytes can be verified against the signature upon receipt of the Batch.

The resulting serialized document is signed with the transactor's private
ECDSA key using the secp256k1 curve.

The validator expects a 64 byte "compact" signature. This is a concatenation
of the R and S fields of the signature. Some libraries will include an
additional header byte, recovery ID field, or provide DER encoded signatures.
Sawtooth will reject the signature if it is anything other than 64 bytes.

Transactions
------------

The transactions field contains a list of Transactions which make up the batch.
Transactions are applied in the order listed.  The transaction_ids field
contains a list of Transaction header_signatures and must be the same order as
the transactions field.

Why Batches?
============

As we have stated above, a batch is the atomic unit of change in the system.
If a batch has been applied, all transactions will have been applied in the
order contained within the batch.  If a batch has not been applied (maybe
because one of the transactions is invalid), then none of the transactions will
be applied.

This greatly simplifies dependency management from a client perspective, since
transactions within a batch do not need explicit dependencies to be declared
between them.  As a result, the usefulness of explicit dependencies (contained
in the dependencies field on a Transaction) are constrained to dependencies
where the transactions cannot be placed in the same batch.

Batches solve an important problem which cannot be solved with explicit
dependencies.  Suppose we have transactions A, B, and C and that the desired
behavior is A, B, C be applied in that order, and if any of them are invalid,
none of them should be applied.  If we attempted to solve this using only
dependencies, we might attempt a relationship between them such as: C depends
on B, B depends on A, and A depends on C.  However, the dependencies field
cannot be used to represent this relationship, since dependencies enforce order
and the above is cyclic (and thus cannot be ordered).

Transactions from multiple transaction families can also be batched together,
which further encourages reuse of transaction families.  For example,
transactions for a configuration or identity transaction family could be
batched with application-specific transactions.

Transactions and batches can also be signed by different keys.  For example, a
browser application can sign the transaction and a server-side component can
add transactions and create the batch and sign the batch.  This enables
interesting application patterns, including aggregation of transactions from
multiple transactors into an atomic operation (the batch).

There is an important restriction enforced between transactions and batches,
which is that the transaction must contain the public key of the batch signer
in the batcher_public_key field.  This is to prevent transactions from being reused
separate from the intended batch.  So, for example, unless you have the
batcher's private key, it is not possible to take transactions from a batch and
repackage them into a new batch, omitting some of the transactions.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
