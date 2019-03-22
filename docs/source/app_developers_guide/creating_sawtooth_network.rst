***************************
Creating a Sawtooth Network
***************************

This procedure describes how to create a Sawtooth network with multiple
validator nodes. It creates an application development environment that is
similar to the single-node environment in :doc:`installing_sawtooth`, but with
a different consensus mechanism to support additional nodes.

You can install and run a multiple-node Sawtooth application development
environment on one of the following platforms:

* Docker: Run a Sawtooth network from prebuilt
  `Docker <https://www.docker.com/>`_ containers.

* Ubuntu: Install Sawtooth natively using
  `Ubuntu 16.04 <https://www.ubuntu.com/>`_. You will add a node to an existing
  application development environment that is described in :doc:`ubuntu`, but
  you will delete all existing blockchain data, including the genesis block.

* Kubernetes: Run a Sawtooth network in a `Kubernetes <https://kubernetes.io>`_
  cluster inside a virtual machine on your computer.

.. note::

   The guides in this chapter set up an environment with multiple Sawtooth
   validator nodes. For a single-node environment, see
   :doc:`installing_sawtooth`.

To get started, choose the guide for the platform of your choice:

* :ref:`proc-multi-docker-label`

* :ref:`proc-multi-ubuntu-label`

* :ref:`proc-multi-kube-label`


About Sawtooth Networks
=======================

A Sawtooth network has the following requirements:

* Each host system (physical computer, virtual machine, set of Docker
  containers, or Kubernetes pod) must run one validator, an optional REST API,
  and an identical set of transaction processors.

  This environment includes the Sawtooth REST API on all validator nodes.
  However, an application could provide a custom REST API (or no REST API). See
  `Sawtooth Supply Chain <https://github.com/hyperledger/sawtooth-supply-chain>`_
  for an example of a custom REST API.

* Each validator node must advertise a routable address. The Docker and
  Kubernetes platforms provide preconfigured settings. For the Ubuntu platform,
  you must follow the instructions in this procedure to provide this information
  when starting the validator.

* The authorization type must be the same on all nodes: either ``trust``
  (default) or ``challenge``. This application development environment uses
  ``trust`` authorization.

* The genesis block is created for the first validator node only. It includes
  on-chain configuration settings that will be available to the new validator
  nodes once they join the network.

.. note::

   The first validator node on the network has no special meaning, other than
   being the node that created the genesis block. Sawtooth has no concept of a
   "head node" or "master node". Once multiple nodes are up and running, each
   node has the same genesis block and treats all other nodes as peers.


.. _proc-multi-docker-label:

Docker: Start a Multiple-node Sawtooth Network
==============================================

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

Like the single-node environment, this environment uses serial transaction
processing and static peering. However, it has the following differences:

* PoET simulator consensus instead of dev mode, because dev mode's random-leader
  consensus is not recommended for multi-node or production networks. Sawtooth
  offers two versions of :term:`PoET` consensus. PoET-SGX relies on Intel
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

      sawtooth.consensus.algorithm: poet
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


.. _proc-multi-ubuntu-label:

Ubuntu: Add a Node to the Single-Node Environment
=================================================

This procedure describes how to add a second validator node to an existing
single-node application development environment, as described in :doc:`ubuntu`.
You will stop the Sawtooth components on the first node and delete the
existing blockchain data, then create a new genesis block that specifies PoET
simulator consensus and related settings. All nodes on the network will run four
transaction processors (Settings, IntegerKey, XO, and PoET Validator Registry).


About the Sawtooth Network Environment
--------------------------------------

The following figure shows an example network with two validator nodes:

.. figure:: ../images/appdev-environment-two-nodes.*
   :width: 100%
   :align: center
   :alt: Ubuntu: Sawtooth network with two nodes

Like the single-node environment, this environment uses serial transaction
processing and static peering. However, it has the following differences:

* PoET simulator consensus instead of dev mode, because dev mode's random-leader
  consensus is not recommended for multi-node or production networks. Sawtooth
  offers two versions of :term:`PoET` consensus. PoET-SGX relies on Intel
  Software Guard Extensions (SGX) to implement a leader-election lottery system.
  PoET simulator provides the same consensus algorithm on an SGX simulator.

* An additional transaction processor, PoET Validator Registry, handles PoET
  settings for a multiple-node network.

.. _prereqs-multi-ubuntu-label:

Prerequisites
-------------

This procedure assumes that you have created a working (runnable) validator node
with a validator, REST API, and the Settings, IntegerKey, and XO transaction
processors. For more information, see :doc:`ubuntu`.

For each validator node that will be on your network, gather the following
information:

* **Component bind string**: Where this validator will listen for incoming
  communication from this validator's components. You will set this value with
  ``--bind component`` when starting the validator. Default:
  ``tcp://127.0.0.1:4004``.

