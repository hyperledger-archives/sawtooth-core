.. _proc-multi-ubuntu-label:

Using Ubuntu for a Sawtooth Test Network
========================================

This procedure describes how to create a Sawtooth network for an application
development environment on a Ubuntu platform. Each host system (physical
computer or virtual machine) is a `Sawtooth node` that runs a validator and
related Sawtooth components.

.. note::

   For a single-node environment, see :doc:`ubuntu`.

This procedure guides you through the following tasks:

 * Installing Sawtooth
 * Creating user and validator keys
 * Creating the genesis block on the first node
   (includes specifying either PBFT or PoET consensus)
 * Starting Sawtooth on each node
 * Confirming network functionality
 * Configuring the allowed transaction types (optional)

For information on Sawtooth :term:`dynamic consensus` or to learn how to change
the consensus type, see :doc:`/sysadmin_guide/about_dynamic_consensus`.

.. note::

   These instructions have been tested on Ubuntu 18.04 (Bionic) only.


.. _about-sawtooth-nw-env-label:

About the Ubuntu Sawtooth Network Environment
---------------------------------------------

This test environment is a network of several Sawtooth nodes. The following
figure shows a network with five nodes.

.. figure:: ../images/appdev-environment-multi-node.*
   :width: 100%
   :align: center
   :alt: Ubuntu: Example Sawtooth network with five nodes

.. include:: ../_includes/about-nw-each-node-runs.inc

Like the single-node environment, this environment uses parallel transaction
processing and static peering. However, it uses a different consensus algorithm
(Devmode consensus is not recommended for a network).

This procedure explains how to configure either PBFT or PoET consensus. The
initial network must include the minimum number of nodes for the chosen consensus:

.. include:: ../_includes/consensus-node-reqs.inc

.. note::

   For PBFT consensus, the network must be `fully peered` (each node must be
   connected to all other nodes).


.. _prereqs-multi-ubuntu-label:

Prerequisites
-------------

* Remove data from an existing single node: To reuse the single test node
  described in :doc:`ubuntu`, stop Sawtooth and delete all blockchain data
  and logs from that node.

  1. If the first node is running, stop the Sawtooth components
     (validator, REST API, consensus engine, and transaction processors),
     as described in :ref:`stop-sawtooth-ubuntu-label`.

  #. Delete the existing blockchain data by removing all files from
     ``/var/lib/sawtooth/``.

  #. Delete the logs by removing all files from ``/var/log/sawtooth/``.

  #. You can reuse the existing user and validator keys. If you want to start with
     new keys, delete the ``.priv`` and ``.pub`` files from
     ``/home/yourname/.sawtooth/keys/`` and ``/etc/sawtooth/keys/``.

* Gather networking information: For each node that will be on your
  network, gather the following information.

  * **Component bind string**: Where this validator will listen for incoming
    communication from this validator's components. You will set this value with
    ``--bind component`` when starting the validator. Default:
    ``tcp://127.0.0.1:4004``.

  * **Network bind string**: Where this validator will listen for incoming
    communication from other nodes (also called peers). You will set
    this value with ``--bind network`` when starting the validator.  Default:
    ``tcp://127.0.0.1:8800``.

  * **Public endpoint string**: The address that other peers should use to
    find the validator on this node. You will set this value with ``--endpoint`` when
    starting the validator. You will also specify this value in the peers list
    when starting a validator on another node. Default: ``tcp://127.0.0.1:8800``.

  * **Consensus endpoint string**: Where this validator will listen for incoming
    communication from the :term:`consensus engine`. You will set this value
    with ``--bind consensus`` when starting the validator.  Default:
    ``tcp://127.0.0.1:5050``.

  * **Peers list**: The addresses that this validator should use to connect to
    the other nodes (peers); that is, the public endpoint strings of
    those nodes. You will set this value with ``--peers`` when starting the
    validator. Default: none.

.. include:: ../_includes/about-network-bind-endpoint-strings.inc


.. _appdev-multinode-install-label:

Step 1: Install Sawtooth on All Nodes
-------------------------------------

Use these steps on each system to install Hyperledger Sawtooth.

.. note::

   * For PBFT consensus, you must install Sawtooth and generate keys for all
     nodes before continuing to step 3 (creating the genesis block on the
     first node).

   * For PoET consensus, you can choose to install Sawtooth on the other nodes
     after configuring and starting the first node.

.. include:: ../_includes/install-sawtooth.inc

.. _appdev-multinode-keys-label:

Step 2: Create User and Validator Keys
--------------------------------------

.. note::

   Skip this step if you are reusing an existing node that already has user and
   validator keys.

.. include:: ../_includes/generate-keys.inc


Step 3: Create the Genesis Block on the First Node
--------------------------------------------------

The first node creates the genesis block, which specifies the initial on-chain
settings for the network configuration. Other nodes access those settings when
they join the network.

**Prerequisites**:

* If you are reusing an existing node, make sure that you have deleted the
  blockchain data before continuing (as described in :ref:`the Ubuntu section's
  prerequisites <prereqs-multi-ubuntu-label>`).

* For PBFT, the genesis block requires the validator keys for at least four
  nodes (or all nodes in the initial network, if known). If you have not
  installed Sawtooth and generated keys on the other nodes, perform
  :ref:`Step 1 <appdev-multinode-install-label>` and
  :ref:`Step 2 <appdev-multinode-keys-label>`
  on those nodes, then gather the public keys from
  ``/etc/sawtooth/keys/validator.pub`` on each node.

.. include:: ../_includes/create-genesis-block.inc


Step 4. (PBFT Only) Configure Peers in Off-Chain Settings
---------------------------------------------------------

For PBFT, each node specify the peer nodes in the network, because a PBFT
network must be fully peered (all nodes must be directly connected). This
setting is in the off-chain
:doc:`validator configuration file <../sysadmin_guide/configuring_sawtooth/validator_configuration_file>`.

1. Create the validator configuration file by copying the example file.

   .. code-block:: console

      $ sudo cp -a /etc/sawtooth/validator.toml.example /etc/sawtooth/validator.toml

#. Use ``sudo`` to edit this file.

   .. code-block:: console

      $ sudo vi /etc/sawtooth/validator.toml

#. Locate the ``peering`` setting and make sure that it is set to ``static``
   (the default).

#. Find the ``peers`` setting and enter the URLs for other validators on the
   network.

   Use the format ``tcp://{hostname}:{port}`` for each peer. Specify multiple
   peers in a comma-separated list. For example:

   .. code-block:: ini

      peers = ["tcp://node1:8800", "tcp://node2:8800", "tcp://node3:8800"]

This setting will take effect when the validator starts.

.. note::

   For information about optional configuration settings, see
   :doc:`../sysadmin_guide/off_chain_settings`.

.. _start-sawtooth-first-node-label:

Step 5. Start Sawtooth on the First Node
----------------------------------------

This step shows how to start all Sawtooth components: the validator, REST API,
transaction processors, and consensus engine. Use a separate terminal window
to start each component.

1. Start the validator with the following command.

   Substitute your actual values for the component and network bind strings,
   public endpoint string, and peer list, as described in
   :ref:`prereqs-multi-ubuntu-label`.

   .. code-block:: console

      $ sudo -u sawtooth sawtooth-validator \
      --bind component:{component-bind-string} \
      --bind network:{network-bind-string} \
      --bind consensus:{consensus-bind-string} \
      --endpoint {public-endpoint-string} \
      --peers {peer-list}

   Specify multiple peers in a comma-separated list, as in this example:

        .. code-block:: none

           --peers tcp://203.0.113.0:8800,198.51.100.0:8800

   .. important::

      For PBFT, specify all known peers in the initial network. (PBFT requires
      at least four nodes.) If you want to add another PBFT node later, see
      :doc:`../sysadmin_guide/pbft_adding_removing_node`.

   The following example uses these values:

   * component bind address ``127.0.0.1:4004`` (the default value)
   * network bind address and endpoint ``192.0.2.0:8800``
     (a TEST-NET-1 example address)
   * consensus bind address and endpoint ``192.0.2.0:5050``
   * three peers at the public endpoints ``203.0.113.0:8800``,
     ``203.0.113.1:8800``, and ``203.0.113.2:8800``.

      .. code-block:: console

         $ sudo -u sawtooth sawtooth-validator \
         --bind component:tcp://127.0.0.1:4004 \
         --bind network:tcp://192.0.2.0:8800 \
         --bind consensus:tcp://192.0.2.0:5050 \
         --endpoint tcp://192.0.2.0:8800 \
         --peers tcp://203.0.113.0:8800,tcp://203.0.113.1:8800,tcp://203.0.113.2:8800

   Leave this window open; the validator will continue to display logging output
   as it runs.

#. Open a separate terminal window and start the REST API.

   .. code-block:: console

      $ sudo -u sawtooth sawtooth-rest-api -v

   If necessary, use the ``--connect`` option to specify a non-default value for
   the validator's component bind address and port, as described in
   :ref:`prereqs-multi-ubuntu-label`. The following example shows the default
   value:

      .. code-block:: none

         $ sudo -u sawtooth sawtooth-rest-api -v --connect 127.0.0.1:4004

   For more information, see :ref:`start-rest-api-label`.

#. Start the transaction processors. Open a separate terminal window to start
   each one.

   As with the previous command, use the ``--connect`` option for each command,
   if necessary, to specify a non-default value for validator's component bind
   address and port.

   .. code-block:: console

      $ sudo -u sawtooth settings-tp -v

   .. code-block:: console

      $ sudo -u sawtooth intkey-tp-python -v

   .. code-block:: console

      $ sudo -u sawtooth xo-tp-python -v

   .. note::

      The transaction processors for Integer Key (``intkey-tp-python``) and
      XO (``xo-tp-python``) are not required for a Sawtooth network, but are
      used for the other steps in this guide.

   For more information, see :ref:`start-tps-label`.

#. (PoET only) Also start the PoET Validator Registry transaction processor in
   a separate terminal window.

   .. code-block:: console

      $ sudo -u sawtooth poet-validator-registry-tp -v

#. Start the consensus engine in a separate terminal window.

   .. note::

      Change the ``--connect`` option, if necessary, to specify a non-default
      value for validator's consensus bind address and port.

   * For PBFT:

     .. code-block:: console

        $ sudo -u sawtooth pbft-engine -vv --connect tcp://localhost:5050

   * For PoET:

     .. code-block:: console

        $ sudo -u sawtooth poet-engine -vv --connect tcp://localhost:5050

   The terminal window displays log messages as the consensus engine connects to
   and registers with the validator. The output will be similar to this example:

   .. code-block:: console

      [2019-01-09 11:45:07.807 INFO     handlers] Consensus engine registered: ...

      DEBUG | {name:}:engine | Min: 0 -- Max: 0
      INFO  | {name:}:engine | Wait time: 0
      DEBUG | {name}::engine | Initializing block


Step 6. Test the First Node
---------------------------

Although the Sawtooth network is not fully functional until other nodes have
joined the network, you can use any or all of the following commands to verify
the REST API and check that the genesis block has been committed.

.. include:: ../_includes/testing-rest-api.inc

.. include:: ../_includes/sawtooth-block-list.inc

.. include:: ../_includes/sawtooth-settings-list-pbft.inc


.. _install-second-val-ubuntu-label:

Step 7: Start the Other Nodes
-----------------------------

After confirming basic functionality on the first node, start Sawtooth on all
other nodes in the initial network.

Use the procedure in :ref:`start-sawtooth-first-node-label`.

.. important::

   Be careful to specify the correct values for the component and network bind
   address, endpoint, and peers settings. Incorrect values could cause the
   network to fail.

   Start the same transaction processors that are running on the first
   node. For example, if you chose not to start ``intkey-tp-python``
   and ``xo-tp-python`` on the first node, do not start them on the other nodes.

When each node's validator fully starts, it will peer with the other running
nodes.

.. _confirm-nw-funct-ubuntu-label:

Step 8: Confirm Network Functionality
-------------------------------------

For the remaining steps, multiple nodes in the network must be running.

      * PBFT requires at least four nodes.

      * PoET requires at least three nodes.

1. To check whether peering has occurred on the network, submit a peers query
   to the REST API on the first node.

   Open a terminal window on the first node and run the following
   command.

     .. code-block:: console

        $ curl http://localhost:8008/peers

   .. note::

      This environment runs a local REST API on each node. For
      a node that is not running a local REST API, you must replace
      ``localhost:8008`` with the externally advertised IP address and
      port.  (Non-default values are set with the ``--bind`` option when
      starting the REST API.)

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

#. Run the following Sawtooth commands on a node to show the other
   nodes on the network.

   a. Run ``sawtooth peer list`` to show the peers of a particular node.

   b. Run ``sawnet peers list`` to display a complete graph of peers on the
      network (available in Sawtooth release 1.1 and later).

#. Verify that transactions are being processed correctly.

   a. Submit a transaction to the REST API on the first node. This
      example sets a key named ``MyKey`` to the value 999.

      Run the following command in a terminal window on the first node.

      .. code-block:: console

         $ intkey set MyKey 999

   #. Watch for this transaction to appear on the other node. The
      following command requests the value of ``MyKey`` from the REST API on the
      that node.

      Open a terminal window on another node to run the following
      command.


      .. code-block:: console

         $ intkey show MyKey
         MyKey: 999


.. _configure-txn-procs-ubuntu-label:

Step 9. (Optional) Configure the Allowed Transaction Types
----------------------------------------------------------

By default, a validator accepts transactions from any transaction processor.
However, Sawtooth allows you to limit the types of transactions that can be
submitted.

For this procedure, see :doc:`../sysadmin_guide/setting_allowed_txns` in the
System Administrator's Guide.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
