**************************
Using Sawtooth with Docker
**************************


This procedure walks through the process of setting up Hyperledger Sawtooth
for application development using Docker Compose, introduces some of the basic
Sawtooth concepts necessary for application development, and walks through
performing the following tasks:

* Submit transactions to the REST API
* View blocks, transactions, and state with Sawtooth commands
* Start and stop validators and transaction processors


Upon completing this tutorial, you will be prepared for the more advanced
tutorials that guide you in performing app development tasks, such as
implementing business logic with transaction families and writing clients
which use Sawtooth's REST API.

Overview of Sawtooth Components
===============================

A running Sawtooth network consists of the following applications or processes:

.. image:: ../images/hyperledger_sawtooth_components.*
   :width: 80%
   :align: center
   :alt: Sawtooth components

This diagram represents a simple network with just two validators and two
transaction processors. The second validator's transaction processors are not
depicted.


Install Docker Engine and Docker Compose
========================================

Windows
-------

Install the latest version of
`Docker Engine for Windows <https://docs.docker.com/docker-for-windows/install/>`_.

On Windows, Docker Compose is installed automatically when you
install Docker Engine.


macOS
-----

Install the latest version of
`Docker Engine for macOS <https://docs.docker.com/docker-for-mac/install/>`_.

On macOS, Docker Compose is installed automatically when you
install Docker Engine.


Linux
-----

On Linux, follow these steps:

#. Install `Docker Engine <https://docs.docker.com/engine/installation/linux/ubuntu>`_.
#. Install `Docker Compose <https://github.com/docker/compose/releases>`_.

.. warning::

  Note that the minimum version of Docker Engine necessary is 17.03.0-ce.
  Linux distributions often ship with older versions of Docker.


Environment Setup
=================

Download the Docker Compose File
--------------------------------

A Docker Compose file is provided which defines the process for constructing a
simple Sawtooth environment. This environment includes the following
containers:

* A single validator using dev-mode consensus
* A REST API connected to the validator
* The Settings, IntegerKey, and XO transaction processors
* A client container for running Sawtooth commands

The Docker Compose file also specifies the container images to download from
Docker Hub and the network settings needed for all the containers to communicate
correctly.

This Docker Compose file can serve as the basis for your own multi-container
Sawtooth development environment or application.

Download the Docker Compose file `here <./sawtooth-default.yaml>`_.


Proxy Settings (Optional)
-------------------------

To configure Docker to work with an HTTP or HTTPS proxy server, follow the
instructions for your  operating system:

* Windows - See the instructions for proxy configuration in
  `Get Started with Docker for Windows
  <https://docs.docker.com/docker-for-windows/#proxies>`_.


* macOS - See the instructions for proxy configuration in
  `Get Started with Docker for Mac <https://docs.docker.com/docker-for-mac/>`_.


* Linux - See the instructions for proxy configuration in
  `Control and configure Docker with
  Systemd <https://docs.docker.com/engine/admin/systemd/#httphttps-proxy>`_.


Starting Sawtooth
-----------------

To start up the environment, perform the following tasks:

1. Open a terminal window.
2. Change your working directory to the same directory where you saved the
   Docker Compose file.
3. Run the following command:

.. _restart:

.. code-block:: console

  % docker-compose -f sawtooth-default.yaml up

.. note::

  To learn more about the startup process, see :doc:`ubuntu`.


Downloading the Docker images that comprise the Sawtooth demo
environment can take several minutes. Once you see the containers
registering and creating initial blocks, you can move on to the next step.

.. code-block:: console

  Attaching to sawtooth-validator-default, sawtooth-xo-tp-python-default, sawtooth-intkey-tp-python-default, sawtooth-rest-api-default, sawtooth-settings-tp-default, sawtooth-shell-default
  sawtooth-validator-default | writing file: /etc/sawtooth/keys/validator.priv
  sawtooth-validator-default | writing file: /etc/sawtooth/keys/validator.pub
  sawtooth-validator-default | creating key directory: /root/.sawtooth/keys
  sawtooth-validator-default | writing file: /root/.sawtooth/keys/my_key.priv
  sawtooth-validator-default | writing file: /root/.sawtooth/keys/my_key.pub
  sawtooth-validator-default | Generated config-genesis.batch
  sawtooth-validator-default | Processing config-genesis.batch...
  sawtooth-validator-default | Generating /var/lib/sawtooth/genesis.batch