* **Network bind string**: Where this validator will listen for incoming
  communication from other validator nodes (also called peers). You will set
  this value with ``--bind network`` when starting the validator.  Default:
  ``tcp://127.0.0.1:8800``.

* **Public endpoint string**: The address that other peers should use to
  find this validator node. You will set this value with ``--endpoint`` when
  starting the validator. You will also specify this value in the peers list
  when starting a validator on another node. Default: ``tcp://127.0.0.1:8800``.

* **Peers list**: The addresses that this validator should use to connect to
  the other validator nodes (peers); that is, the public endpoint strings of
  those nodes. You will set this value with ``--peers`` when starting the
  validator. Default: none.

.. _about-bind-strings-label:

About component and network bind strings
++++++++++++++++++++++++++++++++++++++++

For the network bind string and component bind string, you would typically use
a specific network interface that you want to bind to.
The ``ifconfig`` command provides an easy way to determine what this interface
should be. ``ifconfig`` displays the network interfaces on your host system,
along with additional information about the interfaces. For example:

.. code-block:: console

   $ ifconfig
   eth0      Link encap:Ethernet  HWaddr ...
             inet addr:...  Bcast:...  Mask:255.255.0.0
             UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
             RX packets:17964 errors:0 dropped:0 overruns:0 frame:0
             TX packets:6134 errors:0 dropped:0 overruns:0 carrier:0
             collisions:0 txqueuelen:0
             RX bytes:26335425 (26.3 MB)  TX bytes:338394 (338.3 KB)
   lo        Link encap:Local Loopback
             inet addr:127.0.0.1  Mask:255.0.0.0
             UP LOOPBACK RUNNING  MTU:65536  Metric:1
             RX packets:0 errors:0 dropped:0 overruns:0 frame:0
             TX packets:0 errors:0 dropped:0 overruns:0 carrier:0
             collisions:0 txqueuelen:1
             RX bytes:0 (0.0 B)  TX bytes:0 (0.0 B)

This example output shows that ``eth0`` is a network interface that has access
to the Internet. In this case, you could use one of the following:

* If you would like the validator node to accept connections from other
  validator nodes on the network behind ``eth0``, you could specify a
  network bind string such as ``tcp://eth0:8800``.

* If you would like the validator node to accept only connections from local
  Sawtooth components, you could specify the component bind string
  ``tcp://lo:4004``. Note that this is equivalent to ``tcp://127.0.0.1:4004``.

For more information on how to specify the component and network bind strings,
see "Assigning a local address to a socket" in the
`zmq-tcp API Reference <http://api.zeromq.org/4-2:zmq-tcp>`_.

.. _about-endpoint-string-label:

About the public endpoint string
++++++++++++++++++++++++++++++++

The correct value for your public endpoint string depends on your network
configuration.

* If this network is for development purposes and all of the validator nodes
  will be on the same local network, the IP address returned by ``ifconfig``
  should work as your public endpoint string.

* If part of your network is behind a NAT or firewall, or if you want to start
  up a public network on the Internet, you must determine the correct routable
  values for all the validator nodes in your network.

  Determining these values for a distributed or production network is an
  advanced networking topic that is beyond the scope of this guide. Contact your
  network administrator for help with this task.

For information on how to specify the public endpoint string, see "Connecting
a socket" in the `zmq-tcp API Reference <http://api.zeromq.org/4-2:zmq-tcp>`_.


Step 1: Configure the Network on the First Node
-----------------------------------------------

This step assumes an existing application development environment as described
in :doc:`ubuntu`.

#. If the first validator node is running, stop the Sawtooth components
   (validator, REST API, and transaction processors), as described
   in :ref:`stop-sawtooth-ubuntu-label`.

#. Delete any existing blockchain data by removing all files from
   ``/var/lib/sawtooth/``.

#. (Optional) Delete existing logs by removing all files from
   ``/var/log/sawtooth/``.

#. Ensure that the required user and validator keys exist:

   .. code-block:: console

      $ ls ~/.sawtooth/keys/
      {yourname}.priv    {yourname}.pub

      $ ls /etc/sawtooth/keys/
      validator.priv   validator.pub

   If these key files do not exist, create them as described in
   :ref:`generate-user-key-ubuntu`
   and :ref:`generate-root-key-ubuntu`.

#. Create a batch to initialize the Settings transaction family in the genesis
   block.

   .. code-block:: console

      $ sawset genesis -k /etc/sawtooth/keys/validator.priv -o config-genesis.batch

#. Create a batch to initialize the PoET consensus settings. This command sets
   the consensus algorithm to PoET simulator, and then applies the required
   settings.

   .. code-block:: console

      $ sawset proposal create -k /etc/sawtooth/keys/validator.priv \
      -o config.batch \
      sawtooth.consensus.algorithm.name=PoET \
      sawtooth.consensus.algorithm.version=0.1 \
      sawtooth.poet.report_public_key_pem="$(cat /etc/sawtooth/simulator_rk_pub.pem)" \
      sawtooth.poet.valid_enclave_measurements=$(poet enclave measurement) \
      sawtooth.poet.valid_enclave_basenames=$(poet enclave basename)

#. Create a batch to register the first validator with the Validator
   Registry. Without this command, the validator would not be able to publish
   any blocks.

   .. code-block:: console

      $ poet registration create -k /etc/sawtooth/keys/validator.priv -o poet.batch

#. (Optional) Create a batch to configure optional PoET settings.  This example
   shows the default settings.

   .. code-block:: console

      $ sawset proposal create -k /etc/sawtooth/keys/validator.priv \
      -o poet-settings.batch \
      sawtooth.poet.target_wait_time=5 \
      sawtooth.poet.initial_wait_time=25 \
      sawtooth.publisher.max_batches_per_block=100

#. Combine the previously created batches into a single genesis batch that will
   be committed in the genesis block.

   .. code-block:: console

      $ sawadm genesis config-genesis.batch config.batch poet.batch poet-settings.batch

#. Use the following command to start the validator on the first node.
   Substitute your actual values for the component and network bind strings,
   public endpoint string, and peer list, as described in
   :ref:`prereqs-multi-ubuntu-label`.

   .. code-block:: console

      $ sudo -u sawtooth sawtooth-validator \
      --bind component:{component-bind-string} \
      --bind network:{network-bind-string} \
      --endpoint {public-endpoint-string} \
      --peers {peer-list}

   For example, the following command uses the component bind address
   ``127.0.0.1:4004`` (the default value), the network bind address and endpoint
   ``192.0.2.0:8800`` (a TEST-NET-1 example address), and one peer at the public
   endpoint ``203.0.113.0:8800``.

      .. code-block:: console

         $ sudo -u sawtooth sawtooth-validator \
         --bind component:tcp://127.0.0.1:4004 \
         --bind network:tcp://192.0.2.0:8800 \
         --endpoint tcp://192.0.2.0:8800 \
         --peers tcp://203.0.113.0:8800

   .. note::

      Specify multiple peers in a comma-separated list, as in this example:

        .. code-block:: none

           --peers tcp://203.0.113.0:8800,198.51.100.0:8800

#. Open a separate terminal window and start the REST API on the first validator
   node.

   .. code-block:: console

      $ sudo -u sawtooth sawtooth-rest-api -v

   If necessary, use the ``--connect`` option to specify a non-default value for
   the validator's component bind address and port, as described in
   :ref:`prereqs-multi-ubuntu-label`. The following example shows the default
   value:

      .. code-block:: none

         $ sudo -u sawtooth sawtooth-rest-api -v --connect 127.0.0.1:4004

   For more information, see :ref:`start-rest-api-label`.

#. Start the transaction processors on the first validator node. Open a separate
   terminal window to start each component.

   As with the previous command, use the ``--connect`` option for each command,
   if necessary, to specify a non-default value for validator's component bind
   address and port.

   .. code-block:: console

      $ sudo -u sawtooth settings-tp -v

   .. code-block:: console

      $ sudo -u sawtooth intkey-tp-python -v

   .. code-block:: console

      $ sudo -u sawtooth xo-tp-python -v

   .. code-block:: console

      $ sudo -u sawtooth poet-validator-registry-tp -v

   .. note::

      This network requires the Settings transaction processor, ``settings-tp``,
      and the PoET Validator Registry transaction processor,
      ``poet-validator-registry-tp``.
      The other transaction processors (``intkey-tp-python`` and
      ``xo-tp-python``) are not required, but are used for the other tutorials
      in this guide. Note that each node in the network must run the same
      transaction processors.

   For more information, see :ref:`start-tps-label`.

.. _install-second-val-ubuntu-label:

Step 2: Set Up the Second Validator Node
----------------------------------------

#. Install Sawtooth on the second node, as described in Step 1 of
   :doc:`ubuntu`.

#. Create your user key:

   .. code-block:: console

      $ sawtooth keygen
      writing file: /home/{yourname}/.sawtooth/keys/{yourname}.priv
      writing file: /home/{yourname}/.sawtooth/keys/{yourname}.pub

#. Create the root key for the validator:

   .. code-block:: console

      $ sudo sawadm keygen
      writing file: /etc/sawtooth/keys/validator.priv
      writing file: /etc/sawtooth/keys/validator.pub

If you have additional nodes, repeat this step on those nodes.

Step 3: Start the Second Validator Node
----------------------------------------

This step starts all the Sawtooth components on the second node. When the second
validator fully starts, it will peer with the first validator node.

#. Open a new terminal window on the second node, then use the following command
   to start the validator. Use the actual values for the component and network
   bind strings, public endpoint string, and peer list, as described in
   :ref:`prereqs-multi-ubuntu-label`.

   .. code-block:: console

      $ sudo -u sawtooth sawtooth-validator \
      --bind component:{component-bind-string} \
      --bind network:{network-bind-string} \
      --endpoint {public-endpoint-string} \
      --peers {peer-list}

   For example, the following command uses the component bind address
   ``127.0.0.1:4004`` (the default value), the network bind address and
   endpoint ``203.0.113.0:8800`` (a TEST-NET-3 example address), and a peer (the
   first node) at the public endpoint ``192.0.2.0:8800``.

      .. code-block:: console

         $ sudo -u sawtooth sawtooth-validator \
         --bind component:tcp://127.0.0.1:4004 \
         --bind network:tcp://203.0.113.0:8800 \
         --endpoint tcp://203.0.113.0:8800 \
         --peers tcp://192.0.2.0:8800

   .. note::

      Specify multiple peers in a comma-separated list, as in this example:

        .. code-block:: none

           --peers tcp://192.0.2.0:8800,tcp://198.51.100.0:8800

#. Open a separate terminal window and start the REST API on the second
   validator node.

   .. code-block:: console

      $ sudo -u sawtooth sawtooth-rest-api -v

   If necessary, use the ``--connect`` option to specify a non-default value for
   the validator's component bind address and port, as described in
   :ref:`prereqs-multi-ubuntu-label`. The following example shows the default
   value:

      .. code-block:: none

         $ sudo -u sawtooth sawtooth-rest-api -v --connect 127.0.0.1:4004

   For more information, see :ref:`start-rest-api-label`.

#. Start the transaction processors on the second validator node. Open a
   separate terminal window to start each component.

   As with the previous command, use the ``--connect`` option for each command,
   if necessary, to specify a non-default value for validator's component bind
   address and port.

   .. Important::

      Start the same transaction processors that are running on the first
      validator node. For example, if you chose not to start
      ``intkey-tp-python`` and ``xo-tp-python`` on the first node, do not start
      them on this node.

   .. code-block:: console

      $ sudo -u sawtooth settings-tp -v

   .. code-block:: console

      $ sudo -u sawtooth intkey-tp-python -v

   .. code-block:: console

      $ sudo -u sawtooth xo-tp-python -v

   .. code-block:: console

      $ sudo -u sawtooth poet-validator-registry-tp -v

   For more information, see :ref:`start-tps-label`.

If you have additional nodes in the network, repeat this step on those nodes.


.. _confirm-nw-funct-ubuntu-label:

Step 4: Confirm Network Functionality
-------------------------------------

#. To check whether peering has occurred on the network, submit a peers query
   to the REST API on the first validator node.

   Open a terminal window on the first validator node and run the following
   command.

     .. code-block:: console

        $ curl http://localhost:8008/peers

   .. note::

      This environment runs a local REST API on each validator node. For
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

#. (Optional) You can also run the following Sawtooth commands on a validator
   node to show the other nodes on the network.

   a. Run ``sawtooth peer list`` to show the peers of a particular node.

   b. Run ``sawnet peers list`` to display a complete graph of peers on the
      network (available in Sawtooth release 1.1 and later).

#. Submit a transaction to the REST API on the first validator node. This
   example sets a key named ``MyKey`` to the value 999.

   Run the following command in a terminal window on the first validator node.

     .. code-block:: console

        $ intkey set MyKey 999

#. Watch for this transaction to appear on the second validator node. The
   following command requests the value of ``MyKey`` from the REST API on the
   second validator node.

   Open a terminal window on the second validator node to run the
   following command.


      .. code-block:: console

         $ intkey show MyKey
         MyKey: 999


.. _configure-txn-procs-ubuntu-label:

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
handles on-chain configuration settings. You can use the ``sawset`` command to
create and submit a batch of transactions containing the configuration change.

Use the following steps to create and submit a batch containing the new on-chain
setting.

1. Open a terminal window on the first validator node (node 0).  The next
   command requires the validator key that was generated on that node.

#. Use the ``sawset`` command to create and submit a batch of transactions
   containing the configuration change.

   .. code-block:: console

      # sawset proposal create --key /etc/sawtooth/keys/validator.priv \
      sawtooth.validator.transaction_families='[{"family": "intkey", "version": "1.0"}, {"family":"sawtooth_settings", "version":"1.0"}, {"family":"xo", "version":"1.0"}, {"family":"sawtooth_validator_registry", "version":"1.0"}]'

   This command sets ``sawtooth.validator.transaction_families`` to a JSON array
   that specifies the family name and version of each allowed transaction
   processor (defined in the transaction header of each family's
   :doc:`transaction family specification <../transaction_family_specifications>`).

#. After this command runs, a ``TP_PROCESS_REQUEST`` message appears in the log
   for the Settings transaction processor.

   You can examine the log file,
   ``/var/log/sawtooth/logs/settings-{xxxxxxx}-debug.log``, on any node. (Each
   Settings log file has a unique string in the name.) The messages will
   resemble this example:

   .. code-block:: none

      [20:07:58.039 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
      [20:07:58.190 [MainThread] handler INFO] Setting setting sawtooth.validator.transaction_families changed from None to [{"family": "intkey", "version": "1.0"}, {"family":"sawtooth_settings", "version":"1.0"}, {"family":"xo", "version":"1.0"}, {"family":"sawtooth_validator_registry", "version":"1.0"}]

#. Run the following command to check the setting change.

   .. code-block:: console

      # sawtooth settings list

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


.. _proc-multi-kube-label:

Kubernetes: Start a Multiple-node Sawtooth Network
==================================================

This procedure explains how to create a Hyperledger Sawtooth network with
`Kubernetes <https://kubernetes.io/docs/concepts/overview/what-is-kubernetes/>`__.
This environment uses `Minikube <https://kubernetes.io/docs/setup/minikube/>`_
to deploy Sawtooth as a containerized application in a local Kubernetes cluster
inside a virtual machine (VM) on your computer.

.. note::

   This environment has five Sawtooth validator nodes. For a single-node
   environment, see :doc:`installing_sawtooth`.

This procedure walks you through the following tasks:

 * Installing ``kubectl`` and Minikube
 * Starting Minikube
 * Starting Sawtooth in a Kubernetes cluster
 * Connecting to the Sawtooth shell containers
 * Verifying network and blockchain functionality
 * Stopping Sawtooth and deleting the Kubernetes cluster

Prerequisites
-------------

This application development environment requires
`kubectl <https://kubernetes.io/docs/concepts/overview/object-management-kubectl/overview/>`_
and
`Minikube <https://kubernetes.io/docs/setup/minikube/>`_ with a supported VM
hypervisor, such as VirtualBox.


About the Kubernetes Sawtooth Network Environment
-------------------------------------------------

This environment is a network of five Sawtooth node. Each node has a
:term:`validator`, a :term:`REST API`, and four
:term:`transaction processors<transaction processor>`. This environment uses
:ref:`PoET mode consensus <dynamic-consensus-label>`,
:doc:`serial transaction processing <../architecture/scheduling>`,
and static peering (all-to-all)

.. figure:: ../images/appdev-environment-multi-node-kube.*
   :width: 100%
   :align: center
   :alt: Kubernetes: Sawtooth network with five nodes

The Kubernetes cluster has a pod for each Sawtooth node. On each pod, there are
containers for each Sawtooth component. The Sawtooth nodes are connected in
an all-to-all peering relationship.

After the cluster is running, you can use the `Kubernetes dashboard
<https://kubernetes.io/docs/tasks/access-application-cluster/web-ui-dashboard/>`_
to view pod status, container names, Sawtooth log files, and more.

This example environment includes the following transaction processors:

 * :doc:`Settings <../transaction_family_specifications/settings_transaction_family>`
   handles Sawtooth's on-chain settings. The Settings transaction processor,
   ``settings-tp``, is required for this environment.

 * :doc:`PoET Validator Registry <../transaction_family_specifications/validator_registry_transaction_family>`
   configures PoET consensus and handles a network with multiple validators.

 * :doc:`IntegerKey <../transaction_family_specifications/integerkey_transaction_family>`
   is a basic application (also called transaction family) that introduces
   Sawtooth functionality. The ``sawtooth-intkey-tp-python`` transaction
   processor works with the ``int-key`` client, which has shell commands to
   perform integer-based transactions.

 * :doc:`XO <../transaction_family_specifications/xo_transaction_family>`
   is a simple application for playing a game of tic-tac-toe on the blockchain.
   The ``sawtooth-xo-tp-python`` transaction processor works with the ``xo``
   client, which has shell commands to define players and play a game.
   XO is described in a later tutorial.

.. note::

   Sawtooth provides the Settings transaction processor as a reference
   implementation. In a production environment, you must always run the
   Settings transaction processor or an equivalent that supports the
   :doc:`Sawtooth methodology for storing on-chain configuration settings
   <../transaction_family_specifications/settings_transaction_family>`.


Step 1: Install kubectl and Minikube
------------------------------------

This step summarizes the Kubernetes installation procedures. For more
information, see the
`Kubernetes documentation <https://kubernetes.io/docs/tasks/>`_.

1. Install a virtual machine (VM) hypervisor such as VirtualBox, VMWare,
   KVM-QEMU, or Hyperkit. The steps in this procedure assume
   `VirtualBox <https://www.virtualbox.org/wiki/Downloads>`_ (the default).

#. Install the ``kubectl`` command as described in the Kubernetes document
   `Install kubectl <https://kubernetes.io/docs/tasks/tools/install-kubectl/>`_.

   * Linux quick reference:

     .. code-block:: none

        $ curl -Lo kubectl https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl \
        && chmod +x kubectl && sudo cp kubectl /usr/local/bin/ && rm kubectl

   * Mac quick reference:

     .. code-block:: none

        $ curl -Lo kubectl https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/darwin/amd64/kubectl \
        && chmod +x kubectl && sudo cp kubectl /usr/local/bin/ && rm kubectl

#. Install ``minikube`` as described in the Kubernetes document
   `Install Minikube <https://kubernetes.io/docs/tasks/tools/install-minikube/>`_.

   * Linux quick reference:

     .. code-block:: none

        $ curl -Lo minikube https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64 \
        && chmod +x minikube && sudo cp minikube /usr/local/bin/ && rm minikube

   * Mac quick reference:

     .. code-block:: none

        $ curl -Lo minikube https://storage.googleapis.com/minikube/releases/latest/minikube-darwin-amd64 \
        && chmod +x minikube && sudo mv minikube /usr/local/bin/


Step 2: Start and Test Minikube
-------------------------------

This step summarizes the procedure to start Minikube and test basic
functionality. If you have problems, see the Kubernetes document
`Running Kubernetes Locally via Minikube
<https://kubernetes.io/docs/setup/minikube/>`_.

1. Start Minikube.

   .. code-block:: console

      $ minikube start

#. Start Minikube's "Hello, World" test cluster, ``hello-minikube``.

   .. code-block:: console

      $ kubectl run hello-minikube --image=k8s.gcr.io/echoserver:1.10 --port=8080

      $ kubectl expose deployment hello-minikube --type=NodePort

#. Check the list of pods.

   .. code-block:: console

      $ kubectl get pods

   After the pod is up and running, the output of this command should display a
   pod starting with ``hello-minikube...``.

#. Run a ``curl`` test to the cluster.

   .. code-block:: none

      $ curl $(minikube service hello-minikube --url)

#. Remove the ``hello-minikube`` cluster.

   .. code-block:: console

      $ kubectl delete services hello-minikube

      $ kubectl delete deployment hello-minikube


Step 3: Download the Sawtooth Configuration File
------------------------------------------------

Download the Kubernetes configuration (kubeconfig) file for a Sawtooth network,
`sawtooth-kubernetes-default-poet.yaml <./sawtooth-kubernetes-default-poet.yaml>`_.

This kubeconfig file creates a Sawtooth network with five pods, each running a
Sawtooth validator node. The pods are numbered from 0 to 4.

The configuration file also specifies the container images to download (from
DockerHub) and the network settings needed for the containers to communicate
correctly.


Step 4: Start the Sawtooth Cluster
----------------------------------

.. note::

   The Kubernetes configuration file handles the Sawtooth startup steps such as
   generating keys and creating a genesis block. To learn about the full
   Sawtooth startup process, see :doc:`ubuntu`.

Use these steps to start the Sawtooth network:

1. Change your working directory to the same directory where you saved the
   configuration file.

#. Make sure that Minikube is running.

   .. code-block:: console

      $ minikube status
      minikube: Running
      cluster: Running
      kubectl: Correctly Configured: pointing to minikube-vm at 192.168.99.100

   If necessary, start it with ``minikube start``.

#. Start Sawtooth in a local Kubernetes cluster.

   .. _restart-kube-label:

   .. code-block:: console

      $ kubectl apply -f sawtooth-kubernetes-default-poet.yaml
      deployment.extensions/sawtooth-0 created
      service/sawtooth-0 created
      deployment.extensions/sawtooth-1 created
      service/sawtooth-1 created
      deployment.extensions/sawtooth-2 created
      service/sawtooth-2 created
      deployment.extensions/sawtooth-3 created
      service/sawtooth-3 created
      deployment.extensions/sawtooth-4 created
      service/sawtooth-4 created

#. (Optional) Start the Minikube dashboard.

   .. code-block:: console

      $ minikube dashboard

   This command opens the dashboard in your default browser. The overview page
   shows the Sawtooth deployment, pods, and replica sets.

.. important::

   Any work done in this environment will be lost once you stop Minikube and
   delete the Sawtooth cluster. In order to use this environment for application
   development, or to start and stop Sawtooth nodes (and pods), you would need
   to take additional steps, such as defining volume storage. See the
   `Kubernetes documentation <https://kubernetes.io/docs/home/>`__ for more
   information.


.. _confirm-func-kube-label:

Step 5: Confirm Network and Blockchain Functionality
----------------------------------------------------

1. Connect to the shell container on the first pod.

     .. code-block:: none

        $ kubectl exec -it $(kubectl get pods | awk '/sawtooth-0/{print $1}') --container sawtooth-shell -- bash

        root@sawtooth-0#

   .. note::

      In this procedure, the prompt ``root@sawtooth-0#`` marks the commands that should
      be run on the Sawtooth node in pod 0. (The actual prompt is similar to
      ``root@sawtooth-0-5ff6d9d578-5w45k:/#``.)

#. Display the list of blocks on the Sawtooth blockchain.

     .. code-block:: none

        root@sawtooth-0# sawtooth block list

   The output will be similar to this example:

     .. code-block:: console

        NUM  BLOCK_ID                                                                                                                          BATS  TXNS  SIGNER
        2    f40b90d06b4a9074af2ab09e0187223da7466be75ec0f472f2edd5f22960d76e402e6c07c90b7816374891d698310dd25d9b88dce7dbcba8219d9f7c9cae1861  3     3     02e56e...
        1    4d7b3a2e6411e5462d94208a5bb83b6c7652fa6f4c2ada1aa98cabb0be34af9d28cf3da0f8ccf414aac2230179becade7cdabbd0976c4846990f29e1f96000d6  1     1     034aad...
        0    0fb3ebf6fdc5eef8af600eccc8d1aeb3d2488992e17c124b03083f3202e3e6b9182e78fef696f5a368844da2a81845df7c3ba4ad940cee5ca328e38a0f0e7aa0  3     11    034aad...

   Block 0 is the :term:`genesis block`. The other two blocks contain
   transactions for on-chain settings, such as setting PoET consensus.

#. In a separate terminal window, connect to a different pod (such as pod 1) and
   verify that it has joined the Sawtooth network.

     .. code-block:: none

        $ kubectl exec -it $(kubectl get pods | awk '/sawtooth-1/{print $1}') --container sawtooth-shell -- bash

        root@sawtooth-1#

   .. note::

      The prompt ``root@sawtooth-1#`` marks the commands that should be run on
      the Sawtooth node in pod 1.

#. Display the list of blocks on the second pod.

     .. code-block:: none

        root@sawtooth-1# sawtooth block list

   You should see the same list of blocks with the same block IDs, as in this
   example:

     .. code-block:: console

        NUM  BLOCK_ID                                                                                                                          BATS  TXNS  SIGNER
        2    f40b90d06b4a9074af2ab09e0187223da7466be75ec0f472f2edd5f22960d76e402e6c07c90b7816374891d698310dd25d9b88dce7dbcba8219d9f7c9cae1861  3     3     02e56e...
        1    4d7b3a2e6411e5462d94208a5bb83b6c7652fa6f4c2ada1aa98cabb0be34af9d28cf3da0f8ccf414aac2230179becade7cdabbd0976c4846990f29e1f96000d6  1     1     034aad...
        0    0fb3ebf6fdc5eef8af600eccc8d1aeb3d2488992e17c124b03083f3202e3e6b9182e78fef696f5a368844da2a81845df7c3ba4ad940cee5ca328e38a0f0e7aa0  3     11    034aad...

#. (Optional) You can repeat the previous two steps on the other pods to verify
   that they have the same block list. To connect to a different pod, replace
   the `N` (in ``sawtooth-N``) in the following command with the pod number.
   command:

     .. code-block:: none

        $ kubectl exec -it $(kubectl get pods | awk '/sawtooth-N/{print $1}') --container sawtooth-shell -- bash

#. (Optional) You can also connect to the shell container of any pod, and
   run the following Sawtooth commands to show the other nodes on the network.

   a. Run ``sawtooth peer list`` to show the peers of a particular node.

   b. Run ``sawnet peers list`` to display a complete graph of peers on the
      network (available in Sawtooth release 1.1 and later).

#. You can submit a transaction on one Sawtooth node, then look for the results
   of that transaction on another node.

   a. From the shell container on pod 0, use the ``intkey set`` command to
      submit a transaction on the first validator node. This example sets a key
      named ``MyKey`` to the value 999.

        .. code-block:: console

           root@sawtooth-0# intkey set MyKey 999
           {
             "link":
             "http://127.0.0.1:8008/batch_statuses?id=1b7f121a82e73ba0e7f73de3e8b46137a2e47b9a2d2e6566275b5ee45e00ee5a06395e11c8aef76ff0230cbac0c0f162bb7be626df38681b5b1064f9c18c76e5"
             }

   b. From the shell container on a different pod (such as pod 1), check that
      the value has been changed on that validator node.

        .. code-block:: console

           root@sawtooth-1# intkey show MyKey
           MyKey: 999

#. You can check whether a Sawtooth component is running by connecting to a
   different container, then running the ``ps`` command. The container names are
   available in the kubeconfig file or on a pod's page on the Kubernetes
   dashboard.

   The following example connects to pod 3's PoET Validator Registry container
   (``sawtooth-poet-validator-registry-tp``), then displays the list of running
   process.

   .. code-block:: console

      $ kubectl exec -it $(kubectl get pods | awk '/sawtooth-3/{print $1}') --container sawtooth-poet-validator-registry-tp -- bash

      root@sawtooth-3# ps --pid 1 fw
        PID TTY      STAT   TIME COMMAND
          1 ?        Ssl    0:02 /usr/bin/python3 /usr/bin/poet-validator-registry-tp -vv -C tcp://sawtooth-3-5bd565ff45-2klm7:4004

At this point, your environment is ready for experimenting with Sawtooth.

For more ways to test basic functionality, see the Kubernetes section of
"Setting Up a Sawtooth Application Development Environment".

* To use Sawtooth client commands to view block information and check state
  data, see :ref:`sawtooth-client-kube-label`.

* For information on the Sawtooth logs, see :ref:`examine-logs-kube-label`.


.. _configure-txn-procs-kube-label:

Step 6. Configure the Allowed Transaction Types (Optional)
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
handles on-chain configuration settings. You can use the ``sawset`` command to
create and submit a batch of transactions containing the configuration change.

Use the following steps to create and submit a batch containing the new setting.

1. Connect to the validator container of the first node
   (``sawtooth-0-{xxxxxxxx}``). The next command requires the validator key that
   was generated in that container.

   .. code-block:: console

      $ kubectl exec -it $(kubectl get pods | awk '/sawtooth-0/{print $1}') --container sawtooth-validator -- bash
      root@sawtooth-0#

#. Run the following command from the validator container:

   .. code-block:: console

      root@sawtooth-0# sawset proposal create --key /etc/sawtooth/keys/validator.priv sawtooth.validator.transaction_families='[{"family": "intkey", "version": "1.0"}, {"family":"sawtooth_settings", "version":"1.0"}, {"family":"xo", "version":"1.0"}, {"family":"sawtooth_validator_registry", "version":"1.0"}]'

   This command sets ``sawtooth.validator.transaction_families`` to a JSON array
   that specifies the family name and version of each allowed transaction
   processor (defined in the transaction header of each family's
   :doc:`transaction family specification <../transaction_family_specifications>`).

#. After this command runs, a ``TP_PROCESS_REQUEST`` message appears in the log
   for the Settings transaction processor.

   * You can use the Kubernetes dashboard to view this log message:

     a. From the Overview page, scroll to the list of pods and click on any pod
        name.

     #. On the pod page, click :guilabel:`LOGS` (in the top right).

     #. On the pod's log page, select logs from ``sawtooth-settings-tp``, then
        scroll to the bottom of the log. The message will resemble this example:

        .. code-block:: none

           [2018-09-05 20:07:41.903 DEBUG    core] received message of type: TP_PROCESS_REQUEST
   * You can also connect to the ``sawtooth-settings-tp`` container on any pod,
     then examine ``/var/log/sawtooth/logs/settings-{xxxxxxx}-debug.log``. (Each
     Settings log file has a unique string in the name.) The messages will
     resemble this example:

     .. code-block:: none

         .
         .
         .
        [20:07:58.039 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
        [20:07:58.190 [MainThread] handler INFO] Setting setting sawtooth.validator.transaction_families changed from None to [{"family": "intkey", "version": "1.0"}, {"family":"sawtooth_settings", "version":"1.0"}, {"family":"xo", "version":"1.0"}, {"family":"sawtooth_validator_registry", "version":"1.0"}]

#. Run the following command to check the setting change. You can use any
   container, such as a shell or another validator container.

   .. code-block:: console

      root@sawtooth-1# sawtooth settings list

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


.. _stop-sawtooth-kube2-label:

Step 6: Stop the Sawtooth Kubernetes Cluster
--------------------------------------------

Use the following commands to stop and reset the Sawtooth network.

.. important::

  Any work done in this environment will be lost once you delete the Sawtooth
  pods. To keep your work, you would need to take additional steps, such as
  defining volume storage.  See the
  `Kubernetes documentation <https://kubernetes.io/docs/home/>`__ for more
  information.

#. Log out of all Sawtooth containers.

#. Stop Sawtooth and delete the pods. Run the following command from the same
   directory where you saved the configuration file.

   .. code-block:: console

      $ kubectl delete -f sawtooth-kubernetes-default-poet.yaml
      deployment.extensions "sawtooth-0" deleted
      service "sawtooth-0" deleted
      deployment.extensions "sawtooth-1" deleted
      service "sawtooth-1" deleted
      deployment.extensions "sawtooth-2" deleted
      service "sawtooth-2" deleted
      deployment.extensions "sawtooth-3" deleted
      service "sawtooth-3" deleted
      deployment.extensions "sawtooth-4" deleted
      service "sawtooth-4" deleted

#. Stop the Minikube cluster.

   .. code-block:: console

      $ minikube stop
      Stopping local Kubernetes cluster...
      Machine stopped.

#. Delete the Minikube cluster, VM, and all associated files.

   .. code-block:: console

      $ minikube delete
      Deleting local Kubernetes cluster...
      Machine deleted.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
