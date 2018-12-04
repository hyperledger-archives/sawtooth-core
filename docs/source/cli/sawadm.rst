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

******
sawadm
******

The ``sawadm`` command is used for Sawtooth administration tasks.
The ``sawadm`` subcommands create validator keys during
initial configuration and help create the genesis block when
initializing a validator.

.. literalinclude:: output/sawadm_usage.out
   :language: console

sawadm genesis
==============

The ``sawadm genesis`` subcommand produces a file for use during the
initialization of a validator. A network requires an initial block (known as the
`genesis block`) whose signature will determine the blockchain ID. This initial
block is produced from a list of batches, which will be applied at
genesis time.

The optional argument `input_file` specifies one or more files containing
serialized ``BatchList`` protobuf messages to add to the genesis data. (Use a
space to separate multiple files.) If no input file is specified,
this command produces an empty genesis block.

The output is a file containing a serialized ``GenesisData`` protobuf message.
This file, when placed at `sawtooth_data`/``genesis.batch``, will trigger
the genesis process.

.. Note::

  The location of `sawtooth_data` depends on whether the
  environment variable ``SAWTOOTH_HOME`` is set. If it is, then
  `sawtooth_data` is located at ``SAWTOOTH_HOME/data``. If it is
  not, then `sawtooth_data` is located at ``/var/lib/sawtooth``.

When ``sawadm genesis`` runs, it displays the path and filename of the
target file where the serialized ``GenesisData`` is written. (Default:
`sawtooth_data`/``genesis.batch``.) For example:

.. code-block:: console

    $ sawadm genesis config.batch mktplace.batch
    Generating /var/lib/sawtooth/genesis.batch

Use ``--output`` `filename` to specify a different name for the target file.

.. literalinclude:: output/sawadm_genesis_usage.out
   :language: console


sawadm keygen
=============

The ``sawadm keygen`` subcommand generates keys that the validator uses to
sign blocks. This system-wide key must be created during Sawtooth
configuration.

Validator keys are stored in the directory ``/etc/sawtooth/keys/``. By
default, the public-private key files are named ``validator.priv`` and
validator.pub. Use the <key-name> argument to specify a different file
name.

.. literalinclude:: output/sawadm_keygen_usage.out
   :language: console

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
