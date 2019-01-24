*********************************************
Using Ubuntu for Your Development Environment
*********************************************

This procedure explains how to set up Hyperledger Sawtooth for application
development on Ubuntu 16.04. It shows you how to install Sawtooth on Ubuntu,
then walks you through the following tasks:

 * Generating a user key
 * Creating the genesis block
 * Generating a root key
 * Starting the components: validator, consensus engine, REST API, and
   transaction processors
 * Checking the status of the REST API
 * Using Sawtooth commands to submit transactions, display block data, and view
   global state
 * Examining Sawtooth logs
 * Stopping Sawtooth and resetting the development environment

After completing this procedure, you will have the application development
environment that is required for the other tutorials in this guide. The next
tutorial introduces the XO transaction family by using the ``xo`` client
commands to play a game of tic-tac-toe. The final set of tutorials describe how
to use an SDK to create a transaction family that implements your application's
business logic.


About the Application Development Environment
=============================================

The Ubuntu application development environment is a single validator node that
is running a validator, a REST API, and three transaction processors. This
environment uses Developer mode (dev mode) consensus and serial transaction
processing.

.. figure:: ../images/appdev-environment-one-node-3TPs.*
   :width: 100%
   :align: center
   :alt: Ubuntu: Sawtooth application environment with one node

This environment introduces basic Sawtooth functionality with the
`IntegerKey <../transaction_family_specifications/integerkey_transaction_family>`_
and
`Settings <../transaction_family_specifications/settings_transaction_family>`_
transaction processors for the business logic and Sawtooth commands as a client.
It also includes the
`XO <../transaction_family_specifications/xo_transaction_family>`_
transaction processor, which is used in later tutorials.

The IntegerKey and XO families are simple examples of a transaction family, but
Settings is a reference implementation. In a production environment, you should
always run a transaction processor that supports the Settings transaction
family.

In this procedure, you will open seven terminal windows on your host system: one
for each Sawtooth component and one to use for client commands.

.. note::

   This procedure starts the validator first, then the REST API, followed by
   the transaction processors. However, the start-up order is flexible. For
   example, you can start the transaction processors before starting the
   validator.


Prerequisites
=============

This Sawtooth development environment requires Ubuntu 16.04.


Step 1: Install Sawtooth
========================

The Sawtooth package repositories provide two types of Ubuntu packages:
stable or nightly.  We recommend using the stable repository.


#. Open a terminal window on your host system.
   From this point on, this procedure refers to this window as the "validator
   terminal window".
   In the following examples, the prompt ``user@validator$``
   shows the commands that must run in this window.

#. Choose either the stable repository or the nightly repository.

   * To add the stable repository, run these commands:

     .. code-block:: console

       user@validator$ sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 8AA7AF1F1091A5FD
       user@validator$ sudo add-apt-repository 'deb [arch=amd64] http://repo.sawtooth.me/ubuntu/bumper/stable xenial universe'
       user@validator$ sudo apt-get update

   * To use the nightly repository, run the following commands:

     .. Caution::

        Nightly builds have not gone through long-running network testing and
        could be out of sync with the documentation.  We really do recommend the
        stable repository.

     .. code-block:: console

        user@validator$ sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 44FC67F19B2466EA
        user@validator$ sudo apt-add-repository "deb http://repo.sawtooth.me/ubuntu/nightly xenial universe"
        user@validator$ sudo apt-get update

#. Install the Sawtooth packages. Sawtooth consists of several Ubuntu packages
   that can be installed together using the ``sawtooth`` meta-package. Run the
   following command:

   .. code-block:: console

      user@validator$ sudo apt-get install -y sawtooth

#. Install the Sawtooth Devmode consensus engine package. Run the following
   command:

   .. code-block:: console

       user@validator$ sudo apt-get install sawtooth-devmode-engine-rust

#. Any time after installation, you can view the installed Sawtooth packages
   with the following command:

   .. code-block:: console

      user@validator$ dpkg -l '*sawtooth*'


.. _generate-user-key-ubuntu:

Step 2: Generate a User Key
===========================

Generate your user key for Sawtooth, using the same terminal window as the
previous step.

   .. code-block:: console

      user@validator$ sawtooth keygen
      writing file: /home/yourname/.sawtooth/keys/yourname.priv
      writing file: /home/yourname/.sawtooth/keys/yourname.pub


.. _create-genesis-block-ubuntu-label:

Step 3: Create the Genesis Block
================================

Because this is a new network, you must create a genesis block (the first block
on the distributed ledger). This step is done only for the first validator node
on the network. Validator nodes that join an existing network do not create
a genesis block.

The genesis block contains initial values that are necessary when a Sawtooth
distributed ledger is created and used for the first time, including the keys
for users who are authorized to set and change configuration settings.

Use the same terminal window as the previous step.

#. Create a settings proposal (as a batch of transactions) that authorizes you
   to set and change configuration settings. By default (if no options are
   specified), the ``sawset genesis`` command uses the key of the current user
   (you).

   .. code-block:: console

      user@validator$ sawset genesis
      Generated config-genesis.batch

    This settings proposal will change authorized keys in the setting
    ``sawtooth.settings.vote.authorized_keys``. The change will take effect
    after the validator and Settings transaction processor have started.

#. Run the following command:

   .. code-block:: console

     user@validator$ sudo -u sawtooth sawadm genesis config-genesis.batch
     Processing config-genesis.batch...
     Generating /var/lib/sawtooth/genesis.batch

   .. note::

      The ``-u sawtooth`` option refers to the sawtooth user,
      not the sawtooth command.


.. _generate-root-key-ubuntu:

Step 4: Generate the Root Key for the Validator
===============================================

Generate the key for the validator, which runs as root. Use the same terminal
window as the previous step.

.. code-block:: console

   user@validator$ sudo sawadm keygen
   writing file: /etc/sawtooth/keys/validator.priv
   writing file: /etc/sawtooth/keys/validator.pub


.. _start-validator-ubuntu-label:

Step 5: Start the Validator
===========================

Use the same terminal window as the previous step.

#. Start a validator that listens locally on the default ports.

   .. code-block:: console

      user@validator$ sudo -u sawtooth sawtooth-validator -vv

   .. note::

      See :doc:`../cli/sawtooth-validator` in the CLI Command Reference for
      information on the ``sawtooth-validator`` options.

   The validator terminal window displays verbose log messages. The output will
   be similar to this truncated example:

   .. code-block:: console

      [2018-03-14 15:53:34.909 INFO     cli] sawtooth-validator (Hyperledger Sawtooth) version 1.0.1
      [2018-03-14 15:53:34.909 INFO     path] Skipping path loading from non-existent config file: /etc/sawtooth/path.toml
      [2018-03-14 15:53:34.910 INFO     validator] Skipping validator config loading from non-existent config file: /etc/sawtooth/validator.toml
      [2018-03-14 15:53:34.911 INFO     keys] Loading signing key: /etc/sawtooth/keys/validator.priv
      [2018-03-14 15:53:34.912 INFO     cli] config [path]: config_dir = "/etc/sawtooth"; config [path]: key_dir = "/etc/sawtooth/keys"; config [path]: data_dir = "/var/lib/sawtooth"; config [path]: log_dir = "/var/log/sawtooth"; config [path]: policy_dir = "/etc/sawtooth/policy"
      [2018-03-14 15:53:34.913 WARNING  cli] Network key pair is not configured, Network communications between validators will not be authenticated or encrypted.
      [2018-03-14 15:53:34.914 DEBUG    core] global state database file is /var/lib/sawtooth/merkle-00.lmdb
      ...
      [2018-03-14 15:53:34.929 DEBUG    genesis] genesis_batch_file: /var/lib/sawtooth/genesis.batch
      [2018-03-14 15:53:34.930 DEBUG    genesis] block_chain_id: not yet specified
      [2018-03-14 15:53:34.931 INFO     genesis] Producing genesis block from /var/lib/sawtooth/genesis.batch
      [2018-03-14 15:53:34.932 DEBUG    genesis] Adding 1 batches
      [2018-03-14 15:53:34.934 DEBUG    executor] no transaction processors registered for processor type sawtooth_settings: 1.0
      [2018-03-14 15:53:34.936 INFO     executor] Waiting for transaction processor (sawtooth_settings, 1.0)

   Note that the validator is waiting for the Settings transaction processor
   (``sawtooth_settings``) to start.

