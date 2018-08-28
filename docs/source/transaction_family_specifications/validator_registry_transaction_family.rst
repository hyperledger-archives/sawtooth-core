*************************************
Validator Registry Transaction Family
*************************************

Overview
=========

The validator registry transaction family provides a way to add new validators
to the network.

The validator's information is used by poet_consensus to verify that when a
validator tries to claim a block it is following the block claiming policies of
PoET consensus. For example, the Z policy will refuse blocks from a validator
if it has already claimed a disproportionate amount of blocks compared to the
other validators on the network. The C policy says that a validator may not
claim blocks, after being added to the registry or updating their information,
until a certain number of blocks are claimed by other participants. The number
of blocks claimed since signup can be found by checking the current block number
against the block number that is stored in the validator information when the
validator registry information has either been added or updated. And finally the K
policy requires new signup information to be sent to the validator registry
after it has claimed a maximum number of block. If the validator is not found
in the validator registry the block will be rejected since there is no way to
validate.

Currently the number of blocks claimed by a specific validator is stored within
the poet_consensus, not within the validator registry.


State
=====
This section describes in detail how validator information, including
identification and signup data, is stored and addressed using the validator
registry transaction family.

The following protocol buffers definition defines the validator info:

.. code-block:: protobuf

  message ValidatorInfo {
    // The name of the endpoint. It should be a human readable name.
    string name = 1;

    // The validator's public key (currently using signer_public_key as this is
    // stored in the transaction header)
    string id = 2;

    // This is the protocol buffer described below.
    SignUpInfo signup_info = 3;

    // The header signature for the ValidatorRegistryPayload transaction. This
    // will be used to look up the block the ValidatorInfo was committed on.
    string transaction_id = 4;
  }


The above ValidatorInfo includes the following protocol buffer:

.. code-block:: protobuf

  message SignUpInfo {
    // Encoded public key corresponding to private key used by PoET to sign
    // wait certificates.
    string poet_public_key = 1;

    // Information that can be used internally to verify the validity of
    // the signup information stored as an opaque buffer.
    string proof_data = 2;

    // A string corresponding to the anti-Sybil ID for the enclave that
    // generated the signup information.
    string anti_sybil_id = 3;

    // The nonce associated with the signup info.  Note that this must match
    // the nonce provided when the signup info was created.
    string nonce = 4;
  }

Currently the poet_enclave needs a way to check how many validators are
currently registered within the validator registry. It also needs a way to
find the validator_id associated with an anti-sybil_id. A ValidatorMap, where
the anti_sybil_id is the key and the validator_id is the value solves both of
these problems.

.. code-block:: protobuf

  message ValidatorMap {
      // Contains a validator entry where the key is an  anti_sybil_id,
      // and the value is a validator_id
      message Entry {
          string key = 1;
          string value = 2;
      }

      // List of validator entries
      repeated Entry entries = 1;
  }


This can be used to check the number of validators registered. This
information is used to decide what number of blocks a validator has to wait
for before it can start claiming blocks after it adds new signup information
to the validator registry. This check is necessary because if the number of
blocks that must be waited on is greater than the number of validators minus
one, it is possible for the network to get into a state where nobody can
publish blocks because the validators are all waiting for more blocks to be
committed or their signup information to be added to a block.

Validator registry transaction would not be able to be done at the same time as
any other transaction as an update to the ValidatorMap is necessary. However all
other transaction that need to access the state set by the validator registry,
can be done in parallel since it will only be a read and  the statics for each
validator is stored in the poet_enclave. If this was changed so that the stats
were stored in the validator registry this would require a write to state every
time a block is published and would reduce the ability for parallelism.

Addressing
----------

When a validator’s signup info is registered or updated it should be accessed
using the following algorithm:

Addresses for the validator registry transaction family are set by adding
sha256 hash of the validator's id to the validator registry namespace. The
namespace for the validator registry will be the first 6 characters of the
sha256  hash of the string “validator_registry”, which is “6a4372” For example,
the validator signup info of a validator with the id “validator_id” could be
set like this:

.. code-block:: pycon

  >>>“6a4372” + hashlib.sha256('validator_id'.encode("utf-8")).hexdigest()
  '6a43722aee5b550a3cbd1595f4de10049ee805bc035b5e232dfacfc31cc6275170b30d'

The map of the current registered validator_id should be stored at the
following address:


.. code-block:: pycon

  >>>“6a4372” + hashlib.sha256('validator_map'.encode()).hexdigest()
  '6a437247a1c12c0fb03aa6e242e6ce988d1cdc7fcc8c2a62ab3ab1202325d7d677e84c'

Transaction Payload
===================
Validator registry transaction family payloads are defined by the following
protocol buffers code:

.. code-block:: protobuf

  message ValidatorRegistryPayload {
    // The action that the transaction processor will take. Currently this
    // is only “register”, but could include other actions in the futures
    // such as “revoke”
    string verb = 1;

    // The name of the endpoint. It should be a human readable name.
    string name = 2;

    // Validator's public key (currently using signer_public_key as this is
    // stored in the transaction header)
    string id = 3;

    // This is the protocol buffer described above.
    SignUpInfo signup_info = 4;

  }


Transaction Header
==================

Inputs and Outputs
------------------

The inputs for validator registry family transactions must include:

* the address of *validator_id*
* the address of *validator_map*
* the address of *sawtooth.poet.report_public_key_pem*
* the address of *sawtooth.poet.valid_enclave_measurement*
* the address of *sawtooth.poet.valid_enclave_basenames*

The outputs for validator registry family transactions must include:

* the address of *validator_id*
* the address of *validator_map*


Dependencies
------------

None

Family
------
- family_name: "sawtooth_validator_registry"
- family_version: "1.0"


Execution
=========

Untrusted Python code that is a part of the transaction processor will verify
the attestation verification report for the signup information. It is important
to note that the IAS report public key will need to be on the blockchain, and
that it will need to be set during configuration. This will allow both the simulator
logic and real SGX logic to be the same.

If the validator_name does not match syntactic requirements, the transaction is
invalid. The current requirement is that the validator_name is 64 characters
or less.

If the validator_id does not match the transaction signer, the transaction is
invalid. The validator_id should be the same as the signer_public_key stored in the
transaction header.

The signup info needs to be verified next. The signup info, public key hash, and
the most recent wait_certificate_id are passed to verify the signup data.

If any of the signup info checks fail verification, the validator_registry
transaction is rejected and a invalid transaction response is returned.

If the transaction is deemed to be valid, the validator_id is used to find
the address where the validator_info should be stored. Store the serialized
ValidatorInfo protocol buffer in state at the address as mentioned above. If
this validator is new (not updating its SignUpInfo), the validator’s id needs
to be added to the validator_map.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
