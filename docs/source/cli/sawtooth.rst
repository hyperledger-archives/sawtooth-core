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

.. literalinclude:: output/sawtooth_usage.out
   :language: console
   :linenos:

sawtooth admin
==============

.. literalinclude:: output/sawtooth_admin_usage.out
   :language: console
   :linenos:

sawtooth admin genesis
======================

Overview
--------

The genesis CLI tool produces a file for use during initialization of a
validator.  A network requires an initial block (known as the genesis block)
whose signature will determine the block chain id.  This initial block is
produced from a list of batches, which will be applied at genesis time.  The
input to the command is a set of zero or more files containing serialized
``BatchList`` protobuf messages. The output is a file containing a serialized
``GenesisData`` protobuf message.  This file, when placed at
``<sawtooth_data>/genesis.batch``, will trigger the genesis process.

The location ``sawtooth_data`` depends on whether or not the environment
variable ``SAWTOOTH_HOME`` is set.  If it is, then ``sawtooth_data`` is located
at ``<SAWTOOTH_HOME>/data``.  If it is not, then ``sawtooth_data`` is located
at ``/var/lib/sawtooth``.

Usage
-----

.. literalinclude:: output/sawtooth_admin_genesis_usage.out
   :language: console
   :linenos:

Arguments
^^^^^^^^^

- ``input_batch_file`` - a repeated list of files containing a serialized
  ``BatchList`` message.  This may be empty, which will produce an empty
  genesis block.

- ``--output <filename>`` - a target file where the serialized ``GenesisData``
  will be written. Defaults to ``<sawtooth_data>/genesis.batch``.

Output
^^^^^^

The output of the command displays a message where the output ``GenesisData`` is
written.

Example
^^^^^^^

.. code-block:: console

    > sawtooth admin genesis config.batch mktplace.batch
    Generating /var/lib/sawtooth/genesis.batch

sawtooth admin keygen
=====================

.. literalinclude:: output/sawtooth_admin_keygen_usage.out
   :language: console
   :linenos:

sawtooth batch
==============

.. literalinclude:: output/sawtooth_batch_usage.out
   :language: console
   :linenos:

sawtooth batch list
===================

.. literalinclude:: output/sawtooth_batch_list_usage.out
   :language: console
   :linenos:

sawtooth batch show
===================

.. literalinclude:: output/sawtooth_batch_show_usage.out
   :language: console
   :linenos:

sawtooth batch status
=====================

.. literalinclude:: output/sawtooth_batch_status_usage.out
   :language: console
   :linenos:

sawtooth batch submit
=====================

.. literalinclude:: output/sawtooth_batch_submit_usage.out
   :language: console
   :linenos:

sawtooth block
==============

.. literalinclude:: output/sawtooth_block_usage.out
   :language: console
   :linenos:

sawtooth block list
===================

.. literalinclude:: output/sawtooth_block_list_usage.out
   :language: console
   :linenos:

sawtooth block show
===================

.. literalinclude:: output/sawtooth_block_show_usage.out
   :language: console
   :linenos:

sawtooth config
===============

.. literalinclude:: output/sawtooth_config_usage.out
   :language: console
   :linenos:

sawtooth config genesis
=======================

.. literalinclude:: output/sawtooth_config_genesis_usage.out
   :language: console
   :linenos:

sawtooth config proposal
========================

.. literalinclude:: output/sawtooth_config_proposal_usage.out
   :language: console
   :linenos:

sawtooth config proposal create
===============================

.. literalinclude:: output/sawtooth_config_proposal_create_usage.out
   :language: console
   :linenos:

sawtooth config proposal list
=============================

.. literalinclude:: output/sawtooth_config_proposal_list_usage.out
   :language: console
   :linenos:

sawtooth config proposal vote
=============================

.. literalinclude:: output/sawtooth_config_proposal_vote_usage.out
   :language: console
   :linenos:

sawtooth config settings
========================

.. literalinclude:: output/sawtooth_config_settings_usage.out
   :language: console
   :linenos:

sawtooth config settings list
=============================

.. literalinclude:: output/sawtooth_config_settings_list_usage.out
   :language: console
   :linenos:

sawtooth state
==============

.. literalinclude:: output/sawtooth_state_usage.out
   :language: console
   :linenos:

sawtooth state list
===================

.. literalinclude:: output/sawtooth_state_list_usage.out
   :language: console
   :linenos:

sawtooth state show
===================

.. literalinclude:: output/sawtooth_state_show_usage.out
   :language: console
   :linenos:

sawtooth transaction
====================

.. literalinclude:: output/sawtooth_transaction_usage.out
   :language: console
   :linenos:

sawtooth transaction list
=========================

.. literalinclude:: output/sawtooth_transaction_list_usage.out
   :language: console
   :linenos:

sawtooth transaction show
=========================

.. literalinclude:: output/sawtooth_transaction_show_usage.out
   :language: console
   :linenos:

