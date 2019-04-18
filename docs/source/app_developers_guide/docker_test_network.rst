.. _proc-multi-docker-label:

Using Docker for a Sawtooth Test Network
========================================

In this procedure, you will use a Docker Compose file that creates a new
application development environment with five validator nodes and four
transaction processors (Settings, IntegerKey, XO, and PoET Validator Registry).

About the Sawtooth Network Environment
--------------------------------------

The following figure shows an example network with two validator nodes:

.. figure:: ../images/appdev-environment-multi-node.*
   :width: 100%
   :align: center
   :alt: Docker: Sawtooth network with five nodes

Like the single-node environment, this environment uses parallel transaction
processing and static peering. However, it has the following differences:

* PoET simulator consensus instead of dev mode, because dev mode's random-leader
  consensus is not recommended for multi-node or production networks. Sawtooth
  offers two versions of :term:`PoET consensus`. PoET-SGX relies on Intel
  Software Guard Extensions (SGX) to implement a leader-election lottery system.
  PoET simulator provides the same consensus algorithm on an SGX simulator.

* An additional transaction processor, PoET Validator Registry, handles PoET
  settings for a multiple-node network.

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

Download the Docker Compose file for a multiple-node network,
`sawtooth-default-poet.yaml <./sawtooth-default-poet.yaml>`_.
Save this file in the same directory as the single-node compose file
(``sawtooth-default.yaml``).


Step 2: Start the Sawtooth Network
----------------------------------

#. Use the following command to start the multiple-node Sawtooth network:

   .. code-block:: console

      user@host$ docker-compose -f sawtooth-default-poet.yaml up

#. This Compose file creates five validator nodes, numbered from 0 to 4.
   Note the container names for the Sawtooth components on each node:

   ``validator-0``:

    * ``sawtooth-validator-default-0``
    * ``sawtooth-rest-api-default-0``
    * ``sawtooth-settings-tp-default-0``
    * ``sawtooth-intkey-tp-python-default-0``
    * ``sawtooth-xo-tp-python-default-0``
    * ``sawtooth-poet-validator-registry-tp-0``

   ``validator-1``:

    * ``sawtooth-validator-default-1``
    * ``sawtooth-rest-api-default-1``
    * ``sawtooth-settings-tp-default-1``
    * ``sawtooth-intkey-tp-python-default-1``
    * ``sawtooth-xo-tp-python-default-1``
    * ``sawtooth-poet-validator-registry-tp-1``

   ... and so on.

#. Note that there is only one shell container for this Docker environment:

    * ``sawtooth-shell-default``

Step 3: Verify Connectivity
---------------------------

You can connect to a Docker container, such as
``sawtooth-poet-validator-registry-tp-0``, then use the following ``ps``
command to verify that the component is running.

.. code-block:: console

   # ps --pid 1 fw
   PID TTY      STAT   TIME COMMAND
   1 ?        Ssl    0:04 python3 /project/sawtooth-core/bin/poet-validator-registry-tp -C tcp://validator-0:4004


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
only from the four transaction processors in the example environment:
IntegerKey, Settings, XO, and Validator Registry. Transaction-type restrictions
are an on-chain setting, so this configuration change is applied to all
validators.

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

   .. code-block:: console

      # sawset proposal create --url http://sawtooth-rest-api-default-0:8008 --key /etc/sawtooth/keys/validator.priv \
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
      [22:18:33.219 [MainThread] handler INFO] Setting setting sawtooth.validator.transaction_families changed from None to [{"family": "intkey", "version": "1.0"}, {"family":"sawtooth_settings", "version":"1.0"}, {"family":"xo", "version":"1.0"}, {"family":"sawtooth_validator_registry", "version":"1.0"}]

#. Run the following command to check the setting change. You can use any
   container for this step. Also, you can specify any REST API on the network;
   this example uses the REST API on the first validator node.

   .. code-block:: console

      # sawtooth settings list --url http://sawtooth-rest-api-default-0:8008

   The output should be similar to this example:

   .. code-block:: console

      sawtooth.consensus.algorithm.name: PoET
      sawtooth.consensus.algorithm.version: 0.1
      sawtooth.poet.initial_wait_time: 15
      sawtooth.poet.key_block_claim_limit: 100000
      sawtooth.poet.report_public_key_pem: -----BEGIN PUBL...
      sawtooth.poet.target_wait_time: 15
      sawtooth.poet.valid_enclave_basenames: b785c58b77152cb...
      sawtooth.poet.valid_enclave_measurements: c99f21955e38dbb...
      sawtooth.poet.ztest_minimum_win_count: 100000
      sawtooth.publisher.max_batches_per_block: 200
      sawtooth.settings.vote.authorized_keys: 03e27504580fa15...
      sawtooth.validator.transaction_families: [{"family": "in...


Step 6: Stop the Sawtooth Network (Optional)
--------------------------------------------

If you need to stop or reset the multiple-node Sawtooth environment, enter
CTRL-c in the window where you ran ``docker-compose up``, then run the following
command from your host system:

.. code-block:: console

   user@host$ docker-compose -f sawtooth-default-poet.yaml down


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
