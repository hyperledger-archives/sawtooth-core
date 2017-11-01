..
   Copyright 2017 Intel Corporation

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

.. _sawtooth-cli-reference-label:

************
Sawtooth CLI
************

sawtooth
========

The Sawtooth CLI has a large set of subcommands that are used to
configure, manage, and interact with the components of Sawtooth.

.. literalinclude:: output/sawtooth_usage.out
   :language: console
   :linenos:

sawtooth admin
==============

The ``sawtooth admin`` subcommands create validator keys during
initial configuration and help create the genesis block when
initializing a validator.

.. literalinclude:: output/sawtooth_admin_usage.out
   :language: console
   :linenos:

sawtooth admin genesis
======================

Overview
--------

The genesis CLI tool produces a file for use during initialization of
a validator. A network requires an initial block (known as the genesis
block) whose signature will determine the block chain id. This initial
block is produced from a list of batches, which will be applied at
genesis time. The input to the command is a set of zero or more files
containing serialized ``BatchList`` protobuf messages. The output is a
file containing a serialized ``GenesisData`` protobuf message. This
file, when placed at ``<sawtooth_data>/genesis.batch``, will trigger
the genesis process.

The location ``sawtooth_data`` depends on whether or not the
environment variable ``SAWTOOTH_HOME`` is set. If it is, then
``sawtooth_data`` is located at ``<SAWTOOTH_HOME>/data``. If it is
not, then ``sawtooth_data`` is located at ``/var/lib/sawtooth``.

Usage
-----

.. literalinclude:: output/sawtooth_admin_genesis_usage.out
   :language: console
   :linenos:

Arguments
^^^^^^^^^

- ``input_batch_file`` - a repeated list of files containing a
  serialized ``BatchList`` message. This may be empty, which will
  produce an empty genesis block.

- ``--output <filename>`` - a target file where the serialized
  ``GenesisData`` will be written. Defaults to
  ``<sawtooth_data>/genesis.batch``.

Output
^^^^^^

The output of the command displays a message where the output
``GenesisData`` is written.

Example
^^^^^^^

.. code-block:: console

    > sawtooth admin genesis config.batch mktplace.batch
    Generating /var/lib/sawtooth/genesis.batch

sawtooth admin keygen
=====================

The ``admin keygen`` command generates keys that the validator uses to
sign blocks. This system-wide key must be created during Sawtooth
configuration.

Validator keys are stored in the directory ``/etc/sawtooth/keys/``. By
default, the public-private key files are named ``validator.priv`` and
validator.pub. Use the <key-name> argument to specify a different file
name.

.. literalinclude:: output/sawtooth_admin_keygen_usage.out
   :language: console
   :linenos:

sawtooth batch
==============

The ``sawtooth batch`` subcommands display information about the
Batches in the current blockchain and submit Batches to the validator
via the REST API. A Batch is a group of interdependent transactions
that is the atomic unit of change in Sawtooth. For more information,
see “Transactions and Batches!”


.. literalinclude:: output/sawtooth_batch_usage.out
   :language: console
   :linenos:

sawtooth batch list
===================

