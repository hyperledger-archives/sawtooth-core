.. _proc-multi-docker-label:

Using Docker for a Sawtooth Test Network
========================================

This procedure describes how to use Docker to create a network of five Sawtooth
nodes for an application development environment, using either PBFT or PoET
consensus. (Devmode consensus is not recommended for a network.)

.. include:: ../_includes/pbft-vs-poet-cfg.inc


.. _about-sawtooth-nw-env-docker-label:

About the Sawtooth Network Environment
--------------------------------------

The following figure shows an example network with two validator nodes:

.. figure:: ../images/appdev-environment-multi-node.*
   :width: 100%
   :align: center
   :alt: Docker: Sawtooth network with five nodes

.. include:: ../_includes/about-nw-each-node-runs.inc

Like the :doc:`single-node test environment <docker>`, this environment uses
parallel transaction processing and static peering.


.. _prereqs-multi-docker-label:

Prerequisites
-------------

This procedure assumes that you have already created a single-node environment,
as described in :doc:`docker`. Refer to the previous procedure for more
information on each step.

If the single-node environment is still running, shut it down. Enter CTRL-c from
the window where you originally ran ``docker-compose up``, then run the
following command from your host system:

.. code-block:: console

   $ docker-compose -f sawtooth-default.yaml down

For more information, see :ref:`stop-sawtooth-docker-label`.


Step 1: Download the Docker Compose File
----------------------------------------

Download the Docker Compose file for a multiple-node network.

* For PBFT: Download
  `sawtooth-default-pbft.yaml <./sawtooth-default-pbft.yaml>`_

* For PoET: Download
  `sawtooth-default-poet.yaml <./sawtooth-default-poet.yaml>`_

Step 2: Start the Sawtooth Network
----------------------------------

.. note::

   The Docker Compose file for Sawtooth handles environment setup steps such as
   generating keys and creating a genesis block. To learn how the typical
   network startup process works, see :doc:`ubuntu_test_network`.

1. Open a terminal window.

#. Change to the directory where you saved the Docker Compose file.

#. Start the Sawtooth network.

   * For PBFT:

     .. code-block:: console

        user@host$ docker-compose -f sawtooth-default-pbft.yaml up

   * For PoET:

     .. code-block:: console

        user@host$ docker-compose -f sawtooth-default-poet.yaml up

#. This Compose file creates five Sawtooth nodes named ``validator-#``
   (numbered from 0 to 4). Note the container names for the Sawtooth components
   on each node:

   ``validator-0``:

    * ``sawtooth-validator-default-0``
    * ``sawtooth-rest-api-default-0``
    * ``sawtooth-pbft-engine-default-0`` or ``sawtooth-poet-engine-0``
    * ``sawtooth-settings-tp-default-0``
    * ``sawtooth-intkey-tp-python-default-0``
    * ``sawtooth-xo-tp-python-default-0``
    * (PoET only) ``sawtooth-poet-validator-registry-tp-0``

   ``validator-1``:

    * ``sawtooth-validator-default-1``
    * ``sawtooth-rest-api-default-1``
    * ``sawtooth-pbft-engine-default-1`` or ``sawtooth-poet-engine-1``
    * ``sawtooth-settings-tp-default-1``
    * ``sawtooth-intkey-tp-python-default-1``
    * ``sawtooth-xo-tp-python-default-1``
    * (PoET only) ``sawtooth-poet-validator-registry-tp-1``

   ... and so on.

#. Note that there is only one shell container for this Docker environment:

    * ``sawtooth-shell-default``

Step 3: Check the REST API Process
----------------------------------

Use these commands on one or more nodes to confirm that the REST API is
running.

1. Connect to the REST API container on a node, such as
   ``sawtooth-poet-rest-api-default-0``.

   .. code-block:: console

      user@host$ docker exec -it sawtooth-rest-api-default-0 bash
      root@b1adcfe0#

#. Use the following command to verify that this component is running.

   .. code-block:: console

      root@b1adcfe0# ps --pid 1 fw
      PID TTY      STAT   TIME COMMAND
        1 ?        Ssl    0:00 /usr/bin/python3 /usr/bin/sawtooth-rest-api
        --connect tcp://validator-0:4004 --bind rest-api-0:8008

.. _confirm-nw-funct-docker-label:

Step 4: Confirm Network Functionality
-------------------------------------

#. To check whether peering has occurred on the network, submit a peers query
   to the REST API on the first validator node.

   Run the following command from the shell container,
   ``sawtooth-shell-default``.  This command specifies the container name and
   port for the first node's REST API.

     .. code-block:: console

        $ curl http://sawtooth-rest-api-default-0:8008/peers

   If this query returns a 503 error, the nodes have not yet peered with the
   Sawtooth network. Repeat the query until you see output that resembles the
   following example:

     .. code-block:: console

        {
            "data": [
            "tcp://validator-1:8800",
          ],
          "link": "http://rest-api:8008/peers"
        }

#. (Optional) You can also connect to a validator container, such as
   ``sawtooth-validator-default-0``, and run the following Sawtooth commands to
   show the other nodes on the network.

   a. Run ``sawtooth peer list`` to show the peers of a particular node.

   b. Run ``sawnet peers list`` to display a complete graph of peers on the
      network (available in Sawtooth release 1.1 and later).

#. Submit a transaction to the REST API on the first validator node. This
   example sets a key named ``MyKey`` to the value 999.

   Use the shell container to run the following command.

     .. code-block:: console

        # intkey set --url http://sawtooth-rest-api-default-0:8008 MyKey 999

#. Watch for this transaction to appear on the second validator node. The
   following command requests the value of ``MyKey`` from the REST API on the
   second validator node.

   Use the shell container to run the following command.

     .. code-block:: console

        # intkey show --url http://sawtooth-rest-api-default-1:8008 MyKey
        MyKey: 999


.. _configure-txn-procs-docker-label:

Step 5. Configure the Allowed Transaction Types (Optional)
----------------------------------------------------------

By default, a validator accepts transactions from any transaction processor.
However, Sawtooth allows you to limit the types of transactions that can be
submitted.

In this step, you will configure the validator network to accept transactions
only from the transaction processors running in the example environment.
Transaction-type restrictions are an on-chain setting, so this configuration
change is made on one node, then applied to all other nodes.

The :doc:`Settings transaction processor
<../transaction_family_specifications/settings_transaction_family>`
handles on-chain configuration settings. You will use the ``sawset`` command to
create and submit a batch of transactions containing the configuration change.

Use the following steps to create and submit a batch containing the new on-chain
setting.

1. Connect to the first validator container (``sawtooth-validator-default-0``).
   The next command requires the validator key that was generated in that
   container.

   .. code-block:: console

     % docker exec -it sawtooth-validator-default-0 bash

#. Run the following command from the validator container to check the setting
   change.

   * For PBFT:

     .. code-block:: console

        root@c0c0ab33# sawset proposal create --url http://sawtooth-rest-api-default-0:8008 --key /etc/sawtooth/keys/validator.priv \
        sawtooth.validator.transaction_families='[{"family": "intkey", "version": "1.0"}, {"family":"sawtooth_settings", "version":"1.0"}, {"family":"xo", "version":"1.0"}]'

   * For PoET:

     .. code-block:: console

        root@c0c0ab33# sawset proposal create --url http://sawtooth-rest-api-default-0:8008 --key /etc/sawtooth/keys/validator.priv \
        sawtooth.validator.transaction_families='[{"family": "intkey", "version": "1.0"}, {"family":"sawtooth_settings", "version":"1.0"}, {"family":"xo", "version":"1.0"}, {"family":"sawtooth_validator_registry", "version":"1.0"}]'

   This command sets ``sawtooth.validator.transaction_families`` to a JSON array
   that specifies the family name and version of each allowed transaction
   processor (defined in the transaction header of each family's
   :doc:`transaction family specification <../transaction_family_specifications>`).

#. After this command runs, a ``TP_PROCESS_REQUEST`` message appears in the
   Settings transaction processor log.

   You can view this log file by connecting to the ``sawtooth-settings-tp``
   container on any node, then examining
   ``/var/log/sawtooth/logs/settings-{xxxxxxx}-debug.log``. (Each Settings log
   file has a unique string in the name.) This example connects to the Settings
   transaction processor on the first node (``sawtooth-settings-tp-default-0``).


   .. code-block:: console

     % docker exec -it sawtooth-settings-tp-default-0 bash
     # tail /var/log/sawtooth/settings-*-debug.log
      .
      .
      .
      [22:18:33.137 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
      [22:18:33.219 [MainThread] handler INFO] Setting setting sawtooth.validator.transaction_families changed from None to [{"family": "intkey", "version": "1.0"}, {"family":"sawtooth_settings", "version":"1.0"}, {"family":"xo", "version":"1.0"}, ...

#. Run the following command to check the setting change. You can use any
   container for this step. Also, you can specify any REST API on the network;
   this example uses the REST API on the first validator node.

   .. code-block:: console

      # sawtooth settings list --url http://sawtooth-rest-api-default-0:8008

   The output should be similar to this example:

   * For PBFT:

     .. code-block:: console

        sawtooth.consensus.algorithm.name: pbft
        sawtooth.consensus.algorithm.version: 0.1
        sawtooth.consensus.pbft.members=["0242fcde86373d0aa376055fc6...
        sawtooth.publisher.max_batches_per_block=1200
        sawtooth.settings.vote.authorized_keys: 0242fcde86373d0aa376...
        sawtooth.validator.transaction_families: [{"family": "intkey...

   * For PoET:

     .. code-block:: console

        sawtooth.consensus.algorithm.name: PoET
        sawtooth.consensus.algorithm.version: 0.1
        sawtooth.poet.initial_wait_time: 15
        sawtooth.poet.report_public_key_pem: -----BEGIN PUBLIC KEY-----
        MIIBIjANBgkqhki...
        sawtooth.poet.target_wait_time: 5
        sawtooth.poet.valid_enclave_basenames: b785c58b77152cbe7fd55ee3...
        sawtooth.poet.valid_enclave_measurements: c99f21955e38dbb03d2ca...
        sawtooth.publisher.max_batches_per_block: 100
        sawtooth.settings.vote.authorized_keys: 036631291bbe87c3c9dde22...
        sawtooth.validator.transaction_families: [{"family": "intkey", ...

     ??? REVIEWERS: WHAT ABOUT ZTEST? `sawtooth.poet.ztest_minimum_win_count: 100000`

Step 6: Stop the Sawtooth Network (Optional)
--------------------------------------------

If you need to stop or reset the multiple-node Sawtooth environment, enter
CTRL-c in the window where you ran ``docker-compose up``, then run the following
command from your host system:

#. Enter CTRL-c in the window where you ran ``docker-compose up``.

#. After all containers have shut down, you can reset the environment (remove
   all containers and data) with the following command:

   * For PBFT:

     .. code-block:: console

        user@host$ docker-compose -f sawtooth-default-pbft.yaml down

   * For PoET:

     .. code-block:: console

        user@host$ docker-compose -f sawtooth-default-poet.yaml down


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
