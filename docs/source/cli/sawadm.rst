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

.. _sawadm-reference-label:

******************
Sawtooth Admin CLI
******************

sawadm
======

The ``sawadm`` subcommands create validator keys during
initial configuration and help create the genesis block when
initializing a validator.

.. literalinclude:: output/sawadm_usage.out
   :language: console
   :linenos:

sawadm genesis
==============

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

.. literalinclude:: output/sawadm_genesis_usage.out
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

    > sawadm genesis config.batch mktplace.batch
    Generating /var/lib/sawtooth/genesis.batch

sawadm keygen
=============

The ``sawadm keygen`` command generates keys that the validator uses to
sign blocks. This system-wide key must be created during Sawtooth
configuration.

Validator keys are stored in the directory ``/etc/sawtooth/keys/``. By
default, the public-private key files are named ``validator.priv`` and
validator.pub. Use the <key-name> argument to specify a different file
name.

.. literalinclude:: output/sawadm_keygen_usage.out
   :language: console
   :linenos:
