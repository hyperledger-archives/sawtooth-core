Admin Genesis CLI Tool
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

Command
-------

.. code-block:: console

    sawtooth admin genesis [--output <filename>] [<input_batch_file1> [<input_batch_file2> ...]]

Arguments
^^^^^^^^^

Required:

None.

Optional:

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