The validator terminal window will continue to display log messages as you
complete this procedure.

.. note::

   If you want to stop the validator, enter CTRL-c in the validator terminal
   window. For more information, see :ref:`stop-sawtooth-ubuntu-label`.


.. _start-devmode-consensus-label:

Step 6: Start the Devmode Consensus Engine
==========================================

#. Open a new terminal window (the consensus terminal window). In this procedure,
   the prompt ``user@consensus$`` shows the commands that should be run in this
   window.

#. Run the following command to start the Devmode consensus engine that decides what block to add to a blockchain.

   .. code-block:: console

       user@consensus$ sudo -u sawtooth devmode-engine-rust -vv --connect tcp://localhost:5050

   The consensus terminal window displays verbose log messages showing the
   Devmode engine connecting to and registering with the validator.
   The output will be similar to this example:

   .. code-block:: console

      [2019-01-09 11:45:07.807 INFO     handlers] Consensus engine registered: Devmode 0.1
      DEBUG | devmode_rust::engine | Min: 0 -- Max: 0
      INFO  | devmode_rust::engine | Wait time: 0
      DEBUG | devmode_rust::engine | Initializing block


.. _start-rest-api-label:

Step 7: Start the REST API
==========================

The REST API allows you to configure a running validator, submit batches, and
query the state of the distributed ledger.

#. Open a new terminal window (the rest-api terminal window). In this procedure,
   the prompt ``user@rest-api$`` shows the commands that should be run in this
   window.

#. Run the following command to start the REST API and connect to the local
   validator.

   .. code-block:: console

      user@rest-api$ sudo -u sawtooth sawtooth-rest-api -v

   .. note::

      See :doc:`../cli/sawtooth-rest-api` in the CLI Command Reference for
      information on the ``sawtooth-rest-api`` options.

   The output is similar to this example:

   .. code-block:: console

      Connecting to tcp://localhost:4004
      [2018-03-14 15:55:29.509 INFO     rest_api] Creating handlers for validator at tcp://localhost:4004
      [2018-03-14 15:55:29.511 INFO     rest_api] Starting REST API on 127.0.0.1:8008
      ======== Running on http://127.0.0.1:8008 ========
      (Press CTRL+C to quit)

The rest-api terminal window continues display log messages as you complete this
procedure.


.. _start-tps-label:

Step 8: Start the Transaction Processors
========================================

In this step, you will open a new terminal window for each transaction
processor.

1. Start the Settings transaction processor, ``settings-tp``.

   a. Open a new terminal window (the settings terminal window). The prompt
      ``user@settings-tp$`` shows the commands that should be run in this
      window.

   #. Run the following command:

      .. code-block:: console

         user@settings$ sudo -u sawtooth settings-tp -v

      .. note::

         See :doc:`../cli/settings-tp` in the CLI Command Reference for
         information on the ``settings-tp`` options.

   #. Check the validator terminal window to confirm that the transaction
      processor has registered with the validator, as shown in this example
      log message:

      .. code-block:: console

         [2018-03-14 16:00:17.223 INFO     processor_handlers] registered transaction processor: connection_id=eca3a9ad0ff1cdbc29e449cc61af4936bfcaf0e064952dd56615bc00bb9df64c4b01209d39ae062c555d3ddc5e3a9903f1a9e2d0fd2cdd47a9559ae3a78936ed, family=sawtooth_settings, version=1.0, namespaces=['000000']

   #. Open a new terminal window (the client terminal window). In this
      procedure, the prompt ``user@client$`` shows the commands that should be
      run in this window.

   #. At this point, you can see the authorized keys setting that was proposed
      in :ref:`create-genesis-block-ubuntu-label`.
      Run the following command in the client terminal window:

      .. code-block:: console

         user@client$ sawtooth settings list
         sawtooth.settings.vote.authorized_keys: 0276023d4f7323103db8d8683a4b7bc1eae1f66fbbf79c20a51185f589e2d304ce

   The ``settings-tp`` transaction processor continues to run and to display log
   messages in its terminal window.

