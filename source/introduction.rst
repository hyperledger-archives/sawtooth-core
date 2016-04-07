************
Introduction
************

.. caution::

    This project includes a consensus algorithm, PoET (Proof of Elapsed Time),
    which is intended to run in a Trusted Execution Environment (TEE), such as
    `Intel® Software Guard Extensions (SGX)
    <https://software.intel.com/en-us/isa-extensions/intel-sgx>`_.
    This release includes software which runs outside of SGX and simulates the
    behavior of the PoET algorithm. It does **not** provide security in this
    mode. This project is intended for experimental usage and we recommend
    against using it for security sensitive applications.

This project, called "Sawtooth Lake" is a highly modular platform for
building, deploying and running distributed ledgers. Distributed ledgers
provide a digital record (such as asset ownership) that is maintained
without a central authority or implementation. Instead of a single,
centralized database, participants in the ledger contribute resources
to shared computation that ensures universal agreement on the state of
the ledger. While Bitcoin is the most popular distributed ledger, the
technology has been proposed for many different applications ranging
from international remittance, insurance claim processing, supply chain
management and the Internet of Things (IoT).

Distributed ledgers generally consist of three basic components:

    * A data model that captures the current state of the ledger

    * A language of transactions that change the ledger state

    * A protocol used to build consensus among participants around
      which transactions will be accepted by the ledger.

In Sawtooth Lake the data model and transaction language are implemented
in a “transaction family”. While we expect users to build custom transaction
families that reflect the unique requirements of their ledgers, we provide
three transaction families that are sufficient for building, testing and
deploying a marketplace for digital assets:

    * EndPointRegistry - A transaction family for registering ledger
      services.

    * IntegerKey - A transaction family used for testing deployed ledgers.

    * MarketPlace - A transaction family for buying, selling and trading
      digital assets.

This set of transaction families provides an “out of the box” ledger that
implements a fully functional marketplace for digital assets.


Consensus
=========

Consensus is the process of building agreement among a group of mutually
distrusting participants. There are many different algorithms for building
consensus based on requirements related to performance, scalability,
consistency, threat model, and failure model. While most distributed ledgers
operate with an assumption of Byzantine failures (malicious attacker),
other properties are largely determined by application requirements.
For example, ledgers used to record financial transactions often require
high transaction rates with relatively few participants and immediate
finality of commitment. Consumer markets, in contrast, require substantial
aggregate throughput across a large number of participants; however,
short-term finality is less important.

Algorithms for achieving consensus with arbitrary faults generally require
some form of voting among a known set of participants. Two general approaches
have been proposed. The first, often referred to as "Nakamoto consensus",
elects a leader through some form of “lottery”. The leader then proposes a
block that can be added to a chain of previously committed blocks. In Bitcoin,
the first participant to successfully solve a cryptographic puzzle wins
the leader-election lottery. The elected leader broadcasts the new block
to the rest of the participants who implicitly vote to accept the block by
adding the block to a chain of accepted blocks and proposing subsequent
transaction blocks that build on that chain.

The second approach is based on traditional
`Byzantine Fault Tolerance (BFT)
<https://en.wikipedia.org/wiki/Byzantine_fault_tolerance>`_
algorithms and uses multiple rounds of explicit votes to achieve consensus.
`Ripple <https://ripple.com/>`_ and `Stellar <https://www.stellar.org/>`_
developed consensus protocols that extend traditional BFT for open
participation.

Sawtooth Lake abstracts the core concepts of consensus, isolates consensus
from transaction semantics, and provides two consensus protocols with
different performance trade-offs.  The first, called PoET for “Proof
of Elapsed Time”, is a lottery protocol that builds on trusted execution
environments (TEEs) provided by Intel's SGX to address the needs of
large populations of participants. The second, Quorum Voting,
is an adaptation of the Ripple and Stellar consensus protocols and
serves to address the needs of applications that require immediate
transaction finality.


Proof of Elapsed Time (PoET)
============================

For the purpose of achieving distributed consensus efficiently,
a good lottery function has several characteristics:

    * Fairness: The function should distribute leader election
      across the broadest possible population of participants.

    * Investment: The cost of controlling the leader election
      process should be proportional to the value gained from it.

    * Verification: It should be relatively simple for all participants
      to verify that the leader was legitimately selected.

Sawtooth Lake provides a Nakamoto consensus algorithm called PoET
that uses a trusted execution environment (TEE) such as
`Intel® Software Guard Extensions (SGX)
<https://software.intel.com/en-us/isa-extensions/intel-sgx>`_
to ensure the safety and randomness of the leader election process
without requiring the costly investment of power and specialized
hardware inherent in most “proof” algorithms. Our approach
is based on a guaranteed wait time provided through the TEE.

Basically, every validator requests a wait time from a trusted function.
The validator with the shortest wait time for a particular transaction
block is elected the leader. One function, say “CreateTimer” creates
a timer for a transaction block that is guaranteed to have been created
by the TEE. Another function, say “CheckTimer” verifies that the timer
was created by the TEE and, if it has expired, creates an attestation
that can be used to verify that validator did, in fact, wait the allotted
time before claiming the leadership role.

The PoET leader election algorithm meets the criteria for a good lottery
algorithm. It randomly distributes leadership election across the entire
population of validators with distribution that is similar to what is
provided by other lottery algorithms. The probability of election
is proportional to the resources contributed (in this case, resources
are general purpose processors with a trusted execution environment).
An attestation of execution provides information for verifying that the
certificate was created within the TEE (and that the validator waited
the allotted time). Further, the low cost of participation increases the
likelihood that the population of validators will be large, increasing
the robustness of the consensus algorithm.

Our “proof of processor” algorithm scales to thousands of participants
and will run efficiently on any Intel processor that supports SGX.

**As noted in the caution above, the current implementation simulates
the behavior of the PoET algorithm running in a trusted execution environment
and is not secure.** There are some benefits to using a simulator:

    * It does not require you to have a processor which supports SGX
      in order to experiment with Sawtooth Lake.

    * It allows running many validators (nodes) on a single system. An SGX
      implementation of PoET will allow only a single node per CPU socket.


Getting Sawtooth Lake
=====================

The Sawtooth Lake platform is distributed in source code form with
an Apache license. You can get the code `here
<https://github.com/intelledger>`_ and start building your own
distributed ledger.

Repositories
============

Here are the repositories:

sawtooth-core
    Contains fundamental classes used throughout the Sawtooth Lake project

sawtooth-validator
    Contains the implementation of the validator process which runs on each
    node

sawtooth-mktplace
    Contains the implementation of a transaction family for buying, selling and
    trading digital assets, and a client program for interacting with a node
    to execute market transactions.

sawtooth-dev-tools
    Contains a Vagrant environment for easily launching a network of validators

sawtooth-docs
    Contains the source files for this documentation


