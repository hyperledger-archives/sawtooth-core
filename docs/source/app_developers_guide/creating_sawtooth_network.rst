***************************
Creating a Sawtooth Network
***************************

This procedure describes how to create a Sawtooth network with two or more
validator nodes. It creates an application development environment that is
similar to the single-node environment in :doc:`installing_sawtooth`, but with
these differences:

* Docker: You will create a new application development environment by using a
  Docker Compose file that creates a network with five validator nodes.

* Ubuntu: You will add a node to the existing application development
  environment that is described in :doc:`ubuntu`.

The following figure shows an example network with two validator nodes:

.. figure:: ../images/appdev-environment-two-nodes.*
   :width: 100%
   :align: center
   :alt: Application development environment with two nodes

Like the single-node environment, this environment uses serial transaction
processing and static peering. However, this multiple-node environment uses PoET
simulator consensus instead of dev_mode consensus. As a result, it adds the
Validator Registry transaction processor, which handles certain settings for a
multiple-node network.


About Sawtooth Networks
=======================

A Sawtooth network has the following requirements:

* Each host system (physical computer, virtual machine, or set of Docker
  containers) must run one validator, an optional REST API, and an identical set
  of transaction processors.

  This environment includes the Sawtooth REST API on all validator nodes.
  However, an application could provide a custom REST API (or no REST API). See
  `Sawtooth Supply Chain <https://github.com/hyperledger/sawtooth-supply-chain>`_
  for an example of a custom REST API.

* Each validator node must advertise a routable address. The Docker platform
  provides a preconfigured setting. For the Ubuntu platform, you must follow the
  instructions in this procedure to provide this information when starting the
  validator.

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


Docker: Start a Multiple-node Sawtooth Network
==============================================

In this procedure, you will use a Docker Compose file that creates a new
application development environment with five validator nodes.

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

    * ``sawtooth-poet-validator-0``
    * ``sawtooth-poet-rest-api-0``
    * ``sawtooth-poet-settings-tp-0``
    * ``sawtooth-poet-intkey-tp-python-0``
    * ``sawtooth-poet-xo-tp-python-0``
    * ``sawtooth-poet-validator-registry-tp-0``

   ``validator-1``:

    * ``sawtooth-validator-default-1``
    * ``sawtooth-poet-rest-api-1``
    * ``sawtooth-settings-tp-default-1``
    * ``sawtooth-poet-intkey-tp-python-1``
    * ``sawtooth-poet-xo-tp-python-1``
    * ``sawtooth-poet-validator-registry-tp-1``

   ... and so on.

#. Note that there is only one shell container for this Docker environment:

    * ``sawtooth-poet-shell``

Step 3: Verify Connectivity
---------------------------

You can connect to a validator registry container, such as
``sawtooth-poet-validator-registry-tp-0``, then use the following command
to verify that ``poet-validator-registry-tp`` is running.

.. code-block:: console

   # ps --pid 1 fw
   PID TTY      STAT   TIME COMMAND
   1 ?        Ssl    0:04 python3 /project/sawtooth-core/bin/poet-validator-registry-tp -C tcp://validator-0:4004

Step 4: Stop the Sawtooth Network (Optional)
--------------------------------------------

If you need to stop or reset the multiple-node Sawtooth environment, enter
CTRL-c in the window where you ran ``docker-compose up``, then run the following
command from your host system:

.. code-block:: console

   user@host$ docker-compose -f sawtooth-default-poet.yaml down


Ubuntu: Add a Node to the Single-Node Environment
=================================================

This procedure describes how to add a second validator node to a single-node
application development environment, as described in :doc:`ubuntu`.

.. _prereqs-multi-ubuntu-label:

Prerequisites
-------------

This procedure requires a working (runnable) validator node with a validator,
REST API, and the Settings, IntegerKey, and XO transaction processors
(see :doc:`ubuntu`). This procedure describes how to start the XO transaction
processor if it is not already running.

For each validator node that will be on your network, gather the following
information:

* Where this validator will listen for incoming communication from this
  validator's components (the "component bind string")

* Where this validator will listen for incoming communication from other
  validator nodes, also called peers (the "network bind string")

* The address that other peers should use to find this validator node (the
  "public endpoint string")

* The addresses that this validator should use to connect to the other validator
  nodes, also referred to as peers (the "peers list"). Each address on the list
  is referred to as the "peer's public endpoint string".

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
  Sawtooth components locally, you could specify the component bind string
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