Stopping Sawtooth
-----------------

If the environment needs to be reset or stopped for any reason, it can be
returned to the default state by logging out of the client container, then
pressing CTRL-c from the window where you originally ran ``docker-compose``. Once
the containers have all shut down, run ``docker-compose -f sawtooth-default.yaml
down``.

Sample output after pressing CTRL-c:

.. code-block:: console

  sawtooth-validator-default         | [00:27:56.753 DEBUG    interconnect] message round trip: TP_PROCESS_RESPONSE 0.03986167907714844
  sawtooth-validator-default         | [00:27:56.756 INFO     chain] on_block_validated: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  sawtooth-validator-default         | [00:27:56.761 INFO     chain] Chain head updated to: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  sawtooth-validator-default         | [00:27:56.762 INFO     publisher] Now building on top of block: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  sawtooth-validator-default         | [00:27:56.763 INFO     chain] Finished block validation of: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  Gracefully stopping... (press Ctrl+C again to force)
  Stopping sawtooth-xo-tp-python-default ... done
  Stopping sawtooth-settings-tp-default ... done
  Stopping sawtooth-shell-default... done
  Stopping sawtooth-rest-api-default ... done
  Stopping sawtooth-intkey-tp-python-default ... done
  Stopping sawtooth-validator-default ... done


After shutdown has completed, run this command:

.. code-block:: console

  % docker-compose -f sawtooth-default.yaml down


Logging Into The Client Container
=================================

The client container is used to run Sawtooth commands, which is the usual
way to interact with validators or validator networks.

Log into the client container by opening a new terminal window and
running the following command. Note that ``sawtooth-shell-default`` specifies
the client container name.

.. code-block:: console

  % docker exec -it sawtooth-shell-default bash


.. Important::

  Your environment is ready for experimenting with Sawtooth. However, any work
  done in this environment will be lost once the container exits. The demo
  Docker Compose file is useful as a starting point for the creation of your
  own Docker-based development environment. In order to use it for app
  development, you would need to take additional steps, such as mounting a host
  directory into the container. See `Docker's documentation
  <https://docs.docker.com/>`_ for details.


Confirming Connectivity
-----------------------

To confirm that a validator is running and reachable from the client
container, run this ``curl`` command as root:

.. code-block:: console

  root@75b380886502:/# curl http://rest-api:8008/blocks


To check connectivity from the host computer, open a new terminal window on your
host system and use this ``curl`` command:

.. code-block:: console

  $ curl http://localhost:8008/blocks


If the validator is running and reachable, the output for each command
should be similar to this example:

.. code-block:: console

  {
    "data": [
      {
        "batches": [],
        "header": {
          "batch_ids": [],
          "block_num": 0,
          "consensus": "R2VuZXNpcw==",
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
  }root@75b380886502:/#

If the validator process or the validator container is not running, the ``curl``
command will time out or return nothing.


Using Sawtooth Commands
=======================

Creating and Submitting Transactions with intkey
------------------------------------------------

The ``intkey`` command is provided to create sample transactions of the
intkey (IntegerKey) transaction type for testing purposes. This step uses
``intkey`` to prepare batches of intkey transactions which set a few keys
to random values, then randomly increment and decrement those values. These
batches are saved locally, then submitted to the validator.

Run the following commands from the client container:

.. code-block:: console

  $ intkey create_batch --count 10 --key-count 5
  $ intkey load -f batches.intkey -U http://rest-api:8008

The terminal window in which you ran the ``docker-compose`` command will begin
logging output as the validator and IntegerKey transaction processor handle the
transactions just submitted:

.. code-block:: console

  intkey-tp-python_1  | [21:02:53.164 DEBUG    handler] Incrementing "VaUEPt" by 1
  sawtooth-validator-default         | [21:02:53.169 DEBUG    interconnect] ServerThread receiving TP_STATE_SET_REQUEST message: 194 bytes
  sawtooth-validator-default         | [21:02:53.171 DEBUG    tp_state_handlers] SET: ['1cf126d8a50604ea6ab1b82b33705fc3eeb7199f09ff2ccbc52016bbf33ade68dc23f5']
  sawtooth-validator-default         | [21:02:53.172 DEBUG    interconnect] ServerThread sending TP_STATE_SET_RESPONSE to b'63cf2e2566714070'
  sawtooth-validator-default         | [21:02:53.176 DEBUG    interconnect] ServerThread receiving TP_PROCESS_RESPONSE message: 69 bytes
  sawtooth-validator-default         | [21:02:53.177 DEBUG    interconnect] message round trip: TP_PROCESS_RESPONSE 0.042026519775390625
  sawtooth-validator-default         | [21:02:53.182 DEBUG    interconnect] ServerThread sending TP_PROCESS_REQUEST to b'63cf2e2566714070'
  intkey-tp-python_1  | [21:02:53.185 DEBUG    core] received message of type: TP_PROCESS_REQUEST
  sawtooth-validator-default         | [21:02:53.191 DEBUG    interconnect] ServerThread receiving TP_STATE_GET_REQUEST message: 177 bytes
  sawtooth-validator-default         | [21:02:53.195 DEBUG    tp_state_handlers] GET: [('1cf126721fff0dc4ccb345fb145eb9e30cb7b046a7dd7b51bf7393998eb58d40df5f9a', b'\xa1fZeuYwh\x1a\x00\x019%')]
  sawtooth-validator-default         | [21:02:53.200 DEBUG    interconnect] ServerThread sending TP_STATE_GET_RESPONSE to b'63cf2e2566714070'
  intkey-tp-python_1  | [21:02:53.202 DEBUG    handler] Incrementing "ZeuYwh" by 1


Submitting Transactions with sawtooth batch submit
--------------------------------------------------

Instead of using ``intkey load``, you can also submit transactions,
including IntegerKey transactions, with the ``sawtooth batch submit`` command.

For example, you can submit the transactions in the file ``batches.intkey``
as generated above with this command:

.. code-block:: console

  $ sawtooth batch submit -f batches.intkey --url http://rest-api:8008


Viewing the Block Chain
-----------------------

You can view the blocks stored in the blockchain using the
``sawtooth block`` subcommand.

.. note::

  The ``sawtooth`` command provides help for all subcommands. For example, to
  get help for the ``block`` subcommand, enter the command ``sawtooth block -h``.

Viewing the List of Blocks
++++++++++++++++++++++++++

Enter the command ``sawtooth block list`` to view the blocks stored by the state:

.. code-block:: console

  $ sawtooth block list --url http://rest-api:8008

The output of the command will be similar to this:

.. code-block:: console

  NUM  BLOCK_ID                                                                                                                          BATS  TXNS  SIGNER
  1    e8377628b299f4a3ff11ed173958205f30c1db12ea136ee75ab1b659d43dccd62bc994592faaca1d98d73044da902e9a8ebaced1f1479046a2f829e02e8f7e7e  11    63    027da204...
  0    97b210dd655fce913a76ec02c0fc131c8ec79b14592ec5170c55fea0c0c9fc7b6b84ba61d94d27d31a220d7301b33dd34c56d5221cc04d5724b9c97c34d70234  1     1     027da204...


Viewing a Particular Block
++++++++++++++++++++++++++

From the output generated by the ``sawtooth block list`` command, copy the id
of a block you want to get more info about, then paste it in place of
``{BLOCK_ID}`` in the following ``sawtooth block show`` command:

.. code-block:: console

  $ sawtooth block show --url http://rest-api:8008 {BLOCK_ID}

The output of this command includes all data stored under that block, and can be
quite long. It should look something like this:

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
        inputs:
        - 000000a87cb5eafdcca6a8b79606fb3afea5bdab274474a6aa82c1c0cbf0fbcaf64c0b
        - 000000a87cb5eafdcca6a8b79606fb3afea5bdab274474a6aa82c12840f169a04216b7
        - 000000a87cb5eafdcca6a8b79606fb3afea5bdab274474a6aa82c1918142591ba4e8a7
        - 000000a87cb5eafdcca6a8f82af32160bc531176b5001cb05e10bce3b0c44298fc1c14
        nonce: ''
        outputs:
        - 000000a87cb5eafdcca6a8b79606fb3afea5bdab274474a6aa82c1c0cbf0fbcaf64c0b
        - 000000a87cb5eafdcca6a8f82af32160bc531176b5001cb05e10bce3b0c44298fc1c14
        payload_sha512: 944b6b55e831a2ba37261d904b14b4e729399e4a7c41bd22fcb09c46f0b3821cd41750e38640e33f79b6b5745a20225a1f5427bd5085f3800c166bbb7fb899e8
        signer_public_key: 0276023d4f7323103db8d8683a4b7bc1eae1f66fbbf79c20a51185f589e2d304ce
      header_signature: 24b168aaf5ea4a76a6c316924a1c26df0878908682ea5740dd70814e7c400d56354dee788191be8e28393c70398906fb467fac8db6279e90e4e61619589d42bf
      payload: EtwBCidzYXd0b290aC52YWxpZGF0b3IudHJhbnNhY3Rpb25fZmFtaWxpZXMSngFbeyJmYW1pbHkiOiAiaW50a2V5IiwgInZlcnNpb24iOiAiMS4wIiwgImVuY29kaW5nIjogImFwcGxpY2F0aW9uL3Byb3RvYnVmIn0sIHsiZmFtaWx5Ijoic2F3dG9vdGhfY29uZmlnIiwgInZlcnNpb24iOiIxLjAiLCAiZW5jb2RpbmciOiJhcHBsaWNhdGlvbi9wcm90b2J1ZiJ9XRoQMTQ5NzQ0ODgzMy4zODI5Mw==
  header:
    batch_ids:
    - a93731646a8fd2bce03b3a17bc2cb3192d8597da93ce735950dccbf0e3cf0b005468fadb94732e013be0bc2afb320be159b452cf835b35870db5fa953220fb35
    block_num: 3
    consensus: RGV2bW9kZQ==
    previous_block_id: 042f08e1ff49bbf16914a53dc9056fb6e522ca0e2cff872547eac9555c1de2a6200e67fb9daae6dfb90f02bef6a9088e94e5bdece04f622bce67ccecd678d56e
    signer_public_key: 033fbed13b51eafaca8d1a27abc0d4daf14aab8c0cbc1bb4735c01ff80d6581c52
    state_root_hash: 5d5ea37cbbf8fe793b6ea4c1ba6738f5eee8fc4c73cdca797736f5afeb41fbef
  header_signature: ff4f6705bf57e2a1498dc1b649cc9b6a4da2cc8367f1b70c02bc6e7f648a28b53b5f6ad7c2aa639673d873959f5d3fcc11129858ecfcb4d22c79b6845f96c5e3



Viewing Global State
--------------------

Viewing the List of Nodes (Addresses)
+++++++++++++++++++++++++++++++++++++

Use the command ``sawtooth state list`` to list the nodes in the Merkle tree:

.. code-block:: console

  $ sawtooth state list --url http://rest-api:8008

The output of the command will be similar to this truncated list:

.. code-block:: console

  ADDRESS                                                                                                                                SIZE DATA
  1cf126ddb507c936e4ee2ed07aa253c2f4e7487af3a0425f0dc7321f94be02950a081ab7058bf046c788dbaf0f10a980763e023cde0ee282585b9855e6e5f3715bf1fe 11   b'\xa1fcCTdcH\x...
  1cf1260cd1c2492b6e700d5ef65f136051251502e5d4579827dc303f7ed76ddb7185a19be0c6443503594c3734141d2bdcf5748a2d8c75541a8e568bae063983ea27b9 11   b'\xa1frdLONu\x...
  1cf126ed7d0ac4f755be5dd040e2dfcd71c616e697943f542682a2feb14d5f146538c643b19bcfc8c4554c9012e56209f94efe580b6a94fb326be9bf5bc9e177d6af52 11   b'\xa1fAUZZqk\x...
  1cf126c46ff13fcd55713bcfcf7b66eba515a51965e9afa8b4ff3743dc6713f4c40b4254df1a2265d64d58afa14a0051d3e38999704f6e25c80bed29ef9b80aee15c65 11   b'\xa1fLvUYLk\x...
  1cf126c4b1b09ebf28775b4923e5273c4c01ba89b961e6a9984632612ec9b5af82a0f7c8fc1a44b9ae33bb88f4ed39b590d4774dc43c04c9a9bd89654bbee68c8166f0 13   b'\xa1fXHonWY\x...
  1cf126e924a506fb2c4bb8d167d20f07d653de2447df2754de9eb61826176c7896205a17e363e457c36ccd2b7c124516a9b573d9a6142f031499b18c127df47798131a 13   b'\xa1foWZXEz\x...
  1cf126c295a476acf935cd65909ed5ead2ec0168f3ee761dc6f37ea9558fc4e32b71504bf0ad56342a6671db82cb8682d64689838731da34c157fa045c236c97f1dd80 13   b'\xa1fadKGve\x...



Viewing Data at an Address
++++++++++++++++++++++++++

From the output generated by the ``sawtooth state list`` command, copy the
address you want to view, then paste it in place of ``{STATE_ADDRESS}``
in the following ``sawtooth state show`` command:


.. code-block:: console

  $ sawtooth state show --url http://rest-api:8008 {STATE_ADDRESS}


The output of the command will include both the bytes stored at that address
and the block id of the *chain head* the current state is tied to. It should
look similar to this:

.. code-block:: console

  DATA: "b'\xa1fcCTdcH\x192B'"
  HEAD: "0c4364c6d5181282a1c7653038ec9515cb0530c6bfcb46f16e79b77cb524491676638339e8ff8e3cc57155c6d920e6a4d1f53947a31dc02908bcf68a91315ad5"



Connecting to the REST API
==========================

From the Client Container
-------------------------

Use ``curl`` to confirm that you can connect to the REST API from the host.
Enter the following command from the terminal window for the client container:

.. code-block:: console

  $ curl http://rest-api:8008/blocks


From the Host Operating System
------------------------------

Use ``curl`` to confirm that you can connect to the REST API from the host.
Enter the following command from the terminal window for your host system:

.. code-block:: console

  $ curl http://localhost:8008/blocks


Connecting to Each Container
============================

The Client Container
--------------------

* Submits transactions
* Runs Sawtooth commands
* Container name: ``sawtooth-shell-default``

No Sawtooth components are automatically started in this container.

Log into this container by running this command from the host computer's
terminal window:

.. code-block:: console

  % docker exec -it sawtooth-shell-default bash


The Validator Container
-----------------------

* Runs a single validator
* Available to the other containers and host on TCP port 4004 (default)
* Hostname: ``validator``
* Container name: ``sawtooth-validator-default``

Log into this container by running this command from the host computer's
terminal window:

.. code-block:: console

  $ docker exec -it sawtooth-validator-default bash

To see which components are running, use this command from the container:

.. code-block:: console

  $ ps --pid 1 fw
    PID TTY      STAT   TIME COMMAND
    1 ?        Ss     0:00 bash -c sawadm keygen && sawtooth keygen my_key && sawset genesis -k /root/.sawtooth/keys/my_key.priv && sawadm genesis config-genesis.batch && sawtooth-validator -vv --endpoint

.. note::

  The validator can process transactions in serial or parallel with no difference
  in the state produced. To process in parallel, give ``sawtooth-validator`` the option ``--scheduler parallel``
  in the `sawtooth-default.yaml` file.
  The default option is ``--scheduler serial``. To get the most benefit from the parallel option,
  add more transaction processors to the `sawtooth-default.yaml` file.

The REST API Container
----------------------

* Runs the REST API
* Available to the client container and host on TCP port 8008
* Container name: ``sawtooth-rest-api-default``

Log into this container by running this command from the host computer's
terminal window:

.. code-block:: console

  $ docker exec -it sawtooth-rest-api-default bash

To see which components are running, run this command from the container:

.. code-block:: console

  $ ps --pid 1 fw
    PID TTY      STAT   TIME COMMAND
    1 ?        Ssl    0:02 /usr/bin/python3 /usr/bin/sawtooth-rest-api --connect tcp://validator:4004 --bind rest-api:8008


The Settings Transaction Processor Container
--------------------------------------------

* Runs a single Settings transaction processor
* Handles transactions of the Settings transaction family
* Hostname: ``settings-tp``
* Container name: ``sawtooth-settings-tp-default``

Log into this container by running this command from the host computer's
terminal window:

.. code-block:: console

  $ docker exec -it sawtooth-settings-tp-default bash

To see which components are running, run this command from the container:

.. code-block:: console

  $ ps --pid 1 fw
    PID TTY      STAT   TIME COMMAND
    1 ?        Ssl    0:00 /usr/bin/python3 /usr/bin/settings-tp -vv tcp://validator:4004


The IntegerKey Transaction Processor Container
----------------------------------------------

* Runs a single IntegerKey transaction processor
* Handles transactions of the IntegerKey transaction family
* Hostname: ``intkey-tp-python``
* Container name: ``sawtooth-intkey-tp-python-default``

Log into this container by running this command from the host computer's
terminal window:

.. code-block:: console

  $ docker exec -it sawtooth-intkey-tp-python-default bash

To see which components are running, run this command from the container:

.. code-block:: console

  $ ps --pid 1 fw
    PID TTY      STAT   TIME COMMAND
    1 ?        Ssl    0:00 /usr/bin/python3 /usr/bin/intkey-tp-python -vv tcp://validator:4004


The XO Transaction Processor Container
--------------------------------------

* Runs a single XO transaction processor
* Handles transactions of the XO transaction family
* Hostname: ``xo-tp-python``
* Container name: ``sawtooth-xo-tp-python-default``

Log into this container by running this command from the host computer's
terminal window:

.. code-block:: console

  $ docker exec -it sawtooth-xo-tp-python-default bash

To see which components are running, run this command from the container:

.. code-block:: console

  $ ps --pid 1 fw
    PID TTY      STAT   TIME COMMAND
    1 ?        Ssl    0:00 /usr/bin/python3 /usr/bin/xo-tp-python -vv tcp://validator:4004


Viewing Log Files
=================

You can view the log files for any running Docker container using the
``docker logs`` command.
Replace ``{CONTAINER}`` with the name of one of the Sawtooth Docker containers,
such as ``sawtooth-validator-default``.

.. code-block:: console

  $ docker logs {CONTAINER}


Configuring the List of Transaction Families
============================================

Next, tell the validator or validator network to accept
transactions from the IntegerKey and Settings transaction families.

Sawtooth provides a :doc:`Settings transaction family
<../transaction_family_specifications/settings_transaction_family>` that stores
on-chain configuration settings, along with a Settings family transaction
processor written in Python.

One of the on-chain settings is the list of supported transaction families.
In the example below, a JSON array is submitted to the ``sawset``
command, which creates and submits a batch of transactions containing the
configuration change.

The submitted JSON array tells the validator or validator network to accept
transactions of the following types:

* intkey (IntegerKey transaction family)
* sawtooth_settings (Sawtooth transaction family)

To create and submit the batch containing the new setting, enter the following
commands.

.. note::

  The config command needs to use a key generated in the validator container.
  Thus, you must open a terminal window running in the validator container,
  rather than the client container (for the following command only).
  Run the following command on your host machine:

.. code-block:: console

  % docker exec -it sawtooth-validator-default bash

Then run the following command from the validator container:

.. code-block:: console

  $ sawset proposal create \
    --url http://rest-api:8008 \
    --key /root/.sawtooth/keys/my_key.priv \
    sawtooth.validator.transaction_families='[{"family": "intkey", "version": "1.0"}, {"family":"sawtooth_settings", "version":"1.0"}]'
  $ sawtooth settings list --url http://rest-api:8008


A TP_PROCESS_REQUEST message appears in the logging output of the validator,
and output similar to the following appears in the validator terminal window:

.. code-block:: console

  sawtooth.settings.vote.authorized_keys: 0276023d4f7323103db8d8683a4b7bc1eae1f66fbbf79c20a51185f589e2d304ce
  sawtooth.validator.transaction_families: [{"family": "intkey", "version": "1.0"}, {"family":"sawtooth_settings", "versi...

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
