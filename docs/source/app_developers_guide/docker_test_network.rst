.. _proc-multi-docker-label:

Using Docker for a Sawtooth Test Network
========================================

This procedure describes how to use Docker to create a network of five Sawtooth
nodes for an application development environment. Each node is a set of Docker
containers that runs a validator and related Sawtooth components.

.. note::

   For a single-node environment, see :doc:`docker`.

This procedure guides you through the following tasks:

 * Downloading the Sawtooth Docker Compose file
 * Starting the Sawtooth network with `docker-compose`
 * Checking process status
 * Configuring the allowed transaction types (optional)
 * Connecting to the Sawtooth shell container and confirming network
   functionality
 * Stopping Sawtooth and resetting the Docker environment


.. _about-sawtooth-nw-env-docker-label:

About the Docker Sawtooth Network Environment
---------------------------------------------

This test environment is a network of five Sawtooth nodes.

.. figure:: ../images/appdev-environment-multi-node.*
   :width: 100%
   :align: center
   :alt: Docker: Sawtooth network with five nodes

.. include:: ../_includes/about-nw-each-node-runs.inc

Like the :doc:`single-node test environment <docker>`, this environment uses
parallel transaction processing and static peering. However, it uses a different
consensus algorithm (Devmode consensus is not recommended for a network). You
can choose either PBFT or PoET consensus.

.. include:: ../_includes/pbft-vs-poet-cfg.inc

The first node creates the `genesis block`, which specifies the on-chain
settings for the network configuration. The other nodes access those settings
when they join the network.


.. _prereqs-multi-docker-label:

Prerequisites
-------------

* This application development environment requires Docker Engine and Docker
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

* If you created a :doc:`single-node Docker environment <docker>` that is
  still running, shut it down and delete the existing blockchain data and logs.
  For more information, see :ref:`stop-sawtooth-docker-label`.


Step 1: Download the Docker Compose File
----------------------------------------

Download the Docker Compose file for a multiple-node network.

* For PBFT, download
  `sawtooth-default-pbft.yaml <./sawtooth-default-pbft.yaml>`_

* For PoET, download
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

1. Connect to the shell container.

    .. code-block:: console

       user@host$ docker exec -it sawtooth-shell-default bash
       root@0e0fdc1ab#


#. To check whether peering has occurred on the network, submit a peers query
   to the REST API on the first node. This command specifies the container name
   and port for the first node's REST API.

      .. code-block:: console

         root@0e0fdc1ab# curl http://sawtooth-rest-api-default-0:8008/peers

   If this query returns a 503 error, the nodes have not yet peered with the
   Sawtooth network. Repeat the query until you see output that resembles the
   following example:

     .. code-block:: console

        {
          "data": [
            "tcp://validator-4:8800",
            "tcp://validator-3:8800",
            ...
            "tcp://validator-2:8800",
            "tcp://validator-1:8800"
          ],
          "link": "http://sawtooth-rest-api-default-0:8008/peers"

#. (Optional) You can run the following Sawtooth commands to show the other
   nodes on the network.

   a. Run ``sawtooth peer list`` to show the peers of a particular node. For
      example, the following command specifies the REST API on the first node,
      so it displays the first node's peers.

      .. code-block:: console

         root@0e0fdc1ab# sawtooth peer list --url http://sawtooth-rest-api-default-0:8008
         tcp://validator-1:8800,tcp://validator-1:8800,tcp://validator-2:8800,tcp://validator-3:8800

   #. Run ``sawnet peers list`` to display a complete graph of peers on the
      network (available in Sawtooth release 1.1 and later).

      .. code-block:: console

         root@0e0fdc1ab# sawnet peers list http://sawtooth-rest-api-default-0:8008
         {
         "tcp://validator-0:8800": [
         "tcp://validator-1:8800",
         "tcp://validator-1:8800",
         "tcp://validator-2:8800",
         "tcp://validator-3:8800"
         ]
         }

#. Submit a transaction to the REST API on the first node. This
   example sets a key named ``MyKey`` to the value 999.

     .. code-block:: console

        root@0e0fdc1ab# intkey set --url http://sawtooth-rest-api-default-0:8008 MyKey 999

     The output should resemble this example:

     .. code-block:: console

        {
          "link": "http://sawtooth-rest-api-default-0:8008/batch_statuses?id=dacefc7c9fe2c8510803f8340...
        }

#. Watch for this transaction to appear on a different node. The following
   command requests the value of ``MyKey`` from the REST API on the second node.

   You can run this command from the first node's shell container by specifying
   the URL of the other node's REST API, as in this example.

     .. code-block:: console

        root@0e0fdc1ab# intkey show --url http://sawtooth-rest-api-default-1:8008 MyKey

     The output should show the key name and current value:

     .. code-block:: console

        MyKey: 999


.. _configure-txn-procs-docker-label:

Step 5. Configure the Allowed Transaction Types (Optional)
----------------------------------------------------------

By default, a validator accepts transactions from any transaction processor.
However, Sawtooth allows you to limit the types of transactions that can be
submitted.

In this step, you will configure the Sawtooth network to accept transactions
only from the transaction processors running in the example environment.
Transaction-type restrictions are an on-chain setting, so this configuration
change is made on one node, then applied to all other nodes.

The :doc:`Settings transaction processor
<../transaction_family_specifications/settings_transaction_family>`
handles on-chain configuration settings. You will use the ``sawset`` command to
create and submit a batch of transactions containing the configuration change.

.. important::

   You **must** run this procedure from the first validator container, because
   the example Docker Compose file uses the first validator's key to create and
   sign the genesis block. (At this point, only the key used to create the
   genesis block can change on-chain settings.) For more information, see
   :doc:`/sysadmin_guide/adding_authorized_users`.


1. Connect to the first validator container (``sawtooth-validator-default-0``).
   The next command requires the validator key that was generated in that
   container.

   .. code-block:: console

     user@host$ docker exec -it sawtooth-validator-default-0 bash
     root@c0c0ab33#

#. Run the following command from the validator container to specify the
   allowed transaction families.

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
   docker-compose output.

   .. code-block:: console

      .
      .
      .
      sawtooth-settings-tp-default-0  | INFO  | settings_tp::handler | Setting "sawtooth.validator.transaction_families" changed to "[{\"family\": \"intkey\", \"version\": \"1.0\"}, {\"family\":\"sawtooth_settings\", \"version\":\"1.0\"}, {\"family\":\"xo\", \"version\":\"1.0\"}, {\"family\":\"sawtooth_validator_registry\", \"version\":\"1.0\"}]"
      sawtooth-settings-tp-default-0  | INFO  | sawtooth_sdk::proces | TP_PROCESS_REQUEST sending TpProcessResponse: OK

#. Run the following command to check the setting change on the shell container
   or any validator container. You can specify any REST API on the network;
   this example uses the REST API on the first node.

   .. code-block:: console

      root@0e0fdc1ab# sawtooth settings list --url http://sawtooth-rest-api-default-0:8008

   The output should be similar to this example:

   .. code-block:: console

      sawtooth.consensus.algorithm.name: {name}
      sawtooth.consensus.algorithm.version: {version}
      ...
      sawtooth.publisher.max_batches_per_block=1200
      sawtooth.settings.vote.authorized_keys: 0242fcde86373d0aa376...
      sawtooth.validator.transaction_families: [{"family": "intkey...

Step 6: Stop the Sawtooth Network (Optional)
--------------------------------------------

Use this procedure to stop or reset the multiple-node Sawtooth environment.

1. Exit from all open containers (such as the shell, REST-API, validator, and
   settings containers used in this procedure).

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
