*****************
Intel® SGX Primer
*****************

Intel® SGX is a `Trusted Execution Environment`_. This primer is a high-level
introduction to the parts of SGX required to understand the SGX implementation
of Proof of Elapsed Time (PoET) consensus algorithm. See the
full SGX reference for the proper specification [1]_.

.. _Trusted Execution Environment: https://en.wikipedia.org/wiki/Trusted_execution_environment

Enclave
=======

Enclave
  A protected area in an application’s address space which provides
  confidentiality and integrity even in the presence of privileged malware.

The main concept SGX deals with is the enclave. “Enclave” can also be used to
refer to a specific enclave that has been initialized with a specific set of
code and data. An enclave can:

* Prove its identity to a remote party (see Attestation)
* Request enclave-specific and platform-specific keys that can be used to
  protect keys and data that it wishes to store outside the enclave.

Enclave Creation
----------------

Creation of an enclave follows the process below:

1. Code and data are loaded from untrusted memory.
2. The `Enclave Measurement`_ is calculated and stored.
3. The `Sealing Authority`_ is verified and stored
4. Control is transferred to the enclave code.

Access Control
--------------

Memory access is subject to the following rules:

* Memory within an enclave cannot be accessed when the enclave does not have
  control.
* Memory outside an enclave cannot be accessed while the enclave has control.
* Interactions between code and data within and outside enclaves is done through
  user defined set of “Enclave Interface Functions”.

All interface functions are defined at compile time. Interactions between
untrusted and trusted code can only take place using these interface functions. A pre-processor generates “proxy” functions to
handle interactions between untrusted application code and trusted enclave code.

Enclave Measurement
-------------------

“While the enclave is being built, a secure log is recorded reflecting the
contents of the enclave and how it was loaded. This secure log is [used to
calculate] the enclave’s measurement.” [2]_ The enclave’s measurement is the is a
SHA-256 digest of the internal creation log. This measurement is used as the
identity of the enclave. The enclave measurement can also be referred to as the
"Enclave Identity" or "MRENCLAVE".

Sealing Authority
-----------------

“The Sealing Authority is an entity that signs the enclave prior to
distribution, typically the enclave builder.” [2]_ Upon creation of an enclave,
the enclave is presented with a signed certificate containing an Enclave
Measurement and the public key of the Sealing Authority. The enclave verifies
the signature for the certificate and then compares the “proposed” measurement
in the certificate against the measurement it computed locally through creation.
If they are the same, the enclave stores the public key as the Sealing Authority
for the enclave. The sealing authority can also be refered to as the "Sealing
Identity" or "MRSIGNER".

Execution
---------

Execution of enclave code follows the process below:

1. The untrusted application code calls an untrusted proxy function defined by
   the enclave API.
#. The proxy function prepares input arguments for the enclave.
#. The proxy function makes an ECall and transfers control to the trusted
   enclave code.
#. The trusted enclave code executes, making OCalls as needed to interact with
   OS and other untrusted code.
#. Trusted enclave code prepares output data for untrusted application code.
#. Trusted enclave code transfers control back to untrusted application code.

Attestation
===========

Attestation
  The process of demonstrating that a piece of software has been properly
  instantiated on the platform.

Within SGX, attestation is, “the mechanism by which another party can gain
confidence that the correct software is running within an enclave on an enabled
platform.” [2]_

Enclave Reports
---------------

Enclaves can generate a data structure referred to as a "report" which can be
used for attestation. When creating a report, the measurement of the target
enclave (the intended receiver of the report) is required. Enclave reports
contain:

* The enclave’s identity (Sealing Authority and Enclave Measurement)
* Additional enclave attributes
* Additional developer-defined information
* A message authentication code (MAC)

Intra-Platform Attestation
--------------------------

Intra-Platform attestation refers to attestation between two enclaves on the
same platform. That is, they are both running on the same Intel® SGX enabled
processor and host.

1. A report is created for a given target enclave on the same platform.
2. The target enclave verifies the report.
3. A secure channel is then constructed between the two enclaves using standard
   encryption methods.

Inter-Platform Attestation
--------------------------

Inter-Platform attestation refers to attestation between two enclaves running on
different platforms, most likely connected by a network connection. This form of
attestation is used by PoET and Intel® provides an implementation of this service
through the Intel® Attestation Service (IAS). It is also known as “remote
attestation”.

A special “Quoting Enclave” is provided with SGX and is used in Inter-process
Attestation. The quoting enclave processes reports using the following
procedure:

* The Quoting Enclave verifies reports submitted to it from other enclaves on
  the same platform using the Intra-Platform Attestation described above.
* It then replaces the MAC with a signature created with an anonymous credential
  tied to the device hardware.
* This new data structure is called a “quote”.

The Quoting Enclave uses the Intel® Enhanced Privacy ID (EPID) signature scheme
to overcome the privacy concerns associated with using a small number of
asymmetric keys for signing over the life of a platform. “EPID is a group
signature scheme that allows a platform to sign objects without uniquely
identifying the platform or linking different signatures.” [2]_ In “anonymous”
mode, a signature verifier cannot associate a given signature with a given
identity. In “pseudonymous” mode, a signature verifier can determine whether it
has verified a platform previously. PoET uses the "pseudonymous" or "named base"
mode. This provides a consistent identity for a given blockchain network, but
but does not otherwise link an identity to other blockchain networks or other
SGX applications.

The remote attestation procedure is roughly the following:

1. A local application enclave wants to interact with a remote enclave so it
   connects to the remote service through the local application.
#. The remote service issues a challenge to the local application.
#. The local application retrieves the local quoting enclave’s identity and
   passes it into the the local application enclave along with the challenge.
#. The local application enclave generates a “manifest” that includes:

   a. A response to the challenge
   #. An ephemeral public key

#. The local application enclave generates a hash digest of the manifest. An
   enclave report is generated which includes the hash digest and has the
   platform’s (local) Quoting Enclave as its target enclave.
#. The enclave report and manifest are sent to the local application which
   forwards the report to the Quoting Enclave.
#. The Quoting Enclave verifies the report, generates an enclave quote using its
   EPID key, and forwards the quote to the local application.
#. The local application forwards the enclave quote and manifest to the remote
   service.
#. The remote service verifies the quote and manifest

   a. An EPID public key certificate along with revocation information can be
      used to verify both locally
   #. Alternatively, an attestation verification service can be used (see IAS
      below).

Intel® Attestation Service
--------------------------

As an alternative to keeping track of a set of verified and revoked enclave
identities, Intel® provides an attestation service (IAS) which can be used to
verify enclave quotes. Roughly speaking, IAS provides:

* An up-to-date list of revoked EPID credentials
* Enclave quote verification

Inter-Platform Attestation and IAS are used by PoET when a new validator is
signing up with a network to verify:

* The validator is running the correct PoET code in a trusted enclave.
* The enclave has valid and current credentials conveying a trustworth TCB.

Each Sawtooth blockchain Network should use a unique Service Provider ID. For
example, this could be the identity of the consortium. All nodes in that network
use the same Service Provider ID in the PoET enclave. The Service Provider ID is
used to authenticate with the Intel Attestation Service.

.. [1] “Intel® Software Guard Extensions Programming Reference.” 329298-002US. October 2014
.. [2] “Innovative Technology for CPU Based Attestation and Sealing.” Anati, Gueron, Johnson, Scarlata. Intel Corporation.
.. [3] “Intel® Software Guard Extensions: EPID Provisioning and Attestation Services.” Johnson, Scarlata, Rozas, Brickell, Mckeen. Intel Corporation.
