*********************************************
Using Docker for your Development Environment
*********************************************

This procedure explains how to set up Hyperledger Sawtooth for application
development using a multi-container Docker environment. It shows you how to
start Sawtooth and connect to the necessary Docker containers, then walks you
through the following tasks:

 * Checking the status of Sawtooth components
 * Using Sawtooth commands to submit transactions, display block data, and view
   global state
 * Examining Sawtooth logs
 * Stopping Sawtooth and resetting the Docker environment

After completing this tutorial, you will have the application development
environment that is required for the other tutorials in this guide. The next
tutorial introduces the XO transaction family by using the ``xo`` client
commands to play a game of tic-tac-toe. The final set of tutorials describe how
to use an SDK to create a transaction family that implements your application's
business logic.

About the Application Development Environment
=============================================

The Docker application development environment is a single validator node that
is running a validator, a REST API, and three transaction processors. This
environment uses Developer mode (dev mode) consensus and serial transaction
processing.

.. figure:: ../images/appdev-environment-one-node-3TPs.*
   :width: 100%
   :align: center
   :alt: Docker: Sawtooth application environment with one node

This environment introduces basic Sawtooth functionality with the
`IntegerKey
<../transaction_family_specifications/integerkey_transaction_family>`_
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

.. note::

   The Docker environment includes a Docker Compose file that
   handles environment setup steps such as generating keys and creating a
   genesis block. To learn how the typical startup process works, see
   :doc:`ubuntu`.


Prerequisites
=============

This application development environment requires Docker Engine and Docker
Compose.

* Windows: Install the latest version of
  `Docker Engine for Windows <https://docs.docker.com/docker-for-windows/install/>`_
  (also installs Docker Compose).

* macOS: Install the latest version of
  `Docker Engine for macOS <https://docs.docker.com/docker-for-mac/install/>`_
  (also installs Docker Compose).

* Linux: Install the latest versions of
  `Docker Engine <https://docs.docker.com/engine/installation/linux/ubuntu>`_
  and
  `Docker Compose <https://docs.docker.com/compose/install/#install-compose>`_.
  Then follow
  `Post-Install steps
  <https://docs.docker.com/install/linux/linux-postinstall/#manage-docker-as-a-non-root-user>`_.

In this procedure, you will open six terminal windows to connect to the Docker
containers: one for each Sawtooth component and one to use for client commands.

.. note::

   The Docker Compose file for Sawtooth handles environment setup steps such as
   generating keys and creating a genesis block. To learn how the typical
   startup process works, see :doc:`ubuntu`.


Step 1: Download the Sawtooth Docker Compose File
=================================================

Download the Docker Compose file for the Sawtooth environment,
`sawtooth-default.yaml <./sawtooth-default.yaml>`_.

This example Compose file defines the process for constructing a simple
Sawtooth environment with following containers:

* A single validator using dev mode consensus
* A REST API connected to the validator
* The Settings transaction processor (``sawtooth-settings``)
* The IntegerKey transaction processor (``intkey-tp-python``)
* The XO transaction processor (``xo-tp-python``)
* A client (shell) container for running Sawtooth commands

The Compose file also specifies the container images to download from Docker Hub
and the network settings needed for all the containers to communicate correctly.

After completing the tutorials in this guide, you can use this Compose file as
the basis for your own multi-container Sawtooth development environment or
application.


Step 2: Configure Proxy Settings (Optional)
===========================================

To configure Docker to work with an HTTP or HTTPS proxy server, follow the
instructions for proxy configuration in the documentation for your operating
system:

* Windows - See "`Get Started with Docker for Windows
  <https://docs.docker.com/docker-for-windows/#proxies>`_".

* macOS - See "`Get Started with Docker for Mac
  <https://docs.docker.com/docker-for-mac/>`_".

* Linux - See "`Control and configure Docker with Systemd
  <https://docs.docker.com/engine/admin/systemd/#httphttps-proxy>`_".


Step 3: Start the Sawtooth Docker Environment
=============================================

To start the Sawtooth Docker environment, perform the following tasks:

1. Open a terminal window.

#. Change your working directory to the same directory where you saved the
   Docker Compose file.

#. Run the following command:

   .. _restart:

   .. code-block:: console

     user@host$ docker-compose -f sawtooth-default.yaml up

   .. tip::
      If you previously ran ``docker-compose ... up`` without a clean shut down,
      run the following command first:

      ``docker-compose -f sawtooth-default.yaml down``