#. Start the IntegerKey transaction processor, ``intkey-tp-python``.

   a. Open a new terminal window (the intkey terminal window). The prompt
      ``user@intkey$`` shows the commands that should be run in this window.

   #. Run the following command:

      .. code-block:: console

         user@intkey$ sudo -u sawtooth intkey-tp-python -v
         [23:07:57 INFO    core] register attempt: OK

      .. note::

         For information on the ``intkey-tp-python`` options, run the command
         ``intkey-tp-python --help``.

   #. Check the validator terminal window to confirm that the transaction
      processor has registered with the validator.  A successful registration
      event produces the following output:

      .. code-block:: console

         [2018-03-14 15:56:35.255 INFO     processor_handlers] registered transaction processor: connection_id=94d1aedfc2ba0575a0e4b4f06be7ff7875703f18817027b463b3772ce2b963adb9902f7ed0bafa50201e6845015f65bac814302bdafbcda6e6698fe1733b9411, family=intkey, version=1.0, namespaces=['1cf126']

   The ``intkey-tp-python`` transaction processor continues to run and to
   display log messages in its terminal window.

#. (Optional) Start the XO transaction processor, ``xo-tp-python``. This
   transaction processor will be used in a later tutorial.

   a. Open a new terminal window (the xo terminal window). The prompt
      ``user@xo$`` shows the commands that should be run in this window.

   #. Run the following command:

      .. code-block:: console

         user@xo$ sudo -u sawtooth xo-tp-python -v

      .. note::

         For information on the ``xo-tp-python`` options, run the command
         ``xo-tp-python --help``.

   #. Check the validator terminal window to confirm that the transaction
      processor has registered with the validator.

      .. code-block:: console

         [2018-03-14 16:04:18.706 INFO     processor_handlers] registered transaction processor: connection_id=c885e99a11724e04e7da4ee426ee00d4af2cb54b67bf2fbd2f57e862bf28fa2c759a0d0978573782369659124797cc6f38d41bfde2469fe69e7e48dc1fadf5a9, family=xo, version=1.0, namespaces=['5b7349']

   The ``xo-tp-python`` transaction processor continues to run and to display
   log messages in its terminal window.


.. _confirm-rest-api-ubuntu-label:

Step 9: Confirm Connectivity to the REST API
============================================

#. Run the following command in the client terminal window:

   .. code-block:: console

      user@client$ ps aux | grep [s]awtooth-rest-api
      sawtooth  2829  0.0  0.3  55756  3980 pts/0    S+   19:36   0:00 sudo -u sawtooth sawtooth-rest-api -v
      sawtooth  2830  0.0  3.6 221164 37520 pts/0    Sl+  19:36   0:00 /usr/bin/python3 /usr/bin/sawtooth-rest-api -v

#. If necessary, restart the REST API (see :ref:`start-rest-api-label`).


Step 10: Use Sawtooth Commands as a Client
==========================================

Sawtooth includes commands that act as a client application. This step describes
how to use the ``intkey`` and ``sawtooth`` commands to create and submit
transactions, display blockchain and block data, and examine global state data.

.. note::

   Use the ``--help`` option with any Sawtooth command to display the available
   options and subcommands.

Continue to use the client terminal window to run the commands in this step.

Creating and Submitting Transactions with intkey
------------------------------------------------

The ``intkey`` command creates sample IntegerKey transactions for testing
purposes.

