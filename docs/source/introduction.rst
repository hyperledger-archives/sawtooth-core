************
Introduction
************

Hyperledger Sawtooth is an enterprise blockchain platform for building
distributed ledger applications and networks. The design philosophy targets
keeping ledgers *distributed* and making smart contracts *safe*, particularly
for enterprise use.

Sawtooth simplifies blockchain application development by separating the core
system from the application domain. Application developers can specify the
business rules appropriate for their application, using the language of their
choice, without needing to know the underlying design of the core system.

Sawtooth is also highly modular. This modularity enables enterprises and
consortia to make policy decisions that they are best equipped to make.
Sawtooth's core design allows applications to choose the transaction rules,
permissioning, and consensus algorithms that support their unique business
needs.

Sawtooth is an open source project under the Hyperledger umbrella. For
information on how to contribute, see `Join the Sawtooth Community`_.


About Distributed Ledgers
=========================

A "distributed ledger" is another term for a blockchain. It distributes a
database (a ledger) of transactions to all participants in a network (also
called "peers" or "nodes"). There is no central administrator or centralised
data storage. In essence, it is:

    * **Distributed**: The blockchain database is shared among potentially
      untrusted participants and is demonstrably identical on all nodes
      in the network. All participants have the same information.

    * **Immutable**: The blockchain database is an unalterable history of all
      transactions that uses block hashes to make it easy to detect and
      prevent attempts to alter the history.

    * **Secure**: All changes are performed by transactions that are signed by
      known identities.

These features work together, along with agreed-upon consensus mechanisms, to
provide "adversarial trust" among all participants in a blockchain network.


Distinctive Features of Sawtooth
================================

Separation Between the Application Level and the Core System
------------------------------------------------------------

Sawtooth makes it easy to develop and deploy an application by providing a
clear separation between the application level and the core system level.
Sawtooth provides smart contract abstraction that allows application
developers to write contract logic in a language of their choice.

An application can be a native business logic or a smart contract virtual
machine. In fact, both types of applications can co-exist on the same
blockchain. Sawtooth allows these design decisions to be made in the
transaction-processing layer, which allows multiple types of applications to
exist in the same instance of the blockchain network.

Each application defines the custom
:term:`transaction processors<transaction processor>` for its unique
requirements. Sawtooth provides several example
:term:`transaction families<transaction family>` to serve as models for
low-level functions (such as maintaining chain-wide settings and storing
on-chain permissions) and for specific applications such as performance
analysis and storing block information.

Transaction processor SDKs are available in multiple languages to streamline
creation of new contract languages, including Python, JavaScript, Go, C++,
Java, and Rust. A provided REST API simplifies client development by
adapting :term:`validator<validator>` communication to standard HTTP/JSON.

Private Networks with the Sawtooth Permissioning Features
---------------------------------------------------------

Sawtooth is built to solve the challenges of permissioned (private) networks.
Clusters of Sawtooth nodes can be easily deployed with separate permissioning.
There is no centralized service that could potentially leak transaction
patterns or other confidential information.

The blockchain stores the settings that specify the permissions, such as roles
and identities, so that all participants in the network can access this
information.

Parallel Transaction Execution
------------------------------

Most blockchains require serial transaction execution in order to guarantee
consistent ordering at each node on the network. Sawtooth includes an advanced
parallel scheduler that splits transactions into parallel flows. Based on the
locations in state which are accessed by a transaction, Sawtooth isolates the
execution of transactions from one another while maintaining contextual
changes.

When possible, transactions are executed in parallel, while preventing
double-spending even with multiple modifications to the same state. Parallel
scheduling provides a substantial potential increase in performance over
serial execution.

Event System
------------

Hyperledger Sawtooth supports creating and broadcasting events. This allows
applications to:

    * Subscribe to events that occur related to the blockchain, such as a new
      block being committed or switching to a new fork.

    * Subscribe to application specific events defined by a transaction family.

    * Relay information about the execution of a transaction back to clients
      without storing that data in state.

Subscriptions are submitted and serviced over a ZMQ Socket.

Ethereum Contract Compatibility with Seth
-----------------------------------------

The Sawtooth-Ethereum integration project, Seth, extends the interoperability
of the Sawtooth platform to Ethereum. EVM (Ethereum Virtual Machine) smart
contracts can be deployed to Sawtooth using the Seth transaction family.

.. _dynamic-consensus-label:

Dynamic Consensus
-----------------

In a blockchain, consensus is the process of building agreement among a group
of participants in a network. Algorithms for achieving consensus with
arbitrary faults generally require some form of voting among a known set of
participants. General approaches include Nakamoto-style consensus, which
elects a leader through some form of lottery, and variants of the traditional
`Byzantine Fault Tolerance (BFT)
<https://en.wikipedia.org/wiki/Byzantine_fault_tolerance>`_
algorithms, which use multiple rounds of explicit votes to achieve consensus.

Sawtooth abstracts the core concepts of consensus and isolates consensus from
transaction semantics. The Sawtooth consensus interface supports plugging in
various consensus implementations as *consensus engines* that interact with the
validator through the *consensus API*.
More importantly, Sawtooth allows you to change the consensus after the
blockchain network has been created. The consensus algorithm is selected during
the initial network setup and can be changed on a running blockchain with a
transaction or two.

The Sawtooth consensus API supports a wide variety of consensus algorithms on a
network. Sawtooth currently includes consensus engines for these algorithms:

    * `Sawtooth PBFT <https://sawtooth.hyperledger.org/docs/pbft/nightly/master/>`__
      (Practical Byzantine Fault Tolerance) is a voting-based consensus
      algorithm that provides Byzantine fault tolerance with finality.
      Sawtooth PBFT extends the
      `original PBFT algorithm <https://www.usenix.org/legacy/events/osdi99/full_papers/castro/castro_html/castro.html>`__
      with features such as dynamic network membership, regular view changes,
      and a block catch-up procedure. A Sawtooth network with PBFT consensus
      requires four or more nodes.

    * :doc:`PoET <architecture/poet>`
      (Proof of Elapsed Time) is a Nakamoto-style consensus algorithm that is
      designed to be a production-grade protocol capable of supporting large
      network populations. PoET relies on secure instruction execution to
      achieve the scaling benefits of a Nakamoto-style consensus algorithm
      without the power consumption drawbacks of the Proof of Work algorithm.
      A Sawtooth network with PoET consensus requires at least three nodes.

      Sawtooth includes two versions of PoET consensus:

      * PoET-SGX relies on a Trusted Execution Environment (TEE), such as
        |Intel (R)| Software Guard Extensions (SGX), to implement a
        leader-election lottery system. PoET-SGX is sometimes called "PoET/BFT"
        because it is Byzantine fault tolerant.

      * PoET simulator provides PoET-style consensus on any type of hardware,
        including a virtualized cloud environment. PoET simulator is also called
        "PoET/CFT" because it is crash fault tolerant, not Byzantine fault
        tolerant.

    * `Sawtooth Raft <https://github.com/hyperledger/sawtooth-raft>`__
      is a leader-based consensus algorithm that provides crash fault tolerance
      for a small network with restricted membership.

    * Devmode (short for "developer mode")
      is a simplified random-leader algorithm that is useful for developing and
      testing a transaction processor. Devmode is not recommended for
      multi-node networks and should not be used for production.

For more information, see :doc:`/sysadmin_guide/about_dynamic_consensus`.

.. _sample-transaction-families-label:

Sample Transaction Families
---------------------------

In a Sawtooth application, the data model and transaction language are
implemented in a :term:`transaction family<transaction family>`, which runs
on a Sawtooth node as a :term:`transaction processor`.

While most application developers will build custom transaction families
that reflect the unique requirements of their ledgers, Sawtooth provides
several core transaction families as models\:

    * IntegerKey - Used for testing deployed ledgers.

    * Settings - Provides a reference implementation for storing
      :term:`on-chain configuration settings<on-chain setting>`.

    * Identity - Handles on-chain permissioning for transactor
      and validator keys to streamline managing identities
      for lists of public keys.

Additional transaction families provide models for specific areas\:

    * Smallbank - Handles performance analysis for benchmarking
      and performance testing when comparing the performance of
      blockchain systems.
      This transaction family is based on the H-Store Smallbank benchmark.

    * BlockInfo - Provides a methodology for storing information
      about a configurable number of historic blocks.

Other Hyperledger projects provide smart-contract functionality for the Sawtooth
platform\:

    * `Sawtooth Sabre <https://sawtooth.hyperledger.org/docs/sabre/nightly/master/>`__ -
      Implements on-chain smart contracts that are executed in a WebAssembly
      (WASM) virtual machine.

    * `Sawtooth Seth <https://sawtooth.hyperledger.org/docs/seth/nightly/master/>`__ -
      Supports running Ethereum Virtual Machine (EVM) smart contracts on Sawtooth

For more information, see :doc:`transaction_family_specifications`.


