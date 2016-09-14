Architecture Overview
*********************

What is the Sawtooth Lake Distributed Ledger?
=============================================

The Sawtooth Lake Distributed Ledger is a software framework for
constructing decentralized ledgers with extensible transaction
types. It is comparable to the blockchain ledger that underlies
Bitcoin. Sawtooth Lake uses a unique mechanism for reaching consensus
on the validity of the ledger based on trusted code running inside a
hardware-protected Intel Software Guard Extensions (SGX) enclave.

One of the initial transaction families supported by Sawtooth Lake is
the MarketPlace. The MarketPlace Transaction Family establishes the
concepts of participants, accounts, assets, holdings, liabilities,
and offers in a decentralized ledger to facilitate the exchange of
digital assets. The Sawtooth Lake architecture allows the definition
of additional transaction families or the consumption of an existing
asset-type agnostic transaction family (like MarketPlace) to meet
domain-specific needs.

Repository Structure
====================

**sawtooth-core** - This repository contains the core functionaliy
of the distributed ledger, including:

* the gossip networking layer
* basic transaction, block, and message objects
* the base journal implementation
* the PoET and quorum voting journal consensus mechanisms
* 'built-in' transaction families - Endpoint Registry and Integer Key
  Registry

**sawtooth-mktplace** - This repository contains the MarketPlace
Transaction Family. This demonstrates how to inherit and extend base
sawtooth-core object types to implement a custom transaction family.
sawtooth-mktplace also includes a command line interface called
*mktclient* for interacting with validators running the MarketPlace
Transaction Family.

**sawtooth-validator** - This repository contains the implementation
of a server, known as the validator. The validator acts as a node on
the gossip network, as defined by sawtooth-core. Validators exchange
and act upon messages, as defined by the core classes and via
additional plug-in transaction families like the MarketPlace
Transaction Family.

Core Architecture
=================

The Sawtooth Lake Distributed Ledger consists of three major
architectural layers: the Ledger layer, the Journal layer, and the
Communication Layer.


.. image:: ../images/arch_overview_layers.*
   :scale: 50 %
   :align: center

Ledgers
-------

Ledgers are a conceptual semantic and data model layer for
transaction types. Ledgers are described as a 'conceptual' layer
because they are implemented as a specialization of existing base
classes already present in the Communication and Journal layers.

.. image:: ../images/arch_overview_ledger.*
   :scale: 50 %
   :align: center

In addition to some in-built system ledgers (Endpoint Registry, and
Integer Key Registry), implementing new classes in the ledger layer
allows for the creation of new transaction families. The MarketPlace
Transaction Family, located in the sawtooth-mktplace repository, is a
good example of how the ledger layer can be extended.

Journals
--------

A journal handles consensus on blocks of identifiers. Identifiers
reference transactions, which are globally replicated. In order to
confirm blocks, nodes need a copy of the transaction. In this fashion,
the journal provides global consensus on block ordering, transaction
ordering within blocks, and the content of transactions.

.. image:: ../images/arch_overview_journal.*

The journal module in sawtooth-core contains:

* the implementation of the base transaction and transaction block classes
* the consensus algorithms
* the global store manager
* the block store and key value store

The consensus journal object is journal.journal_core.Journal in the
sawtooth-core repository.

Consensus Mechanisms
~~~~~~~~~~~~~~~~~~~~

Sawtooth Lake contains two consensus implementations: PoET and Quorum
Voting.

PoET and SGX
::::::::::::

The Sawtooth Lake Distributed Ledger provides a unique mechanism to
ensure fairness in the node lottery. Instead of a Proof-of-Work
competition amongst nodes, Sawtooth Lake implements a
Proof-of-Elapsed-Time (PoET) algorithm for distributed consensus.
PoET relies upon a trusted execution environment, Intel's Software
Guard Extensions (SGX), to generate fair, verifiable random wait
timers and signed certificates of timer expiration. This mechanism
substantially reduces the computation and energy cost of ensuring
fair distributed consensus.

