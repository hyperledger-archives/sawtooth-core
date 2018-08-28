***************************
Settings Transaction Family
***************************

Overview
=========

The Settings transaction family provides a methodology for storing on-chain
configuration settings.

The settings stored in state as a result of this transaction family play a
critical role in the operation of a validator. For example, the consensus
module uses these settings; in the case of PoET, one cross-network setting is
target wait time (which must be the same across validators), and this setting
is stored as sawtooth.poet.target_wait_time.  Other parts of the system use
these settings similarly; for example, the list of enabled transaction
families is used by the transaction processing platform.

In addition, pluggable components such as transaction family implementations
can use the settings during their execution.

This design supports two authorization options: a) a single authorized key
which can make changes, and b) multiple authorized keys.  In the case of
multiple keys, a percentage of votes signed by the keys is required to make a
change.

.. note::

	While usable in a production sense, this transaction family also serves as
	a reference specification and implementation.  The authorization scheme
	here provides a simple voting mechanism; another authorization scheme may
	be better in practice.  Implementations which use a different
	authorization scheme can replace this implementation by adhering to the
	same addressing scheme and content format for settings.  (For example, the
	location of PoET settings can not change, or the PoET consensus module
	will not be able to find them.)


State
=====

This section describes in detail how settings are stored and addressed using
the Settings transaction family.

The setting data consists of setting/value pairs. A setting is the name for the
item of configuration data. The value is the data in the form of a string.

Settings
--------

Settings are namespaced using dots:

============================================= ============
Setting (Examples)                            Value
============================================= ============
sawtooth.poet.target_wait_time                5
sawtooth.validator.max_transactions_per_block 1000
============================================= ============


The Settings transaction family uses the following settings for its own configuration:

+-------------------------------------------+------------------------------------------------------------------------------+
| Setting (Settings)                        | Value Description                                                            |
+===========================================+==============================================================================+
| sawtooth.settings.vote.authorized_keys    | List of public keys allowed to vote                                          |
+-------------------------------------------+------------------------------------------------------------------------------+
| sawtooth.settings.vote.approval_threshold | Minimum number of votes required to accept or reject a proposal (default: 1) |
+-------------------------------------------+------------------------------------------------------------------------------+
| sawtooth.settings.vote.proposals          | A list of proposals to make settings changes (see note)                      |
+-------------------------------------------+------------------------------------------------------------------------------+

.. note::
	*sawtooth.settings.vote.proposals* is a base64 encoded string of the
	protobuf message *SettingCandidates*. This setting cannot be modified
	by a proposal or a vote.


Definition of Setting Entries
-----------------------------

The following protocol buffers definition defines setting entries:

.. code-block:: protobuf
	:caption: File: sawtooth-core/protos/setting.proto

	// Setting Container for the resulting state
	message Setting {
	    // Contains a setting entry (or entries, in the case of collisions).
	    message Entry {
	        string key = 1;
	        string value = 2;
	    }

	    // List of setting entries - more than one implies a state key collision
	    repeated Entry entries = 1;
	}

sawtooth.settings.vote.proposals
--------------------------------

The setting 'sawtooth.settings.vote.proposals' is stored as defined by the
following protocol buffers definition. The value returned by this  setting is
a base64 encoded *SettingCandidates* message:

.. code-block:: protobuf
	:caption: File: sawtooth-core/families/settings/protos/settings.proto

	// Contains the vote counts for a given proposal.
	message SettingCandidate {
	    // An individual vote record
	    message VoteRecord {
	        // The public key of the voter
	        string public_key = 1;

	        // The voter's actual vote
	        SettingVote.Vote vote = 2;

	    }

	    // The proposal id, a hash of the original proposal
	    string proposal_id = 1;

	    // The active proposal
	    SettingProposal proposal = 2;

	    // list of votes
	    repeated VoteRecord votes = 3;
	}

	// Contains all the setting candidates up for vote.
	message SettingCandidates {
	    repeated SettingCandidate candidates = 1;
	}


Addressing
----------

When a setting is read or changed, it is accessed by addressing it using the
following algorithm:

Setting keys are broken into four parts, based on the dots in the string. For
example, the address for the key `a.b.c` is computed based on `a`, `b`, `c` and
the empty string.  A longer key, for example `a.b.c.d.e`, is still broken into
four parts, but the remaining pieces are in the last part: `a`, `b`, `c` and `d.e`.

