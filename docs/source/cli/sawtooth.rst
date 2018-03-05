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

********
sawtooth
********

The ``sawtooth`` command is the usual way to interact with validators or
validator networks.

This command has a multi-level structure. It starts with the base call to
``sawtooth``. Next is a top-level subcommand such as ``block`` or ``state``.
Each top-level subcommand has additional subcommands that specify the
operation to perform, such as ``list`` or ``create``.  The subcommands have
options and arguments that control their behavior. For example:

.. code-block:: console

  $ sawtooth state list --format csv

.. literalinclude:: output/sawtooth_usage.out
   :language: console

sawtooth batch
==============

The ``sawtooth batch`` subcommands display information about the
Batches in the current blockchain and submit Batches to the validator
via the REST API. A Batch is a group of interdependent transactions
that is the atomic unit of change in Sawtooth. For more information,
see “Transactions and Batches!”


.. literalinclude:: output/sawtooth_batch_usage.out
   :language: console

sawtooth batch list
===================

The ``sawtooth batch list`` subcommand queries the specified Sawtooth
REST API (default: ``http://localhost:8008``) for a list of Batches in
the current blockchain. It returns the id of each Batch, the public
key of each signer, and the number of transactions in each Batch.

By default, this information is displayed as a white-space delimited
table intended for display, but other plain-text formats (CSV, JSON,
and YAML) are available and can be piped into a file for further
processing.


.. literalinclude:: output/sawtooth_batch_list_usage.out
   :language: console

sawtooth batch show
===================

The ``sawtooth batch show`` subcommand queries the Sawtooth REST API
for a specific batch in the current blockchain. It returns complete
information for this batch in either YAML (default) or JSON format.
Use the ``--key`` option to narrow the returned
information to just the value of a single key, either from the batch
or its header.

This subcommand requires the URL of the REST API (default:
``http://localhost:8008``), and can specify a `username`:`password`
combination when the REST API is behind a Basic Auth proxy.


.. literalinclude:: output/sawtooth_batch_show_usage.out
   :language: console

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
``http://localhost:8008``), and can specify a `username`:`password`
combination when the REST API is behind a Basic Auth proxy.

.. literalinclude:: output/sawtooth_batch_status_usage.out
   :language: console

sawtooth batch submit
=====================

The ``sawtooth batch submit`` subcommand sends one or more Batches to
the Sawtooth REST API to be submitted to the validator. The input is a
binary file with a binary-encoded ``BatchList`` protobuf, which can
contain one or more batches with any number of transactions. The
``--wait`` option indicates that results should not be returned until
processing is complete, with an optional timeout specified in seconds.

This subcommand requires the URL of the REST API (default:
``http://localhost:8008``), and can specify a `username`:`password`
combination when the REST API is behind a Basic Auth proxy.


.. literalinclude:: output/sawtooth_batch_submit_usage.out
   :language: console

sawtooth block
==============

The ``sawtooth block`` subcommands display information about the
blocks in the current blockchain.

.. literalinclude:: output/sawtooth_block_usage.out
   :language: console

sawtooth block list
===================

The ``sawtooth block list`` subcommand queries the Sawtooth REST API
(default: ``http://localhost:8008``) for a list of blocks in the
current chain. Using the ``--count`` option, the number of blocks returned can
be configured. It returns the id and number of each block, the public key of
each signer, and the number of transactions and batches in each.

By default, this information is displayed as a white-space delimited
table intended for display, but other plain-text formats (CSV, JSON,
and YAML) are available and can be piped into a file for further
processing.

.. literalinclude:: output/sawtooth_block_list_usage.out
   :language: console

sawtooth block show
===================

The ``sawtooth block show`` subcommand queries the Sawtooth REST API
for a specific block in the current blockchain. It returns complete
information for this block in either YAML (default) or JSON format.
Using the ``--key`` option, it is possible to narrow the returned
information to just the value of a single key, either from the block,
or its header.

This subcommand requires the URL of the REST API (default:
``http://localhost:8008``), and can specify a `username`:`password`
combination when the REST API is behind a Basic Auth proxy.


.. literalinclude:: output/sawtooth_block_show_usage.out
   :language: console

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
transactions. Use the ``sawset`` commands to change this
setting.


.. literalinclude:: output/sawtooth_identity_usage.out
  :language: console

sawtooth identity policy
========================

The ``sawtooth identity policy`` subcommands are used to display the
current policies stored in state and to create new policies.

.. literalinclude:: output/sawtooth_identity_policy_usage.out
   :language: console

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

sawtooth identity policy list
=============================

The ``sawtooth identity policy list`` subcommand lists the policies
that are currently set in state. This list can be used to figure out
which policy name should be set for a new role.

.. literalinclude:: output/sawtooth_identity_policy_list_usage.out
  :language: console

sawtooth identity role
======================

The ``sawtooth identity role`` subcommands are used to list the
current roles stored in state and to create new roles.

.. literalinclude:: output/sawtooth_identity_role_usage.out
  :language: console

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

sawtooth keygen
===============

The ``sawtooth keygen`` subcommand generates a private key file and a public key
file so that users can sign Sawtooth transactions and batches. These
files are stored in the ``<key-dir>`` directory in ``<key_name>.priv``
and ``<key_dir>/<key_name>.pub``. By default, ``<key_dir>`` is
``~/.sawtooth`` and ``<key_name>`` is ``$USER``.

.. literalinclude:: output/sawtooth_keygen_usage.out
  :language: console

sawtooth peer
=============

The ``sawtooth peer`` subcommand displays the addresses of a specified
validator's peers.

.. literalinclude:: output/sawtooth_peer_usage.out
   :language: console

sawtooth peer list
==================

The ``sawtooth peer list`` subcommand displays the addresses of a
specified validator's peers.

This subcommand requires the URL of the REST API (default:
``http://localhost:8008``), and can specify a `username`:`password`
combination when the REST API is behind a Basic Auth proxy.

.. literalinclude:: output/sawtooth_peer_list_usage.out
   :language: console

sawtooth settings
=================

The ``sawtooth settings`` subcommand displays the values of currently
active on-chain settings.

.. literalinclude:: output/sawtooth_settings_usage.out
   :language: console

sawtooth settings list
======================

The ``sawtooth settings list`` subcommand displays the current keys
and values of on-chain settings.

.. literalinclude:: output/sawtooth_settings_list_usage.out
   :language: console

sawtooth state
==============

The ``sawtooth state`` subcommands display information about the
entries in the current blockchain state.

.. literalinclude:: output/sawtooth_state_usage.out
   :language: console

sawtooth state list
===================

The ``sawtooth state list`` subcommand queries the Sawtooth REST API
for a list of all state entries in the current blockchain state. This subcommand
returns the address of each entry, its size in bytes, and the
byte-encoded data it contains. It also returns the head block for
which this data is valid.

To control the state that is returned, use the ``subtree``
argument to specify an address prefix as a filter or a block id to use
as the chain head.

By default, this information is displayed as a white-space delimited
table intended for display, but other plain-text formats (CSV, JSON,
and YAML) are available and can be piped into a file for further
processing.

This subcommand requires the URL of the REST API (default:
``http://localhost:8008``), and can specify a `username`:`password`
combination when the REST API is behind a Basic Auth proxy.

.. literalinclude:: output/sawtooth_state_list_usage.out
   :language: console

sawtooth state show
===================

The ``sawtooth state show`` subcommand queries the Sawtooth REST API
for a specific state entry (address) in the current blockchain state.
It returns the data stored at this state address and the id of the
chain head for which this data is valid. This data is byte-encoded per
the logic of the transaction family that created it, and must be
decoded using that same logic.

This subcommand requires the URL of the REST API (default:
``http://localhost:8008``), and can specify a `username`:`password`
combination when the REST API is behind a Basic Auth proxy.

By default, the peers are displayed as a CSV string, but other
plain-text formats (JSON, and YAML) are available and can be piped
into a file for further processing.

.. literalinclude:: output/sawtooth_state_show_usage.out
   :language: console

sawtooth status
===============

The ``sawtooth status`` subcommands display information related to a
validator's status.

.. literalinclude:: output/sawtooth_status_usage.out
   :language: console

sawtooth status show
====================

The ``sawtooth status`` subcommand displays information related to a
validator's current status, including its public network endpoint and
its peers.

This subcommand requires the URL of the REST API (default:
``http://localhost:8008``), and can specify a `username`:`password`
combination when the REST API is behind a Basic Auth proxy.

.. literalinclude:: output/sawtooth_status_show_usage.out
   :language: console

sawtooth transaction
====================

The ``sawtooth transaction`` subcommands display information about the
transactions in the current blockchain.

.. literalinclude:: output/sawtooth_transaction_usage.out
   :language: console

sawtooth transaction list
=========================

The ``sawtooth transaction list`` subcommand queries the Sawtooth REST
API (default: ``http://localhost:8008``) for a list of transactions in
the current blockchain. It returns the id of each transaction, its
family and version, the size of its payload, and the data in the
payload itself.

By default, this information is displayed as a white-space delimited
table intended for display, but other plain-text formats (CSV, JSON,
and YAML) are available and can be piped into a file for further
processing.

.. literalinclude:: output/sawtooth_transaction_list_usage.out
   :language: console

sawtooth transaction show
=========================

The ``sawtooth transaction show`` subcommand queries the Sawtooth REST
API for a specific transaction in the current blockchain. It returns
complete information for this transaction in either YAML (default) or
JSON format. Use the ``--key`` option to narrow the
returned information to just the value of a single key, either from
the transaction or its header.

This subcommand requires the URL of the REST API (default:
``http://localhost:8008``), and can specify a `username`:`password`
combination when the REST API is behind a Basic Auth proxy.

.. literalinclude:: output/sawtooth_transaction_show_usage.out
   :language: console

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