.. important::

   This step requires an existing application development environment as
   described in :doc:`ubuntu`.

#. If the first validator node is running, stop the validator, as described
   in the first step of :ref:`stop-sawtooth-ubuntu-label`.

   If the first validator node is not running, start all Sawtooth components
   except for the validator (see :doc:`docker`).

#. Use the following command to start the validator on the first node.
   Substitute your actual values for the network and component bind strings,
   public endpoint string, and peer list, as described in
   :ref:`prereqs-multi-ubuntu-label`.

   .. code-block:: console

      $ sudo -u sawtooth sawtooth-validator \
      --bind network:{network-bind-string} \
      --bind component:(component-bind-string} \
      --endpoint {public-endpoint-string} \
      --peers {peer-list}

   If you plan to add two or more nodes to the network, you can specify
   multiple peers in a comma-separated list, as in this example:

     .. code-block:: none

        --peers tcp://172.0.1.3,tcp://172.0.1.4

#. If the XO transaction processor is not running, start it as described in
   Step 7 of :doc:`docker`.


.. _install-second-val-ubuntu-label:

Step 2: Set Up the Second Validator Node
----------------------------------------

#. Install Sawtooth on the second node, as described in
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
   to start the validator. Use the actual values for the network and component
   bind strings, public endpoint string, and peer list, as described in
   :ref:`prereqs-multi-ubuntu-label`.

   .. code-block:: console

      $ sudo -u sawtooth sawtooth-validator \
      --bind network:{network-bind-string} \
      --bind component:(component-bind-string} \
      --endpoint {public-endpoint-string} \
      --peers {peer-list}

   If you plan to add two or more node to the network, you can specify
   multiple peers in a comma-separated list, as in this example:

     .. code-block:: none

        --peers tcp://172.0.1.2,tcp://172.0.1.4


#. Start the REST API and transaction processors on the second validator node,
   as shown in this summary of steps 3, 4, and 5 in :doc:`ubuntu`. Open a
   separate terminal window to start each component.

   .. code-block:: console

      $ sudo -u sawtooth sawtooth-rest-api -v

   .. code-block:: console

      $ sudo -u sawtooth settings-tp -v

   .. code-block:: console

      $ sudo -u sawtooth intkey-tp-python -v

   .. code-block:: console

      $ sudo -u sawtooth xo-tp-python -v

   .. code-block:: console

      $ sudo -u sawtooth sawtooth-poet-validator-registry-tp -v

If you have additional nodes in the network, repeat this step on those nodes.


Confirm Network Functionality
=============================

#. To check whether peering has occurred on the network, submit a block query
   to the local REST API from the first validator node.

     * Docker: Run this command:

       .. code-block:: console

          $ curl http://sawtooth-poet-rest-api-0:8008/peers

     * Ubuntu: Run the following command, replacing `{rest-api}` with the host
       name and port for the REST API on the first validator node, as determined
       in :ref:`prereqs-multi-ubuntu-label`. On a node that is running the REST
       API and client on the same host system, the default value is
       ``http://localhost:8008``.

       .. code-block:: console

          $ curl http://{rest-api}/peers

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

#. You can also use Sawtooth commands to show peer information.

   * Use ``sawtooth peer list`` to list the peers of a particular node. For more
     information, run ``sawtooth peer list --help``.

   * Use ``sawnet peers list`` to display a complete graph of peers on the
     network. For more information, run ``sawnet peers list --help``.

#. Submit a transaction on the first validator node. This example sets a key
   named ``MyKey`` to the value 999.

   * Docker:

     .. code-block:: console

        # intkey set --url http://sawtooth-poet-rest-api-0:8008 MyKey 999

   * Ubuntu:

     .. code-block:: console

        $ intkey set MyKey 999

     If necessary (if the REST API does not use the default URL and port), you
     must also use the ``--url`` option to provide the actual value for your
     network.

#. On the second validator node, watch for this transaction to appear on the
   blockchain. Run the following command:

   * Docker:

     .. code-block:: console

        # intkey show --url http://sawtooth-poet-rest-api-1:8008 MyKey
        MyKey: 999

   * Ubuntu:

     .. code-block:: console

        $ intkey show MyKey
        MyKey: 999

     If necessary, use the ``--url`` option to specify the REST API, as in the
     example above.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