#. Use ``intkey create_batch`` to prepare batches of transactions that set
   a few keys to random values, then randomly increment and decrement those
   values. These batches are saved locally in the file ``batches.intkey``.

   .. code-block:: console

      user@client$ intkey create_batch --count 10 --key-count 5
      Writing to batches.intkey...

#. Use ``intkey load`` to submit the batches to the validator.

   .. code-block:: console

      user@client$ intkey load -f batches.intkey
      batches: 11 batch/sec: 141.7800162868952

#. The validator terminal window displays many log messages showing that the
   validator is handling the submitted transactions and processing blocks, as in
   this truncated example:

   .. code-block:: console

      ...
      78c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a)^[[0m
      [2018-03-14 16:24:49.621 INFO     chain] Starting block validation of : 60c0c348a00cde622a3664d6d4fb949736b78f8bcb6b77bd0300cdc7675ca9d4116ee23ec18c7cfee5978c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a)
      [2018-03-14 16:24:49.646 INFO     chain] Comparing current chain head 'f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a (block_num:12, state:c30ed78dde19d9ff58587a8bdd4aa435e09212cd1fee3e95d88faafe44f207cc, previous_block_id:dc98ce9029e6e3527bca18060cbb1325b545054b1589f2df7bf200fb0a09d0572491a3837dea1baf2981f5a960bd108f198806c974efcb3b69d2712809cc6065)' against new block '60c0c348a00cde622a3664d6d4fb949736b78f8bcb6b77bd0300cdc7675ca9d4116ee23ec18c7cfee5978c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a)'
      [2018-03-14 16:24:49.647 INFO     chain] Fork comparison at height 13 is between - and 60c0c348
      [2018-03-14 16:24:49.647 INFO     chain] Chain head updated to: 60c0c348a00cde622a3664d6d4fb949736b78f8bcb6b77bd0300cdc7675ca9d4116ee23ec18c7cfee5978c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a)
      [2018-03-14 16:24:49.648 INFO     publisher] Now building on top of block: 60c0c348a00cde622a3664d6d4fb949736b78f8bcb6b77bd0300cdc7675ca9d4116ee23ec18c7cfee5978c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a)
      [2018-03-14 16:24:49.649 DEBUG    chain] Verify descendant blocks: 60c0c348a00cde622a3664d6d4fb949736b78f8bcb6b77bd0300cdc7675ca9d4116ee23ec18c7cfee5978c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a) ([])
      [2018-03-14 16:24:49.651 INFO     chain] Finished block validation of: 60c0c348a00cde622a3664d6d4fb949736b78f8bcb6b77bd0300cdc7675ca9d4116ee23ec18c7cfee5978c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a)

#. The rest-api terminal window displays a log message as it communicates with
   the intkey transaction processor.

      .. code-block:: console

         [2018-03-14 16:24:49.587 INFO     helpers] POST /batches HTTP/1.1: 202 status, 1639 size, in 0.030922 s