The implementation of PoET in Sawtooth Lake runs in a simulated enclave,
not a true trusted execution environment. For this reason, attestation
that wait timers have been fairly generated is not possible. This
version of PoET is intended for experimental purposes and should not
be used as the consensus mechanism in any 'production' environment.

The PoET implementation is located in journal.consensus.poet0 in
sawtooth-core.

Quorum Voting
:::::::::::::

The Quorum Voting consensus implementation is an adaptation of the
Ripple [#]_ and Stellar [#]_ consensus protocols.

.. [#] The Ripple Consensus Protocol -
   https://ripple.com/files/ripple_consensus_whitepaper.pdf
.. [#] The Stellar Consensus Protocol -
   https://www.stellar.org/papers/stellar-consensus-protocol.pdf

The Quorum Voting implementation is located in
journal.consensus.quorum in sawtooth-core.

Transactions
~~~~~~~~~~~~

A transaction is a set of updates to be applied atomically to a
ledger. The transaction defines the data model and representation.
For example, in the IntegerKey Transaction Family (located in
ledger.transaction.integer_key in sawtooth-core), the
IntegerKeyTransaction is defined as a list of zero or more updates
to key value pairs using the defined verbs 'set', 'inc', and 'dec'.
The associated IntegerKeyTransactionMessage wraps the derived
transaction object in a standard message object. There is typically
a message type for every transaction type.

Blocks
~~~~~~

A block is a set of transactions to be applied to a ledger. Other
than some specialized transaction block implementations for the
consensus mechanisms, new transaction block types are not typically
created. The expectation is that multiple transaction types will
coexist on single transaction blocks of type
journal.transaction_block.TransactionBlock. There is typically a
message type for every transaction block type.

Communication
-------------

The gossip protocol enables communication between nodes. It includes
protocol level connection management and basic flow control on top
of UDP. A Token Bucket [#]_ implementation is used to limit the average
rate of message transmission.

.. [#] https://en.wikipedia.org/wiki/Token_bucket

.. image:: ../images/arch_overview_communication.*

Peers in the gossip network are called Nodes. Nodes exchange Messages.
Message handling upon arrival is dispatched via EventHandlers
associated with the journal.

Messages
~~~~~~~~

Messages represent information to send or receive from peers over the
gossip network. Messages are serialized and deserialized using a
standard wire format (either CBOR or JSON).

Message types include:

* transaction messages
* transaction block messages
* journal transfer messages
* debug messages (log data)
* connection messages
* shutdown messages
* topology messages

Messages are used broadly across the architecture for both system
communication (administrative messages, consensus messages), and for
transaction-type specific handling.

Transaction Family Plugin Architecture
======================================

As mentioned above, the creation of new classes in the conceptual
'ledger' layer allows for the addition of transaction families. Via
a message handling and dispatch model, new transaction families can
register themselves with the underlying journal consensus and global
store mechanisms to allow for arbitrary callbacks on message arrival
and persistence of the transactions.

If specialized transaction stores are required, those can also be
defined and added to the ledger during initialization (via
register_transaction_types).

In order to create a basic transaction family, implement the following:

.. code-block:: python

  def register_transaction_types(ledger)

Register message handlers for defined message types and add a
transaction store to the ledger for the transaction types.

.. code-block:: python

  class BasicTransactionMessage(transaction_message.TransactionMessage)

implement __init__

.. code-block:: python

  class BasicTransaction(transaction.Transaction)

implement __init__, __str__, is_valid, apply, and dump

Refer to ledger.transaction.integer_key in sawtooth-core for a
simple example, or to mktplace.transactions.market_place in
sawtooth-mktplace for a more substantial example.

Transaction Families are loaded into the validator in sawtooth-validator
via the "TransactionFamilies" config value (see
sawtooth-validator/etc/txnvalidator.js).