Each of these pieces has a short hash computed (the first 16 characters of its
SHA256 hash in hex) and is joined into a single address, with the settings
namespace (`000000`) added at the beginning.

For example, the setting *sawtooth.settings.vote.proposals* could be set like
this:

.. code-block:: pycon

	>>> '000000' + hashlib.sha256('sawtooth'.encode()).hexdigest()[:16] + \
            hashlib.sha256('config'.encode()).hexdigest()[:16] + \
            hashlib.sha256('vote'.encode()).hexdigest()[:16] + \
            hashlib.sha256('proposals'.encode()).hexdigest()[:16]
        '000000a87cb5eafdcca6a8b79606fb3afea5bdab274474a6aa82c1c0cbf0fbcaf64c0b'


Transaction Payload
===================

Setting transaction family payloads are defined by the following protocol
buffers code:

.. code-block:: protobuf
	:caption: File: sawtooth-core/families/settings/protos/settings.proto

	// Setting Payload
	// - Contains either a proposal or a vote.
	message SettingPayload {
	    // The action indicates data is contained within this payload
	    enum Action {
	        // A proposal action - data will be a SettingProposal
	        PROPOSE = 0;

	        // A vote action - data will be a SettingVote
	        VOTE = 1;
	    }
	    // The action of this payload
	    Action action = 1;

	    // The content of this payload
	    bytes data = 2;
	}

	// Setting Proposal
	//
	// This message proposes a change in a setting value.
	message SettingProposal {
	    // The setting key.  E.g. sawtooth.consensus.module
	    string setting = 1;

	    // The setting value. E.g. 'poet'
	    string value = 2;

	    // allow duplicate proposals with different hashes
	    // randomly created by the client
	    string nonce = 3;
	}

	// Setting Vote
	//
	// In ballot mode, a proposal must be voted on.  This message indicates an
	// acceptance or rejection of a proposal, where the proposal is identified
	// by its id.
	message SettingVote {
	    enum Vote {
	        ACCEPT = 0;
	        REJECT = 1;
	    }

	    // The id of the proposal, as found in the
	    // sawtooth.settings.vote.proposals setting field
	    string proposal_id = 1;

	    Vote vote = 2;
	}


Transaction Header
==================

Inputs and Outputs
------------------

The inputs for config family transactions must include:

* the address of *sawtooth.settings.vote.proposals*
* the address of *sawtooth.settings.vote.authorized_keys*
* the address of *sawtooth.settings.vote.approval_threshold*
* the address of the setting being changed

The outputs for config family transactions must include:

* the address of *sawtooth.settings.vote.proposals*
* the address of the setting being changed


Dependencies
------------

None.


Family
------

- family_name: "sawtooth_settings"
- family_version: "1.0"

Execution
=========

Initially, the transaction processor gets the current values of
*sawtooth.settings.vote.authorized_keys* from the state.

The public key of the transaction signer is checked against the values in
the list of authorized keys.  If it is empty, no settings can be proposed,
save for the authorized keys.

A Propose action is validated.  If it fails, it is considered an invalid
transaction.  A *proposal_id* is calculated by taking the sha256 hash of
the raw *SettingProposal* bytes as they exist in the payload.  Duplicate
*proposal_ids* causes an invalid transaction. The proposal will be
recorded in the *SettingProposals* stored in *sawtooth.settings.vote.proposals*,
with one "accept" vote counted.  The transaction processor outputs a
*DEBUG*-level logging message similar to

.. code-block:: python3

    "Adding proposal {}: {}".format(proposal_id, repr(proposal_data).

A Vote action is validated, checking to see if *proposal_id* exists, and
the public key of the transaction has not already voted.  The value of
*sawtooth.settings.vote.approval_threshold* is read from the state.

- If the "accept" vote count is equal to or above the approval threshold,
  the proposal is applied to the state. This results in the above INFO message
  being logged. The proposal is deleted from the *SettingProposals* record.

- If the "reject" vote count is equal to or above the approval threshold, then
  it is deleted from *sawtooth.settings.vote.proposals* and an appropriate debug
  logging message logged.

Otherwise, the vote is recorded in the list of *sawtooth.settings.vote.proposals*
by the public key and vote pair.

Validation of configuration settings is as follows:

- *sawtooth.settings.vote.approval_threshold* must be a positive integer and
  must be between 1 (the default) and the number of authorized keys, inclusive
- *sawtooth.settings.vote.proposals* may not be set by a proposal

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