Real-world Application Examples
===============================

  * XO: Demonstrates how to construct basic transactions by playing
    `Tic-tac-toe <https://en.wikipedia.org/wiki/Tic-tac-toe>`_. The
    XO transaction family includes create and take transactions, with an ``xo``
    command that allows two participants to play the game.
    For more information, see
    :doc:`/app_developers_guide/intro_xo_transaction_family`.

  * Sawtooth Supply Chain:
    Demonstrates how to trace the provenance and other
    contextual information of any asset. Supply Chain provides an
    example application with a transaction processor, custom REST API, and web
    app. This example application also demonstrates a decentralized solution
    for in-browser transaction signing, and illustrates how to synchronize the
    blockchain state to a local database for complex queries. For more
    information, see the `sawtooth-supply-chain repository on GitHub
    <https://github.com/hyperledger/sawtooth-supply-chain>`_.

  * Sawtooth Marketplace:
    Demonstrates how to exchange specific quantities of customized assets with
    other users on the blockchain. This example application contains a number
    of components that, together with a Sawtooth validator, will run a Sawtooth
    blockchain and provide a simple RESTful API to interact with it.  For more
    information, see the `sawtooth-marketplace repository on GitHub
    <https://github.com/hyperledger/sawtooth-marketplace>`_.

Getting Started with Application Development
============================================

Try Hyperledger Sawtooth
------------------------

The Sawtooth documentation explains how to set up a local
:term:`validator` for demonstrating Sawtooth functionality and
testing an application. Once running, you will be able to submit new
transactions and fetch the resulting state and block data from the blockchain
using HTTP and the Sawtooth :term:`REST API`. These methods apply to the
included example :term:`transaction families<transaction family>`, as
well as to any transaction families you might write yourself.

Sawtooth can be run from a pre-built Docker container, from a Kubernetes cluster
inside a virtual machine on your computer, or on a native Ubuntu installation.

To get started, see :doc:`/app_developers_guide/installing_sawtooth`.

Develop a Custom Application
----------------------------

In Sawtooth, the data model and transaction language are implemented in a
transaction family. Transaction families codify business rules used to modify
state, while client programs typically submit transactions and view state. You
can build custom transaction families that reflect your unique requirements,
using the provided core transaction families as models.

Sawtooth provides a REST API and SDKs in several languages - including Python,
C++, Go, Java, JavaScript, and Rust - for development of applications which run
on top of the Sawtooth platform. In addition, you can write smart contracts in
Solidity for use with the Seth transaction family.

For more information, see :doc:`app_developers_guide`, :doc:`sdks`, and
:doc:`rest_api`.

Participating in Core Development
=================================

Learn about Sawtooth Architecture
---------------------------------

See the :doc:`/architecture` for information on :term:`Sawtooth core`
features such
as :term:`global state`, transactions and :term:`batches<batch>`
(the atomic unit of state change in Sawtooth), permissioning, the validator
network, the event system, and more.

Get the Sawtooth Software
-------------------------

The Sawtooth software is distributed as source code with an Apache license. You
can get the code to start building your own distributed ledger.

  * `sawtooth-core <https://github.com/hyperledger/sawtooth-core>`_: Contains
    fundamental classes used throughout the Sawtooth project, as well as the
    following items:

    * The implementation of the validator process which runs on each node
    * SDKs for writing transaction processing or validation logic in a variety
      of languages
    * Dockerfiles to support development or launching a network of validators
    * Source files for this documentation

  * `Sawtooth PBFT <https://github.com/hyperledger/sawtooth-pbft>`_:
    Use PBFT consensus with Sawtooth

  * `Sawtooth Sabre <https://github.com/hyperledger/sawtooth-sabre>`_:
    Run on-chain smart contracts executed in a WebAssembly virtual machine

  * `Sawtooth Seth <https://github.com/hyperledger/sawtooth-seth>`_:
    Deploy Ethereum Virtual Machine (EVM) smart contracts to Sawtooth

  * `Sawtooth Marketplace <https://github.com/hyperledger/sawtooth-marketplace>`_:
    Exchange customized "assets" with other users on the blockchain

  * `Sawtooth Supply Chain <https://github.com/hyperledger/sawtooth-supply-chain>`_:
    Trace the provenance and other contextual information of any asset

Join the Sawtooth Community
---------------------------

Sawtooth is an open source project under the Hyperledger umbrella. We welcome
working with individuals and companies interested in advancing distributed
ledger technology. Please see :doc:`/community` for ways to become a part of
the Sawtooth community.


Acknowledgements
================

This project uses software developed by the OpenSSL Project for use in the
OpenSSL Toolkit (http://www.openssl.org/).

This project relies on other third-party components. For details, see the
LICENSE and NOTICES files in the `sawtooth-core repository
<https://github.com/hyperledger/sawtooth-core>`_.

.. |Intel (R)| unicode:: Intel U+00AE .. registered copyright symbol

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