#. You can also look at the Sawtooth log files to see what happened. Use the
   following command to display the last 10 entries in the intkey log file,
   which show that values have been changed.

      .. code-block:: console

         user@client$ sudo bash -c "tail -10 /var/log/sawtooth/intkey-*-debug.log"
         [2018-03-14 16:24:49.587 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
         [2018-03-14 16:24:49.588 [MainThread] handler DEBUG] incrementing "MvRznE" by 1
         [2018-03-14 16:24:49.624 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
         [2018-03-14 16:24:49.625 [MainThread] handler DEBUG] incrementing "iJWCRq" by 5
         [2018-03-14 16:24:49.629 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
         [2018-03-14 16:24:49.630 [MainThread] handler DEBUG] incrementing "vJJL1N" by 8
         [2018-03-14 16:24:49.634 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
         [2018-03-14 16:24:49.636 [MainThread] handler DEBUG] incrementing "vsTbBo" by 4
         [2018-03-14 16:24:49.639 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
         [2018-03-14 16:24:49.641 [MainThread] handler DEBUG] incrementing "MvRznE" by 1

      .. note::

         The log file names for the transaction processors contain a random
         string that is unique for each instance of the transaction processor.
         For more information, see :ref:`examine-logs-ubuntu-label`.

Submitting Transactions with sawtooth batch submit
--------------------------------------------------

In the example above, the ``intkey create_batch`` command created the file
``batches.intkey``.  Rather than using ``intkey load`` to submit these
transactions, you could use ``sawtooth batch submit`` to submit them.

#. As before, create a batch of transactions.

   .. code-block:: console

      user@client$ intkey create_batch --count 10 --key-count 5
      Writing to batches.intkey...

#. Submit the batch file with the following command:

   .. code-block:: console

      user@client$ sawtooth batch submit -f batches.intkey
      batches: 11,  batch/sec: 216.80369536716367

Viewing Blockchain and Block Data with sawtooth block
-----------------------------------------------------

The ``sawtooth block`` command displays information about the blocks stored on
the blockchain.

#. Use ``sawtooth block list`` to display the list of blocks stored in state.

   .. code-block:: console

      user@client$ sawtooth block list

   The output includes the block ID, as in this example:

   .. code-block:: console

      NUM  BLOCK_ID                                                                                                                          BATS  TXNS  SIGNER
      61   9566426220751691b7463e3c1ec1d8c4f158c98e89722672721d457182cb3b3d48e734ddceabf706b41fc3e1f8d739451f7d70bd5a8708bc4085b6fb33b40bef  1     4     020d21...
      60   309c0707b95609d4ebc2fad0afd590ec40db41680a3edbbeb0875720ed59f4d775e1160a2c6cbe2e9ccb34c4671f4cd7db1e5ed35a2ed9a0f2a2c99aa981f83c  1     5     020d21...
      59   e0c6c29a9f3d1436e4837c96587ae3fa60274991efa9d0c9000d53694cd2a0841914b2f362aa05c2385126288f060f524bac3a05850edb1ac1c86f0c237afdba  1     3     020d21...
      58   8c67a1ec68bfdd5b07bb02919019b917ed26dbc6ec0fc3de15d539538bd30f8a1aa58795578970d2e607cd63cf1f5ef921476cbc0564cbe37469e5e50b72ecf2  1     3     020d21...
      57   879c6cb43e244fb7c1676cf5d9e51ace25ad8e670f37e81b81e5d9e133aebba80282913677821c14fe2ccb2aae631229bdd044222e6a8927f4f5dabb6d62c409  1     4     020d21...
      ...
      5    dce0921531472a8f9840e256c585917dfc22b78c5045a3416ed76faf57232b065b8be5a34023e8a8cdab74ab24cf029a5c1051f742b9b5280b8edab5a80d805d  2     4     020d21...
      4    0007380e98fc6d63de1d47261b83186bce9722023f2e6ab6849916766e9be29f4903d76a642dfc27579b8a8bf9adba5f077c1f1457b2cad8f52a28d7079333a6  1     8     020d21...
      3    515c827b9e84c22c24838130d4e0f6af07ab271c138a61c555a830c4118a75815f54340ef3f04de009c94c3531f3202690708cf16fcfee04303972cb91e3b87a  1     10    020d21...
      2    9067bcb093bb095ca436d8868914ecf2630215d36bfd78b0b167554c544b9842193dd309f135e6959a664fe34b06b4f16a297528249550821cda9273291ebe70  1     5     020d21...
      1    3ab950b2cd370f26e188d95ee97268965732768080ca1adb71759e3c1f22d1ea19945b48fc81f5f821387fde355349f87096da00a4e356408b630ab80576d3ae  1     5     020d21...
      0    51a704e1a83086372a3c0823533881ffac9479995289902a311fd5d99ff6a32216cd1fb9883a421449c943cad8604ce1447b0f6080c8892e334b14dc082f91d3  1     1     020d21...

#. From the output generated by ``sawtooth block list``, copy the ID of a block
   you want to view, then paste it in place of ``{BLOCK_ID}`` in the following
   command:

   .. code-block:: console

      user@client$ sawtooth block show {BLOCK_ID}

   The output of this command can be quite long, because it includes all data
   stored under that block. This is a truncated example:

   .. code-block:: console

      batches:
      - header:
          signer_public_key: 0276023d4f7323103db8d8683a4b7bc1eae1f66fbbf79c20a51185f589e2d304ce
          transaction_ids:
          - 24b168aaf5ea4a76a6c316924a1c26df0878908682ea5740dd70814e7c400d56354dee788191be8e28393c70398906fb467fac8db6279e90e4e61619589d42bf
        header_signature: a93731646a8fd2bce03b3a17bc2cb3192d8597da93ce735950dccbf0e3cf0b005468fadb94732e013be0bc2afb320be159b452cf835b35870db5fa953220fb35
        transactions:
        - header:
            batcher_public_key: 0276023d4f7323103db8d8683a4b7bc1eae1f66fbbf79c20a51185f589e2d304ce
            dependencies: []
            family_name: sawtooth_settings
            family_version: '1.0'
      ...
      header:
        batch_ids:
        - a93731646a8fd2bce03b3a17bc2cb3192d8597da93ce735950dccbf0e3cf0b005468fadb94732e013be0bc2afb320be159b452cf835b35870db5fa953220fb35
        block_num: 3
        consensus: RGV2bW9kZQ==
        previous_block_id: 042f08e1ff49bbf16914a53dc9056fb6e522ca0e2cff872547eac9555c1de2a6200e67fb9daae6dfb90f02bef6a9088e94e5bdece04f622bce67ccecd678d56e
        signer_public_key: 033fbed13b51eafaca8d1a27abc0d4daf14aab8c0cbc1bb4735c01ff80d6581c52
        state_root_hash: 5d5ea37cbbf8fe793b6ea4c1ba6738f5eee8fc4c73cdca797736f5afeb41fbef
      header_signature: ff4f6705bf57e2a1498dc1b649cc9b6a4da2cc8367f1b70c02bc6e7f648a28b53b5f6ad7c2aa639673d873959f5d3fcc11129858ecfcb4d22c79b6845f96c5e3

Viewing State Data with sawtooth state
--------------------------------------

The ``sawtooth state`` command lets you display state data. Sawtooth stores
state data in a :term:`Merkle-Radix tree`; for more information, see
:doc:`../architecture/global_state`.

#. Use ``sawtooth state list`` to list the nodes (addresses) in state.

   .. code-block:: console

      user@client$ sawtooth state list

   The output will be similar to this truncated example:

   .. code-block:: console

      ADDRESS                                                                                                                                SIZE DATA
      1cf126ddb507c936e4ee2ed07aa253c2f4e7487af3a0425f0dc7321f94be02950a081ab7058bf046c788dbaf0f10a980763e023cde0ee282585b9855e6e5f3715bf1fe 11   b'\xa1fcCTdcH\x...
      1cf1260cd1c2492b6e700d5ef65f136051251502e5d4579827dc303f7ed76ddb7185a19be0c6443503594c3734141d2bdcf5748a2d8c75541a8e568bae063983ea27b9 11   b'\xa1frdLONu\x...
      1cf126ed7d0ac4f755be5dd040e2dfcd71c616e697943f542682a2feb14d5f146538c643b19bcfc8c4554c9012e56209f94efe580b6a94fb326be9bf5bc9e177d6af52 11   b'\xa1fAUZZqk\x...
      1cf126c46ff13fcd55713bcfcf7b66eba515a51965e9afa8b4ff3743dc6713f4c40b4254df1a2265d64d58afa14a0051d3e38999704f6e25c80bed29ef9b80aee15c65 11   b'\xa1fLvUYLk\x...
      1cf126c4b1b09ebf28775b4923e5273c4c01ba89b961e6a9984632612ec9b5af82a0f7c8fc1a44b9ae33bb88f4ed39b590d4774dc43c04c9a9bd89654bbee68c8166f0 13   b'\xa1fXHonWY\x...
      1cf126e924a506fb2c4bb8d167d20f07d653de2447df2754de9eb61826176c7896205a17e363e457c36ccd2b7c124516a9b573d9a6142f031499b18c127df47798131a 13   b'\xa1foWZXEz\x...
      1cf126c295a476acf935cd65909ed5ead2ec0168f3ee761dc6f37ea9558fc4e32b71504bf0ad56342a6671db82cb8682d64689838731da34c157fa045c236c97f1dd80 13   b'\xa1fadKGve\x...

#. Use ``sawtooth state show`` to view state data at a specific address (a node
   in the Merkle-Radix database). Copy the address from the output of
   ``sawtooth state list``, then paste it in place of ``{STATE_ADDRESS}`` in
   the following command:

   .. code-block:: console

      user@client$ sawtooth state show {STATE_ADDRESS}

   The output shows the bytes stored at that address and the block ID of the
   "chain head" that the current state is tied to, as in this example:

   .. code-block:: console

      DATA: "b'\xa1fcCTdcH\x192B'"
      HEAD: "0c4364c6d5181282a1c7653038ec9515cb0530c6bfcb46f16e79b77cb524491676638339e8ff8e3cc57155c6d920e6a4d1f53947a31dc02908bcf68a91315ad5"


.. _examine-logs-ubuntu-label:

Step 11: Examine Sawtooth Logs
==============================

By default, Sawtooth logs are stored in the directory ``/var/log/sawtooth``.
Each component (validator, REST API, and transaction processors) has both a
debug log and an error log. This example shows the log files for this
application development environment:

  .. code-block:: console

     user@client$ sudo ls -1 /var/log/sawtooth
     identity-f5c42a08548c4ffa-debug.log
     identity-f5c42a08548c4ffa-error.log
     intkey-ae98c3726f9743c4-debug.log
     intkey-ae98c3726f9743c4-error.log
     rest_api-debug.log
     rest_api-error.log
     settings-6d591c44915b465c-debug.log
     settings-6d591c44915b465c-error.log
     validator-debug.log
     validator-error.log
     xo-9b8b55265ca0d546-error.log
     xo-9b8b55265ca0d546-debug.log

.. note::

   For the transaction processors, the log file names contain a random string to
   make the names unique. This string changes for each instance of a transaction
   processor. The file names on your system will be different than these
   examples.

For more information on log files, see
:doc:`../sysadmin_guide/log_configuration`.


.. _stop-sawtooth-ubuntu-label:

Step 12: Stop Sawtooth Components
=================================

Use this procedure if you need to stop or reset the Sawtooth environment for any
reason.

.. note::

   This application development environment is used in later procedures in this
   guide. Do not stop this environment if you intend to continue with these
   procedures.

To stop the Sawtooth components:

#. Stop the validator by entering CTRL-c in the validator terminal window.

   .. note::

      A single CTRL-c does a graceful shutdown. If you prefer not to wait, you
      can enter multiple CTRL-c characters to force the shutdown.

#. Stop the Devmode consensus engine by entering a single CTRL-c in consensus terminal window.

#. Stop the REST API by entering a single CTRL-c in REST API terminal window.

#. Stop each transaction processor by entering a single CTRL-c in the
   appropriate window.

You can restart the Sawtooth components at a later time and continue working
with your application development environment.

To completely reset the Sawtooth environment and start over from the beginning
of this procedure, add these steps:

* To delete the blockchain data, remove all files from ``/var/lib/sawtooth``.

* To delete the Sawtooth logs, remove all files from ``/var/log/sawtooth/``.

* To delete the Sawtooth keys, remove the key files
  ``/etc/sawtooth/keys/validator.\*`` and
  ``/home/``\ `yourname`\ ``/.sawtooth/keys/``\ `yourname`\ ``.\*``.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
