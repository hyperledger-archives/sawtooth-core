***********************
Configuring Permissions
***********************

Transactor Permissioning
========================

Overview
--------

A running protected network needs a mechanism for limiting which transactors
are allowed to submit batches and transactions to the validators. There are
two different methods for defining the transactors a validator will accept.

The first method is configuring a validator to only accept batches and
transactions from predefined transactors that are loaded from a local validator
config file. Once the validator is configured the list of allowed transactors
is immutable while the validator is running. This set of permissions are only
enforced when receiving a batch from a connected client, but not when receiving
a batch from a peer on the network.

The second method uses the identity namespace which will allow for network-wide
updates and agreement on allowed transactors. The allowed transactors are
checked when a batch is received from a client, received from a peer, and
when a block is validated.

When using both on-chain and off-chain configuration, the validator only
accepts transactions and batches from a client if both configurations agree it
should be accepted. If a batch is received from a peer, only on-chain
configuration is checked.

It is possible that in the time that the batch has been in the pending queue,
the transactor permissions have been updated to no longer allow a batch signer
or a transaction signer that is being included in a block. For this reason, the
allowed transactor roles will also need to be checked on block validation.

.. _Off-Chain_Transactor_Permissioning:

Off-Chain Transactor Permissioning
----------------------------------
Validators can be locally configured by creating a validator.toml file and
placing it in the config directory. Adding configuration for transactor
permissioning to the configuration shall be done in the following format:

validator.toml:

.. code-block:: none

  [permissions]

  ROLE = POLICY_NAME

Where ROLE is one of the roles defined below for transactor permissioning and
equals the filename for a policy. Multiple roles may be defined in the same
format within the config file.

The policies are stored in the policy_dir defined by the path config. Each
policy will be made up of permit and deny rules, similar to policies defined in
the Identity Namespace. Each line will contain either a “PERMIT_KEY” or
“DENY_KEY” and should be followed with either a public key for an allowed
transactor or an * to allow all possible transactors. The rules will be
evaluated in order.

Policy file:

.. code-block:: none

  PERMIT_KEY <key>
  DENY_KEY <key>


On-Chain Transactor Permissioning
---------------------------------
The Identity Namespace stores roles as key-value pairs, where the key is a role
name and the value is a policy. All roles that limit who is allowed to sign
transactions and batches should start with transactor as a prefix.

.. code-block:: none

  transactor.SUB_ROLE = POLICY_NAME

SUB_ROLEs are more specific signing roles, for example who is allowed to sign
transactions. Each role equals a policy name that corresponds to a policy
stored in state. The policy contains a list of public keys that correspond
to the identity signing key of the transactors.

To configure on-chain roles, the signer of identity transactions needs to have
their public key set in the Setting "sawtooth.identity.allowed_keys". Only
those transactors whose public keys are in that setting are allowed to update
roles and policies.

.. code-block:: console

  $ sawset proposal create sawtooth.identity.allowed_keys=02b2be336a6ada8f96881cd55fd848c10386d99d0a05e1778d2fc1c60c2783c2f4

Once your signer key is stored in the setting, the ``identity-tp`` command can be used
to set and update roles and policies. Make sure that the Identity transaction
processor and the REST API are running.

.. literalinclude:: ../cli/output/sawtooth_identity_policy_create_usage.out
  :language: console

.. literalinclude:: ../cli/output/sawtooth_identity_role_create_usage.out
  :language: console

For example, running the following will create a policy that permits all
and is named policy_1:

.. code-block:: console

    $ sawtooth identity policy create policy_1 "PERMIT_KEY *"

To see the policy in state, run the following command:

.. code-block:: console

  $ sawtooth identity policy list
  policy_1:
    Entries:
      PERMIT_KEY *

Finally, run the following command to set the role for transactor to permit all:

.. code-block:: console

    $ sawtooth identity role create transactor policy_1

To see the role in state, run the following command:

.. code-block:: console

    $ sawtooth identity role list
    transactor: policy_1

Transactor Roles
----------------
The following are the identity roles that are used to control which transactors
are allowed to sign transactions and batches on the system.

default:
  When evaluating role permissions, if the role has not been set, the default
  policy will be used. The policy can be changed to meet the network's
  requirements after initial start-up by submitting a new policy with the name
  default. If the default policy has not been explicitly set, the default
  is “PERMIT_KEY \*”.

transactor:
  The top level role for controlling who can sign transactions and batches on
  the system will be transactor. This role shall be used when the allowed
  transactors for transactions and batches are the same. Any transactor whose
  public key is in the policy will be allowed to sign transactions and batches,
  unless a more specific sub-role disallows their public key.

transactor.transaction_signer:
  If a transaction is received that is signed by a transactor who is not
  permitted by the policy, the batch containing the transaction will be dropped.

transactor.transaction_signer.{tp_name}:
  If a transaction is received for a specific transaction family that is signed
  by a transactor who is not permitted by the policy, the batch containing the
  transaction will be dropped.

transactor.batch_signer:
  If a batch is received that is signed by a transactor who is not permitted by
  the policy, that batch will be dropped.

Validator Key Permissioning
===========================

Overview
--------

One of the permissioning requirements is that the validator network be able to
limit the nodes that are able to connect to it. The permissioning rules
determine the roles a connection is able to play on the network. The roles
control the types of messages that can be sent and received over a given
connection. The entities acting in the different roles will be referred to as
requesters below.

Validators are able to determine whether messages delivered to them should
be handled or dropped based on a set of role and identities stored within the
Identity namespace. Each requester will be identified by the public key derived
from their identity signing key. Permission verifiers examine incoming
messages against the policy and the current configuration and either permit,
drop, or respond with an error. In certain cases, the connection will be
forcibly closed -- for example: if a node is not allowed to connect to the
validator network.

This on-chain approach allows the whole network to change its policies at the
same time while the network is live, instead of relying on a startup
configuration.

Configuring Authorization
-------------------------
The Identity namespace stores roles as key-value pairs, where the key is a role
name and the value is a policy. Validator network permissioning roles use
the following pattern:

.. code-block:: none

  network[.SUB_ROLE] = POLICY_NAME

where network is the name of the role to be used for validator network
permissioning. POLICY_NAME refers to the name of a policy that is set in the
Identity namespace. The policy defines the public keys that are allowed to
participate in that role. The policy is made up of PERMIT_KEY and DENY_KEY
rules and is evaluated in order. If the public key is denied, the connection
will be rejected. For more information, please look at the
:doc:`Identity Transaction Family <../transaction_family_specifications/identity_transaction_family>`.

Like above, run the following command to set the role for network to permit all:

.. code-block:: console

    $ sawtooth identity role create network policy_1

To see the role in state, run the following command:

.. code-block:: console

    $ sawtooth identity role list
    network: policy_1

Network Roles
-------------
The following is the suggested high-level role for on-chain validator network
permissioning.

network
  If a validator receives a peer request from a node whose public key is not
  permitted by the policy, the message will be dropped, an
  AuthorizationViolation will be returned, and the connection will be closed.

This role is checked by the permission verifier when the following
messages are received:

- GossipMessage
- GetPeersRequest
- PeerRegisterRequest
- PeerUnregisterRequest
- GossipBlockRequest
- GossipBlockResponse
- GossipBatchByBatchIdRequest
- GossipBatchByTransactionIdRequest
- GossipBatchResponse
- GossipPeersRequest
- GossipPeersResponse

network.consensus
  If a validator receives a GossipMessage that contains a new block published
  by a node whose public key is not permitted by the policy, the message will
  be dropped, an AuthorizationViolation will be returned, and the connection
  will be closed.

In the future, other sub-roles can be added to further restrict access to
specific functions of the role. For example network.gossip could control who is
allowed to send gossip messages.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
