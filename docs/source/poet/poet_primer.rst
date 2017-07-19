***********
PoET Primer
***********

PoET, short for “Proof of Elapsed Time", is a Nakamoto-style or "lottery"
consensus algorithm. It is designed to be a production-grade protocol capable of
supporting large network populations.

For the purpose of achieving distributed consensus efficiently, a good lottery
function has several characteristics:

* Fairness: The function should distribute leader election
  across the broadest possible population of participants.

* Investment: The cost of controlling the leader election
  process should be proportional to the value gained from it.

* Verification: It should be relatively simple for all participants
  to verify that the leader was legitimately selected.

The PoET leader election algorithm meets the criteria for a good lottery
algorithm. It randomly distributes leadership election across the entire
population of validators with distribution that is similar to what is provided
by other lottery algorithms. The probability of election is proportional to the
resources contributed (in this case, resources are general purpose processors
with a trusted execution environment). An attestation of execution provides
information for verifying that the certificate was created within the enclave
(and that the validator waited the allotted time). Further, the low cost of
participation increases the likelihood that the population of validators will be
large, increasing the robustness of the consensus algorithm.

The following gives a mid-level description of PoET 1.0 and how it operates. It
assumes an understanding of trusted execution environments such as Intel® SGX as
well as some background knowledge of consensus models. At a minimum, the reader
should have a high-level understanding of the Byzantine Generals Problem. [1]_
Many of the specific details are omitted because they are documented in the
comprehensive :doc:`poet_spec`.

Trusted Computing Base
======================

PoET leverages a trusted execution environment (TEE) to ensure fair elections
without requiring the costly investment of power and specialized hardware
inherent in most “proof” algorithms. PoET was first designed and implemented
with Intel® SGX and makes the following assumptions about the trusted execution
environment it depends on:

1. Code and data cannot be accessed or modified once they have been loaded into
   the TEE, except through a strict interface defined prior to loading.
2. Attestation of the code and data loaded into the TEE is possible.
3. Individual “platforms” have a hardware encoded identity in the form of an
   anonymous, revocable credential.
4. An external attestation service (EAS) is available which:

   a. Maintains credential revocation lists.
   b. Validates attestation of code deployed to the TEE.

5. Random number generation is possible within the TEE.

Peer Signup
===========

The following describes the PoET signup process assuming a generic TEE.
"PoET Module" is used to refer to the portion of PoET that runs outside the
TEE. "PoET Enclave" is used to refer to the code that runs inside the TEE.

1. The PoET Enclave is loaded into the TEE by the PoET Module.
2. Attestation is requested from the EAS by the PoET Module.
3. The EAS validates the PoET Enclave and responds with an attestation.
4. The PoET Module requests to join the network and includes the attestation
   with this request.

Leader Election
===============

Individual peers perform the following to participate in leader election:

1. Calculate the “local mean” of the network:

   a. The local mean is computed so that the time between elections is
      approximately the target rate for the network given its size.
   b. The target rate is a configurable parameter and should be “selected to
      minimize the probability of a collision.” (See :doc:`poet_spec` for more
      detail.)

#. Create a new “wait timer” and “wait timer signature” from within the TEE.

   a. Sample an exponential distribution whose mean is the local mean.
   b. The wait timer wraps the sample and includes some additional information.

#. Wait for the time specified in the wait timer.
#. Create a new “wait certificate” and “wait certificate signature” based on the
   wait timer and wait timer signature within the TEE.

   a. The wait timer signature proves the wait timer is valid.
   b. If the time elapsed since creating the timer is less than the sample, this
      fails.
   c. If the time elapsed since creating the timer is greater than some
      expiration time, this fails.

#. Construct a "claim" consisting of the wait certificate, the wait certificate
   signature, the peer's identity, and an ordered list of valid requests to
   commit to distributed state.
#. If another claim has been received and the other claim's wait certificate
   contains a smaller sample, go back to step 1. Otherwise, broadcast this
   peer's claim to the network.
#. Individual peers accept the claim with the wait certificate containing the
   smallest sample for a given election.

.. note::

    When PoET is used with a blockchain, leader elections occur as part of block
    publishing. In this case, the "claim" described above is included in the
    block header and is referred to as the peer "claiming a block".

Forking
-------

Because leader elections are non-deterministic and networks have latency, peers
may think they have won or have the winning block, but may later receive a
"better" block with a smaller wait timer. When nodes disagree about what the
current block is, we say the network has "forked". Upon receiving a "better"
block, the peer must discard the previous block and any blocks that have been
built on top of that block and restart from the new "better" block. This is
known "fork resolution" and in order for it to work, the algorithm for deciding
which block is the "best" must be deterministic. Under normal conditions, forks
will appear for a short period of time around block boundaries and then quickly
resolve as peers receive the "best" block.

Election Policies
=================

In addition to the election process, the following additional policies are
enforced to mitigate security risks. Each of the policies contains a
configurable parameter and is named after that parameter.

K-policy
  A peer must repeat the signup process after it has won K elections.

The signup process involves checking the identity of the peer against a
revocation list maintained by the attestation service. Enforcing periodic
attestation allows the network to identify peers that have been blacklisted by
the attestation service since they first signed up.

c-policy
  A peer may not win an election until at least c blocks have been committed
  since it signed up.

This policy prevents peers from manipulating elections by first generating
multiple identities with corresponding wait timers, choosing a wait timer with a
high probability of winning, and then signing up with whichever identity
corresponded to the low wait timer.

z-policy
  A peer may not win an election more often than is statistically probable.

As a final check that a peer is not manipulating elections, a statistic is
calculated to determine the probability that a correct peer could win as often
as the given peer has won. If the probability is below some threshold, then the
peer is not allowed to win the election.

.. [1] “The Byzantine Generals Problem.” Lamport, Shostak, Pease. SRI International.