#. Downloading the Docker images for the Sawtooth environment can take
   several minutes. Wait until you see output that shows the containers
   registering and creating initial blocks.  Once you see output that resembles
   the following example, you can move on to the next step.

   .. code-block:: console

      ...
      sawtooth-settings-tp-default | [2018-03-08 22:55:10.537 INFO     core] register attempt: OK
      sawtooth-settings-tp-default | [2018-03-08 22:55:10.538 DEBUG    core] received message of type: TP_PROCESS_REQUEST
      sawtooth-settings-tp-default | [2018-03-08 22:55:10.550 INFO     handler] Setting setting sawtooth.settings.vote.authorized_keys changed from None to 039fa17f2962706aae83f3cc1f7d0c51dda7ffe15f5811fefd4ea5fdd3e84d0755
      sawtooth-validator-default | [2018-03-08 22:55:10.557 DEBUG    genesis] Produced state hash 53d38378e8c61f42112c39f9c84d42d339320515ef44f50d6b4dd52f3f1b9054 for genesis block.
      sawtooth-validator-default | [2018-03-08 22:55:10.560 INFO     genesis] Genesis block created: 60e79c91757c73185b36802661833f586f4dd5ef3c4cb889f37c287921af8ad01a8b95e9d81af698e6c3f3eb7b65bfd6f6b834ffc9bc36317d8a1ae7ecc45668 (block_num:0, state:53d38378e8c61f42112c39f9c84d42d339320515ef44f50d6b4dd52f3f1b9054, previous_block_id:0000000000000000)
      sawtooth-validator-default | [2018-03-08 22:55:10.561 DEBUG    chain_id_manager] writing block chain id
      sawtooth-validator-default | [2018-03-08 22:55:10.562 DEBUG    genesis] Deleting genesis data.
      sawtooth-validator-default | [2018-03-08 22:55:10.564 DEBUG    selector_events] Using selector: ZMQSelector
      sawtooth-validator-default | [2018-03-08 22:55:10.565 INFO     interconnect] Listening on tcp://eth0:8800
      sawtooth-validator-default | [2018-03-08 22:55:10.566 DEBUG    dispatch] Added send_message function for connection ServerThread
      sawtooth-validator-default | [2018-03-08 22:55:10.566 DEBUG    dispatch] Added send_last_message function for connection ServerThread
      sawtooth-validator-default | [2018-03-08 22:55:10.568 INFO     chain] Chain controller initialized with chain head: 60e79c91757c73185b36802661833f586f4dd5ef3c4cb889f37c287921af8ad01a8b95e9d81af698e6c3f3eb7b65bfd6f6b834ffc9bc36317d8a1ae7ecc45668 (block_num:0, state:53d38378e8c61f42112c39f9c84d42d339320515ef44f50d6b4dd52f3f1b9054, previous_block_id:0000000000000000)
      sawtooth-validator-default | [2018-03-08 22:55:10.569 INFO     publisher] Now building on top of block: 60e79c91757c73185b36802661833f586f4dd5ef3c4cb889f37c287921af8ad01a8b95e9d81af698e6c3f3eb7b65bfd6f6b834ffc9bc36317d8a1ae7ecc45668 (block_num:0, state:53d38378e8c61f42112c39f9c84d42d339320515ef44f50d6b4dd52f3f1b9054, previous_block_id:0000000000000000)
      ...

This terminal window will continue to display log messages as you run commands
in other containers.

.. note::

   If you need to reset the environment for any reason, see
   :ref:`stop-sawtooth-docker-label`.


Step 4: Log Into the Client Container
=====================================

Sawtooth includes commands that act as a client application. The client
container is used to run these Sawtooth commands, which interact with the
validator through the REST API.

To log into the client container, open a new terminal window and run the
following command:

.. code-block:: console

   user@host$ docker exec -it sawtooth-shell-default bash
   root@client#

In this procedure, the prompt ``root@client#`` is used for commands that should
be run in the terminal window for the client container.

.. important::

  Your environment is ready for experimenting with Sawtooth. However, any work
  done in this environment will be lost once the container in which you ran
  ``docker-compose`` exits. In order to use this application development
  environment for application development, you would need to take additional
  steps, such as mounting a host directory into the container. See the `Docker
  documentation <https://docs.docker.com/>`_ for more information.

.. _confirming-connectivity-docker-label:

Step 5: Confirm Connectivity to the REST API
============================================

#. To confirm that the REST API and validator are running and reachable from
   the client container, run this ``curl`` command:

   .. code-block:: console

      root@client# curl http://rest-api:8008/blocks

#. To check connectivity from the host computer, open a new terminal window on
   your host system and run this ``curl`` command:

   .. code-block:: console

      user@host$ curl http://localhost:8008/blocks

   If the validator and REST API are running and reachable, the output for each
   command should be similar to this example:

   .. code-block:: console

     {
       "data": [
         {
           "batches": [],
           "header": {
             "batch_ids": [],
             "block_num": 0,
             "mconsensus": "R2VuZXNpcw==",
             "previous_block_id": "0000000000000000",
             "signer_public_key": "03061436bef428626d11c17782f9e9bd8bea55ce767eb7349f633d4bfea4dd4ae9",
             "state_root_hash": "708ca7fbb701799bb387f2e50deaca402e8502abe229f705693d2d4f350e1ad6"
           },
           "header_signature": "119f076815af8b2c024b59998e2fab29b6ae6edf3e28b19de91302bd13662e6e43784263626b72b1c1ac120a491142ca25393d55ac7b9f3c3bf15d1fdeefeb3b"
         }
       ],
       "head": "119f076815af8b2c024b59998e2fab29b6ae6edf3e28b19de91302bd13662e6e43784263626b72b1c1ac120a491142ca25393d55ac7b9f3c3bf15d1fdeefeb3b",
       "link": "http://rest-api:8008/blocks?head=119f076815af8b2c024b59998e2fab29b6ae6edf3e28b19de91302bd13662e6e43784263626b72b1c1ac120a491142ca25393d55ac7b9f3c3bf15d1fdeefeb3b",
       "paging": {
         "start_index": 0,
         "total_count": 1
       }
     }

   If the validator process or the validator container is not running, the
   ``curl`` command will time out or return nothing.


.. _configure-tf-settings-docker-label:

Step 6: Use Sawtooth Commands as a Client
=========================================

Sawtooth includes commands that act as a client application. This step describes
how to use the ``intkey`` and ``sawtooth`` commands to create and submit
transactions, display blockchain and block data, and examine global state data.

.. note::

   Use the ``--help`` option with any Sawtooth command to display the available
   options and subcommands.

To run the commands in this section, use the terminal window for the client
container.

Creating and Submitting Transactions with intkey
------------------------------------------------

The ``intkey`` command creates and submits IntegerKey transactions for testing
purposes.

#. Use ``intkey create_batch`` to prepare batches of transactions that set
   a few keys to random values, then randomly increment and decrement those
   values. These batches are saved locally in the file ``batches.intkey``.

   .. code-block:: console

      root@client# intkey create_batch --count 10 --key-count 5
      Writing to batches.intkey...

#. Use ``intkey load`` to submit the batches to the validator.

   .. code-block:: console

      root@client# intkey load -f batches.intkey --url http://rest-api:8008
      batches: 11 batch/sec: 141.7800162868952

#. The terminal window in which you ran the ``docker-compose`` command displays
   log messages showing that the validator is handling the submitted
   transactions and that values are being incremented and decremented, as in
   this example:

   .. code-block:: console

      sawtooth-intkey-tp-python-default | [2018-03-08 21:26:20.334 DEBUG    core] received message of type: TP_PROCESS_REQUEST
      sawtooth-intkey-tp-python-default | [2018-03-08 21:26:20.339 DEBUG    handler] Decrementing "GEJTiZ" by 10
      sawtooth-intkey-tp-python-default | [2018-03-08 21:26:20.347 DEBUG    core] received message of type: TP_PROCESS_REQUEST
      sawtooth-intkey-tp-python-default | [2018-03-08 21:26:20.352 DEBUG    handler] Decrementing "lrAYjm" by 8
      ...
      sawtooth-validator-default | [2018-03-08 21:26:20.397 INFO     chain] Fork comparison at height 50 is between - and 3d4d952d
      sawtooth-validator-default | [2018-03-08 21:26:20.397 INFO     chain] Chain head updated to: 3d4d952d4774988bd67a4deb85830155a5f505c68bea11d832a6ddbdd5eeebc34f5a63a9e59a426376cd2e215e19c0dfa679fe016be26307c3ee698cce171d51 (block_num:50, state:e18c2ce54859d1e9a6e4fb949f8d861e483d330b363b4060b069f53d7e6c6380, previous_block_id:e05737151717eb8787a2db46279fedf9d331a501c12cd8059df379996d9a34577cf605e95f531514558b200a386dc73e11de3fa17d6c00882acf6f9d9c387e82)
      sawtooth-validator-default | [2018-03-08 21:26:20.398 INFO     publisher] Now building on top of block: 3d4d952d4774988bd67a4deb85830155a5f505c68bea11d832a6ddbdd5eeebc34f5a63a9e59a426376cd2e215e19c0dfa679fe016be26307c3ee698cce171d51 (block_num:50, state:e18c2ce54859d1e9a6e4fb949f8d861e483d330b363b4060b069f53d7e6c6380, previous_block_id:e05737151717eb8787a2db46279fedf9d331a501c12cd8059df379996d9a34577cf605e95f531514558b200a386dc73e11de3fa17d6c00882acf6f9d9c387e82)
      sawtooth-validator-default | [2018-03-08 21:26:20.401 DEBUG    chain] Verify descendant blocks: 3d4d952d4774988bd67a4deb85830155a5f505c68bea11d832a6ddbdd5eeebc34f5a63a9e59a426376cd2e215e19c0dfa679fe016be26307c3ee698cce171d51 (block_num:50, state:e18c2ce54859d1e9a6e4fb949f8d861e483d330b363b4060b069f53d7e6c6380, previous_block_id:e05737151717eb8787a2db46279fedf9d331a501c12cd8059df379996d9a34577cf605e95f531514558b200a386dc73e11de3fa17d6c00882acf6f9d9c387e82) ([])
      sawtooth-validator-default | [2018-03-08 21:26:20.402 INFO     chain] Finished block validation of: 3d4d952d4774988bd67a4deb85830155a5f505c68bea11d832a6ddbdd5eeebc34f5a63a9e59a426376cd2e215e19c0dfa679fe016be26307c3ee698cce171d51 (block_num:50, state:e18c2ce54859d1e9a6e4fb949f8d861e483d330b363b4060b069f53d7e6c6380, previous_block_id:e05737151717eb8787a2db46279fedf9d331a501c12cd8059df379996d9a34577cf605e95f531514558b200a386dc73e11de3fa17d6c00882acf6f9d9c387e82)

#. You can also use ``docker logs`` to examine at the Sawtooth log messages
   from your host system. For example, this command displays the last five
   entries in the log:

   .. code-block:: console

      user@host$ docker logs --tail 5 sawtooth-validator-default
      sawtooth-validator-default | [2018-03-08 21:26:20.397 INFO     chain] Fork comparison at height 50 is between - and 3d4d952d
      sawtooth-validator-default | [2018-03-08 21:26:20.397 INFO     chain] Chain head updated to: 3d4d952d4774988bd67a4deb85830155a5f505c68bea11d832a6ddbdd5eeebc34f5a63a9e59a426376cd2e215e19c0dfa679fe016be26307c3ee698cce171d51 (block_num:50, state:e18c2ce54859d1e9a6e4fb949f8d861e483d330b363b4060b069f53d7e6c6380, previous_block_id:e05737151717eb8787a2db46279fedf9d331a501c12cd8059df379996d9a34577cf605e95f531514558b200a386dc73e11de3fa17d6c00882acf6f9d9c387e82)
      sawtooth-validator-default | [2018-03-08 21:26:20.398 INFO     publisher] Now building on top of block: 3d4d952d4774988bd67a4deb85830155a5f505c68bea11d832a6ddbdd5eeebc34f5a63a9e59a426376cd2e215e19c0dfa679fe016be26307c3ee698cce171d51 (block_num:50, state:e18c2ce54859d1e9a6e4fb949f8d861e483d330b363b4060b069f53d7e6c6380, previous_block_id:e05737151717eb8787a2db46279fedf9d331a501c12cd8059df379996d9a34577cf605e95f531514558b200a386dc73e11de3fa17d6c00882acf6f9d9c387e82)
      sawtooth-validator-default | [2018-03-08 21:26:20.401 DEBUG    chain] Verify descendant blocks: 3d4d952d4774988bd67a4deb85830155a5f505c68bea11d832a6ddbdd5eeebc34f5a63a9e59a426376cd2e215e19c0dfa679fe016be26307c3ee698cce171d51 (block_num:50, state:e18c2ce54859d1e9a6e4fb949f8d861e483d330b363b4060b069f53d7e6c6380, previous_block_id:e05737151717eb8787a2db46279fedf9d331a501c12cd8059df379996d9a34577cf605e95f531514558b200a386dc73e11de3fa17d6c00882acf6f9d9c387e82) ([])
      sawtooth-validator-default | [2018-03-08 21:26:20.402 INFO     chain] Finished block validation of: 3d4d952d4774988bd67a4deb85830155a5f505c68bea11d832a6ddbdd5eeebc34f5a63a9e59a426376cd2e215e19c0dfa679fe016be26307c3ee698cce171d51 (block_num:50, state:e18c2ce54859d1e9a6e4fb949f8d861e483d330b363b4060b069f53d7e6c6380, previous_block_id:e05737151717eb8787a2db46279fedf9d331a501c12cd8059df379996d9a34577cf605e95f531514558b200a386dc73e11de3fa17d6c00882acf6f9d9c387e82)

Submitting Transactions with sawtooth batch submit
--------------------------------------------------

In the example above, the ``intkey create_batch`` command created the file
``batches.intkey``.  Rather than using ``intkey load`` to submit these
transactions, you could use ``sawtooth batch submit`` to submit them.

#. As before, create a batch of transactions:

   .. code-block:: console

      root@client# intkey create_batch --count 10 --key-count 5
      Writing to batches.intkey...

#. Submit the batch file with ``sawtooth batch submit``:

   .. code-block:: console

      root@client# sawtooth batch submit -f batches.intkey --url http://rest-api:8008
      batches: 11,  batch/sec: 216.80369536716367

Viewing Blockchain and Block Data with sawtooth block
-----------------------------------------------------

The ``sawtooth block`` command displays information about the blocks stored on
the blockchain.

#. Use ``sawtooth block list`` to display the list of blocks stored in state.

    .. code-block:: console

       root@client# sawtooth block list --url http://rest-api:8008

    The output shows the block number and block ID, as in this example:

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

      root@client# sawtooth block show --url http://rest-api:8008 {BLOCK_ID}

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

#. Use ``sawtooth state list`` to list the nodes (addresses) in state:

   .. code-block:: console

      root@client# sawtooth state list --url http://rest-api:8008

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

      root@client# sawtooth state show --url http://rest-api:8008 {STATE_ADDRESS}

   The output shows the bytes stored at that address and the block ID of the
   "chain head" that the current state is tied to, as in this example:

   .. code-block:: console

      DATA: "b'\xa1fcCTdcH\x192B'"
      HEAD: "0c4364c6d5181282a1c7653038ec9515cb0530c6bfcb46f16e79b77cb524491676638339e8ff8e3cc57155c6d920e6a4d1f53947a31dc02908bcf68a91315ad5"

.. _container-names-label:

Step 7: Connect to Each Container (Optional)
============================================

Use this information when you need to connect to any container in the Sawtooth
application development environment. For example, you can examine the log files
or check the status of Sawtooth components in any container.

#. Use the following ``docker`` command to list all running Docker containers

   .. code-block:: console

      user@host$ docker ps

   The output should resemble the following example:

   .. code-block:: console

      CONTAINER ID IMAGE                                     COMMAND               CREATED       STATUS       PORTS                            NAMES
      76f6731c43a9 hyperledger/sawtooth-all:1.1              "bash -c 'sawtooth k" 7 minutes ago Up 7 minutes 4004/tcp, 8008/tcp               sawtooth-shell-default
      9844faed9e9d hyperledger/sawtooth-intkey-tp-python:1.1 "intkey-tp-python -v" 7 minutes ago Up 7 minutes 4004/tcp                         sawtooth-intkey-tp-python-default
      44db125c2dca hyperledger/sawtooth-settings-tp:1.1      "settings-tp -vv -C " 7 minutes ago Up 7 minutes 4004/tcp                         sawtooth-settings-tp-default
      875df9d022d6 hyperledger/sawtooth-xo-tp-python:1.1     "xo-tp-python -vv -C" 7 minutes ago Up 7 minutes 4004/tcp                         sawtooth-xo-tp-python-default
      93d048c01d30 hyperledger/sawtooth-rest-api:1.1         "sawtooth-rest-api -" 7 minutes ago Up 7 minutes 4004/tcp, 0.0.0.0:8008->8008/tcp sawtooth-rest-api-default
      6bbcda66a5aa hyperledger/sawtooth-validator:1.1        "bash -c 'sawadm key" 7 minutes ago Up 7 minutes 0.0.0.0:4004->4004/tcp           sawtooth-validator-default

   The Docker Compose file defines the name of each container. It also
   specifies the TCP port and host name, if applicable. The following table
   shows the values in the example Compose file, ``sawtooth-default.yaml``.

   +---------------+---------------------------------------+----------+----------------------+
   | **Component** | **Container Name**                    | **Port** | **Host Name**        |
   +===============+=======================================+==========+======================+
   | Validator     | ``sawtooth-validator-default``        | 4004     | ``validator``        |
   +---------------+---------------------------------------+----------+----------------------+
   | REST API      | ``sawtooth-rest-api-default``         | 8008     | ``rest-api``         |
   +---------------+---------------------------------------+----------+----------------------+
   | Settings TP   | ``sawtooth-settings-tp-default``      |          | ``settings-tp``      |
   +---------------+---------------------------------------+----------+----------------------+
   | IntegerKey TP | ``sawtooth-intkey-tp-python-default`` |          | ``intkey-tp-python`` |
   +---------------+---------------------------------------+----------+----------------------+
   | XO TP         | ``sawtooth-xo-tp-python-default``     |          | ``xo-tp-python``     |
   +---------------+---------------------------------------+----------+----------------------+
   | Shell         | ``sawtooth-shell-default``            |          |                      |
   +---------------+---------------------------------------+----------+----------------------+

   Note that the validator and REST API ports are exposed to other containers
   and forwarded (published) for external connections, such as from your host
   system.

#. Use the following ``docker exec`` command from your host system to connect
   to a Sawtooth Docker container.

   .. code-block:: console

      user@host$ docker exec -it {ContainerName} bash

   For example, you can use the following command from your host system to
   connect to the validator container:

   .. code-block:: console

      user@host$ docker exec -it sawtooth-validator-default bash

#. After connecting to the container, you can use ``ps`` to verify that the
   Sawtooth component is running.

   .. code-block:: console

      # ps --pid 1 fw

   In the validator container, the output resembles the following example:

   .. code-block:: console

      PID TTY      STAT   TIME COMMAND
       1 ?        Ss     0:00 bash -c sawadm keygen && sawtooth keygen my_key
      && sawset genesis -k /root/.sawtooth/keys/my_key.priv && sawadm genesis
      config-genesis.batch && sawtooth-validator -vv --endpoint


.. _examine-logs-docker-label:

Step 8: Examine Sawtooth Logs
=============================

As described above, you can display Sawtooth log messages by using the
``docker logs`` command from your host system:

.. code-block:: console

   user@host$ docker logs {OPTIONS} {ContainerName}

In each container, the Sawtooth log files for that component are stored in the
directory ``/var/log/sawtooth``. Each component (validator, REST API, and
transaction processors) has both a debug log and an error log.

For example, the validator container has these log files:

.. code-block:: console

   root@validator# ls -1 /var/log/sawtooth
   validator-debug.log
   validator-error.log

The IntegerKey container has these log files:

.. code-block:: console

   root@intkey-tp# ls -1 /var/log/sawtooth
   intkey-ae98c3726f9743c4-debug.log
   intkey-ae98c3726f9743c4-error.log

.. note::

   By convention, the transaction processors use a random string to make the log
   file names unique. The names on your system may be different than these
   examples.

For more information on log files, see
:doc:`../sysadmin_guide/log_configuration`.


.. _stop-sawtooth-docker-label:

Step 9: Stop the Sawtooth Environment
=====================================

Use this procedure if you need to stop or reset the Sawtooth environment for any
reason.

.. important::

  Any work done in this environment will be lost once the container exits.
  To keep your work, you would need to take additional steps, such as
  mounting a host directory into the container. See the `Docker documentation
  <https://docs.docker.com/>`_ for more information.

#. Log out of the client container.

#. Enter CTRL-c from the window where you originally ran ``docker-compose``. The
   output will resemble this example:

   .. code-block:: console

      ^CGracefully stopping... (press Ctrl+C again to force)
      Stopping sawtooth-shell-default            ... done
      Stopping sawtooth-rest-api-default         ... done
      Stopping sawtooth-intkey-tp-python-default ... done
      Stopping sawtooth-xo-tp-python-default     ... done
      Stopping sawtooth-settings-tp-default      ... done
      Stopping sawtooth-validator-default        ... done

#. After all containers have shut down, run this ``docker-compose`` command:

   .. code-block:: console

      user@host$ docker-compose -f sawtooth-default.yaml down
      Removing sawtooth-shell-default            ... done
      Removing sawtooth-intkey-tp-python-default ... done
      Removing sawtooth-xo-tp-python-default     ... done
      Removing sawtooth-settings-tp-default      ... done
      Removing sawtooth-rest-api-default         ... done
      Removing sawtooth-validator-default        ... done
      Removing network testsawtooth_default


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