The ``sawtooth batch list`` subcommand queries the specified Sawtooth
REST API (default: ``http://localhost:8080``) for a list of Batches in
the current blockchain. It returns the id of each Batch, the public
key of each signer, and the number of transactions in each Batch.

By default, this information is displayed as a white-space delimited
table intended for display, but other plain-text formats (CSV, JSON,
and YAML) are available and can be piped into a file for further
processing.


.. literalinclude:: output/sawtooth_batch_list_usage.out
   :language: console
   :linenos:

sawtooth batch show
===================

The ``sawtooth batch show`` subcommand queries the Sawtooth REST API
for a specific batch in the current blockchain. It returns complete
information for this batch in either YAML (default) or JSON format.
Using the ``--key`` option, it is possible to narrow the returned
information to just the value of a single key, either from the batch
or its header.

This subcommand requires the URL of the REST API (default:
``http://localhost:8080``), and can specify a username:password
combination when the REST API is behind a Basic Auth proxy.


.. literalinclude:: output/sawtooth_batch_show_usage.out
   :language: console
   :linenos:

sawtooth batch status
=====================

The ``sawtooth batch status`` subcommand queries the Sawtooth REST API
for the committed status of one or more batches, which are specified
as a list of comma-separated Batch ids. The output is in either YAML
(default) or JSON format, and includes the ids of any invalid
transactions with an error message explaining why they are invalid.
The ``--wait`` option indicates that results should not be returned
until processing is complete, with an optional timeout value specified
in seconds.

This subcommand requires the URL of the REST API (default:
``http://localhost:8080``), and can specify a username:password
combination when the REST API is behind a Basic Auth proxy.

.. literalinclude:: output/sawtooth_batch_status_usage.out
   :language: console
   :linenos:

sawtooth batch submit
=====================

The ``sawtooth batch submit`` subcommand sends one or more Batches to
the Sawtooth REST API to be submitted to the validator. The input is a
binary file with a binary-encoded ``BatchList`` protobuf, which can
contain one or more batches with any number of transactions. The
``--wait`` option indicates that results should not be returned until
processing is complete, with an optional timeout specified in seconds.

This subcommand requires the URL of the REST API (default:
``http://localhost:8080``), and can specify a username:password
combination when the REST API is behind a Basic Auth proxy.


.. literalinclude:: output/sawtooth_batch_submit_usage.out
   :language: console
   :linenos:

sawtooth block
==============

The ``sawtooth block`` subcommands display information about the
blocks in the current blockchain.

.. literalinclude:: output/sawtooth_block_usage.out
   :language: console
   :linenos:

sawtooth block list
===================

The ``sawtooth block list`` subcommand queries the Sawtooth REST API
(default: ``http://localhost:8080``) for a list of all blocks in the
current chain. It returns the id and number of each block, the public
key of each signer, and the number of transactions and batches in
each.

By default, this information is displayed as a white-space delimited
table intended for display, but other plain-text formats (CSV, JSON,
and YAML) are available and can be piped into a file for further
processing.

.. literalinclude:: output/sawtooth_block_list_usage.out
   :language: console
   :linenos:

sawtooth block show
===================

The ``sawtooth block show`` subcommand queries the Sawtooth REST API
for a specific block in the current blockchain. It returns complete
information for this block in either YAML (default) or JSON format.
Using the ``--key`` option, it is possible to narrow the returned
information to just the value of a single key, either from the block,
or its header.

This subcommand requires the URL of the REST API (default:
``http://localhost:8080``), and can specify a username:password
combination when the REST API is behind a Basic Auth proxy.


.. literalinclude:: output/sawtooth_block_show_usage.out
   :language: console
   :linenos:

sawtooth config
===============

Sawtooth supports storing settings on-chain. The ``sawtooth config``
subcommands can be used to view the current proposals, create
proposals and vote on existing proposals, and produce setting values
that will be set in the genesis block.

.. literalinclude:: output/sawtooth_config_usage.out
   :language: console
   :linenos:

sawtooth config genesis
=======================

The ``sawtooth config genesis`` subcommand creates a Batch of settings
proposals that can be consumed by ``sawtooth admin genesis`` and used
during genesis block construction.

.. literalinclude:: output/sawtooth_config_genesis_usage.out
   :language: console
   :linenos:

sawtooth config proposal
========================

The Settings transaction processor (``sawtooth-settings``) supports a
simple voting mechanism for applying changes to on-change settings.
The ``sawtooth config proposal`` subcommands provide tools to view,
create and vote on proposed settings.

.. literalinclude:: output/sawtooth_config_proposal_usage.out
   :language: console
   :linenos:

sawtooth config proposal create
===============================

The ``sawtooth config proposal create`` subcommand creates proposals
for settings changes. The change may be applied immediately or after a
series of votes, depending on the vote threshold setting.

.. literalinclude:: output/sawtooth_config_proposal_create_usage.out
   :language: console
   :linenos:

sawtooth config proposal list
=============================

The ``sawtooth config proposal list`` subcommand displays the
currently proposed settings that are not yet active. This list of
proposals can be used to find proposals to vote on.

.. literalinclude:: output/sawtooth_config_proposal_list_usage.out
   :language: console
   :linenos:

sawtooth config proposal vote
=============================

The ``sawtooth config proposal vote`` subcommand votes for a specific
settings-change proposal. Use ``sawtooth config proposal list`` to
find the proposal id.

.. literalinclude:: output/sawtooth_config_proposal_vote_usage.out
   :language: console
   :linenos:

sawtooth config settings
========================

The ``sawtooth config settings`` subcommand displays the values of
currently active on-chain settings.

.. literalinclude:: output/sawtooth_config_settings_usage.out
   :language: console
   :linenos:

sawtooth config settings list
=============================

The ``sawtooth config proposal list`` subcommand displays the current
keys and values of on-chain settings.

.. literalinclude:: output/sawtooth_config_settings_list_usage.out
   :language: console
   :linenos:

sawtooth identity
=================

Sawtooth supports an identity system that provides an extensible role-
and policy-based system for defining permissions in a way which can be
used by other pieces of the architecture. This includes the existing
permissioning components for transactor key and validator key; in the
future, this feature may also be used by transaction family
implementations. The ``sawtooth identity`` subcommands can be used to
view the current roles and policy set in state, create new roles, and
new policies.

Note that only the public keys stored in the setting
sawtooth.identity.allowed_keys are allowed to submit identity
transactions. Use the ``sawtooth config`` commands to change this
setting.


.. literalinclude:: output/sawtooth_identity_usage.out
  :language: console
  :linenos:

sawtooth identity policy
========================

The ``sawtooth identity policy`` subcommands are used to display the
current policies stored in state and to create new policies.

.. literalinclude:: output/sawtooth_identity_policy_usage.out
   :language: console
   :linenos:

sawtooth identity policy create
===============================

The ``sawtooth identity policy create`` subcommand creates a new
policy that can then be set to a role. The policy should contain at
least one “rule” (``PERMIT_KEY`` or ``DENY_KEY``). Note that all
policies have an assumed last rule to deny all. This subcommand can
also be used to change the policy that is already set to a role
without having to also reset the role.

.. literalinclude:: output/sawtooth_identity_policy_create_usage.out
  :language: console
  :linenos:

sawtooth identity policy list
=============================

The ``sawtooth identity policy list`` subcommand lists the policies
that are currently set in state. This list can be used to figure out
which policy name should be set for a new role.

.. literalinclude:: output/sawtooth_identity_policy_list_usage.out
  :language: console
  :linenos:

sawtooth identity role
======================

The ``sawtooth identity role`` subcommands are used to list the
current roles stored in state and to create new roles.

.. literalinclude:: output/sawtooth_identity_role_usage.out
  :language: console
  :linenos:

sawtooth identity role create
=============================

The ``sawtooth identity role create`` subcommand creates a new role
that can be used to enforce permissions. The policy argument
identifies the policy that the role is restricted to. This policy must
already exist and be stored in state. Use ``sawtooth identity policy
list`` to display the existing policies. The role name should
reference an action that can be taken on the network. For example, the
role named ``transactor.transaction_signer`` controls who is allowed
to sign transactions.

.. literalinclude:: output/sawtooth_identity_role_create_usage.out
  :language: console
  :linenos:

sawtooth identity role list
===========================

The ``sawtooth identity role list`` subcommand displays the roles that
are currently set in state. This list can be used to determine which
permissions are being enforced on the network. The output includes
which policy the roles are set to.

By default, this information is displayed as a white-space delimited
table intended for display, but other plain-text formats (CSV, JSON,
and YAML) are available and can be piped into a file for further
processing.

.. literalinclude:: output/sawtooth_identity_role_list_usage.out
  :language: console
  :linenos:

sawtooth keygen
===============

The keygen subcommand generates a private key file and a public key
file so that users can sign Sawtooth transactions and batches. These
files are stored in the ``<key-dir>`` directory in ``<key_name>.priv``
and ``<key_dir>/<key_name>.pub``. By default, ``<key_dir>`` is
``~/.sawtooth`` and ``<key_name>`` is ``$USER``.

.. literalinclude:: output/sawtooth_keygen_usage.out
  :language: console
  :linenos:

sawtooth state
==============

The ``sawtooth state`` subcommands display information about the
entries in the current blockchain state.

.. literalinclude:: output/sawtooth_state_usage.out
   :language: console
   :linenos:

sawtooth state list
===================

The ``sawtooth state list`` subcommand queries the Sawtooth REST API
for a list of all state entries in the current blockchain state. It
returns the address of each entry, its size in bytes, and the
byte-encoded data it contains. It also returns the head block for
which this data is valid.

The state that is returned can be controlled using the subtree
argument to specify an address prefix as a filter or a block id to use
as the chain head.

By default, this information is displayed as a white-space delimited
table intended for display, but other plain-text formats (CSV, JSON,
and YAML) are available and can be piped into a file for further
processing.

This subcommand requires the URL of the REST API (default:
``http://localhost:8080``), and can specify a username:password
combination when the REST API is behind a Basic Auth proxy.

.. literalinclude:: output/sawtooth_state_list_usage.out
   :language: console
   :linenos:

sawtooth state show
===================

The ``sawtooth state show`` subcommand queries the Sawtooth REST API
for a specific state entry (address) in the current blockchain state.
It returns the data stored at this state address and the id of the
chain head for which this data is valid. This data is byte-encoded per
the logic of the transaction family that created it, and must be
decoded using that same logic.

This subcommand requires the URL of the REST API (default:
``http://localhost:8080``), and can specify a username:password
combination when the REST API is behind a Basic Auth proxy.

.. literalinclude:: output/sawtooth_state_show_usage.out
   :language: console
   :linenos:

sawtooth transaction
====================

The ``sawtooth transaction`` subcommands display information about the
transactions in the current blockchain.

.. literalinclude:: output/sawtooth_transaction_usage.out
   :language: console
   :linenos:

sawtooth transaction list
=========================

The ``sawtooth transaction list`` subcommand queries the Sawtooth REST
API (default: ``http://localhost:8080``) for a list of transactions in
the current blockchain. It returns the id of each transaction, its
family and version, the size of its payload, and the data in the
payload itself.

By default, this information is displayed as a white-space delimited
table intended for display, but other plain-text formats (CSV, JSON,
and YAML) are available and can be piped into a file for further
processing.

.. literalinclude:: output/sawtooth_transaction_list_usage.out
   :language: console
   :linenos:

sawtooth transaction show
=========================

The ``sawtooth transaction show`` subcommand queries the Sawtooth REST
API for a specific transaction in the current blockchain. It returns
complete information for this transaction in either YAML (default) or
JSON format. Using the --key option, it is possible to narrow the
returned information to just the value of a single key, either from
the transaction or its header.

This subcommand requires the URL of the REST API (default:
``http://localhost:8080``), and can specify a username:password
combination when the REST API is behind a Basic Auth proxy.

.. literalinclude:: output/sawtooth_transaction_show_usage.out
   :language: console
   :linenos:
