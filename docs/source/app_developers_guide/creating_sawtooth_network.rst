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

- Ubuntu: Install Sawtooth natively using
  `Ubuntu 16.04 <https://www.ubuntu.com/>`_. You will add a node to the existing
  application development environment that is described in :doc:`ubuntu`, but
  you will delete all existing blockchain data, including the genesis block.

- Kubernetes: Run a Sawtooth network in a `Kubernetes <https://kubernetes.io>`_
  cluster inside a virtual machine on your computer.

.. note::

   The guides in this chapter set up an environment with five Sawtooth validator
   nodes. For a single-node environment, see :doc:`installing_sawtooth`.

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
  on-chain configuration settings, such as the consensus type, that will be
  available to the new validator nodes once they join the network.

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

.. figure:: ../images/appdev-environment-two-nodes.*
   :width: 100%
   :align: center
   :alt: Application development environment with two nodes

Like the single-node environment, this environment uses serial transaction
processing and static peering. However, it has the following differences:

* PoET simulator consensus instead of dev mode, because dev mode's random-leader
  consensus is not recommended for multi-node or production networks. Sawtooth
  offers two versions of :term:`PoET` consensus. PoET-SGX relies on Intel
  Software Guard Extensions (SGX) to implement a leader-election lottery system.
  PoET simulator provides the same consensus algorithm on an SGX simulator.

* An additional transaction processor, Validator Registry, which handles PoET
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


Step 1: Download the Docker Compose file
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

You can connect to Docker container, such as
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

#. (Optional) You can also run Sawtooth commands on a validator node to show
   the other nodes on the network, called `peers`.

   * Use ``sawtooth peer list`` to show the peers of a particular node.

   * Use ``sawnet peers list`` to display a complete graph of peers on the
     network.

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


Step 5: Stop the Sawtooth Network (Optional)
--------------------------------------------

If you need to stop or reset the multiple-node Sawtooth environment, enter
CTRL-c in the window where you ran ``docker-compose up``, then run the following
command from your host system:

.. code-block:: console

   user@host$ docker-compose -f sawtooth-default-poet.yaml down


.. _proc-multi-ubuntu-label:

Ubuntu: Add a Node to the Single-Node Environment
=================================================

This procedure describes how to add a second validator node to a single-node
application development environment, as described in :doc:`ubuntu`.
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
   :alt: Application development environment with two nodes

Like the single-node environment, this environment uses serial transaction
processing and static peering. However, it has the following differences:

* PoET simulator consensus instead of dev mode, because dev mode's random-leader
  consensus is not recommended for multi-node or production networks. Sawtooth
  offers two versions of :term:`PoET` consensus. PoET-SGX relies on Intel
  Software Guard Extensions (SGX) to implement a leader-election lottery system.
  PoET simulator provides the same consensus algorithm on an SGX simulator.

* An additional transaction processor, Validator Registry, which handles PoET
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
      yourname.priv    yourname.pub

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
      sawtooth.consensus.algorithm=poet \
      sawtooth.poet.report_public_key_pem="$(cat /etc/sawtooth/simulator_rk_pub.pem)" \
      sawtooth.poet.valid_enclave_measurements=$(poet enclave measurement) \
      sawtooth.poet.valid_enclave_basenames=$(poet enclave basename)

#. Create a batch to register the first validator with the PoET Validator
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

      This network requires ``settings-tp`` and ``poet-validator-registry-tp``.
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
      writing file: /home/yourname/.sawtooth/keys/yourname.priv
      writing file: /home/yourname/.sawtooth/keys/yourname.pub

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

#. (Optional) You can also run Sawtooth commands on a validator node to show
   the other nodes on the network, called `peers`.

   * Use ``sawtooth peer list`` to show the peers of a particular node.

   * Use ``sawnet peers list`` to display a complete graph of peers on the
     network.

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


        .. code-block:: console

           $ intkey show MyKey
           MyKey: 999


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
