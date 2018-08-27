*************************************************
Using Kubernetes for Your Development Environment
*************************************************

This procedure explains how to create a single Hyperledger Sawtooth validator
node with
`Kubernetes <https://kubernetes.io/docs/concepts/overview/what-is-kubernetes/>`_.
This environment uses `Minikube <https://kubernetes.io/docs/setup/minikube/>`_
to deploy Sawtooth as a containerized application in a local Kubernetes cluster
inside a virtual machine (VM) on your computer.

.. note::

   This environment has one Sawtooth validator node. For a
   multiple-node environment, see :doc:`creating_sawtooth_network`.

This procedure walks you through the following tasks:

 * Installing ``kubectl`` and Minikube
 * Starting Minikube
 * Starting Sawtooth in a Kubernetes cluster
 * Connecting to the Sawtooth shell container
 * Using Sawtooth commands to submit transactions, display block data, and view
   global state
 * Examining Sawtooth logs
 * Stopping Sawtooth and deleting the Kubernetes cluster

After completing this procedure, you will have the environment required for
the other tutorials in this guide, :doc:`intro_xo_transaction_family` and
:doc:`using_the_sdks`.


Prerequisites
=============

This application development environment requires
`kubectl <https://kubernetes.io/docs/concepts/overview/object-management-kubectl/overview/>`_
and
`Minikube <https://kubernetes.io/docs/setup/minikube/>`_ with a supported VM
hypervisor, such as VirtualBox.


About the Application Development Environment
=============================================

This application development environment is a single validator node that is
running a :term:`validator`, a :term:`REST API`, and three
:term:`transaction processors<transaction processor>`. This environment uses
:ref:`dev mode consensus <dynamic-consensus-label>` and
:doc:`serial transaction processing <../architecture/scheduling>`.

.. figure:: ../images/appdev-environment-one-node-3TPs-kube.*
   :width: 100%
   :align: center
   :alt: Docker application environment for Sawtooth

The Kubernetes cluster has one pod with a container for each Sawtooth component.
After the container is running, you can use the `Kubernetes dashboard
<https://kubernetes.io/docs/tasks/access-application-cluster/web-ui-dashboard/>`_
to view pod status, container names, Sawtooth log files, and more.

This example environment includes the following transaction processors:

 * :doc:`Settings <../transaction_family_specifications/settings_transaction_family>`
   handles Sawtooth's on-chain settings. The ``sawtooth-settings-tp``
   transaction processor is required for this environment.

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
====================================

This step summarizes the kubectl and Minikube installation procedures.
For more information, see the
`Kubernetes documentation <https://kubernetes.io/docs/home/>`_.

1. Install a virtual machine (VM) hypervisor, such as VirtualBox, VMWare,
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
===============================

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
================================================

Download the Kubernetes configuration file for a single-node environment:
`sawtooth-kubernetes-default.yaml <./sawtooth-kubernetes-default.yaml>`_.

This file defines the process for constructing a one-node Sawtooth environment
with following containers:

* A single validator using :ref:`dev mode consensus <dynamic-consensus-label>`
* A REST API connected to the validator
* The Settings transaction processor (``sawtooth-settings``)
* The IntegerKey transaction processor (``intkey-tp-python``)
* The XO transaction processor (``xo-tp-python``)
* A shell container for running Sawtooth commands (a command-line client)

The configuration file also specifies the container images to download
(from DockerHub) and the network settings needed for the containers to
communicate correctly.


Step 4: Start the Sawtooth Cluster
==================================

.. note::

   The Kubernetes configuration file handles the Sawtooth startup steps such as
   generating keys and creating a genesis block. To learn about the full
   Sawtooth startup process, see :doc:`ubuntu`.

Use these steps to start Sawtooth:

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

      $ kubectl apply -f sawtooth-kubernetes-default.yaml

#. (Optional) Start the Minikube dashboard.

   .. code-block:: console

      $ minikube dashboard

   This command opens the dashboard in your default browser.
   The overview page shows the Sawtooth deployment (``sawtooth-0``)
   and pod (:samp:`sawtooth-0-{POD-ID}`).


Step 5: Test Basic Sawtooth Functionality
=========================================

1.  Connect to the shell container.

   .. code-block:: none

      $ kubectl exec -it $(kubectl get pods | awk '/sawtooth-0/{print $1}') --container sawtooth-shell -- bash

   .. note::

      In the rest of this procedure, the prompt ``root@sawtooth-0#`` marks the
      commands that should be run in a Sawtooth container.
      (The actual prompt is similar to ``root@sawtooth-0-5ff6d9d578-5w45k:/#``.)

2. Display the list of blocks on the Sawtooth blockchain.

   .. code-block:: console

      root@sawtooth-0# sawtooth block list

   Because this is a new blockchain, there is only one block. Block 0 is the
   :term:`genesis block`. The output is similar to this example:

   .. code-block:: console

      NUM  BLOCK_ID                                                                                                                          BATS  TXNS  SIGNER
      0    20d7b6657721758d1ad1a3392daadd57473d84e1e1c8c58c14ec862ff7fbf44a3bef4d82c40052dd8fc2808191f830447df59fe074aea02a000ff64bc458e256  1     1     025f80...

#. Copy the block ID from the previous output, then use the following command to
   display more information about the block.

   .. code-block:: console

      root@sawtooth-0# sawtooth block show {BLOCK-ID}

   The output of this command is quite long, because it includes all data stored
   under that block.

   .. code-block:: console

      batches:
      - header:
          signer_public_key: 03f257dee6f021b579cb59d34f2489603892d44bb2e181eaa444e1bb4f4b4b812d
          transaction_ids:
          - 3f6c2f60a66317f09d052757dba605d0c1c56caa38cdfdefbd7f4511a830a1fc22d8e13ff86201ac309344605b5df77a85e59799c16c3ba9e3cba950b709be04
        header_signature: 6e5446e99bae1fe2d7d4a7561880bd069cc404e099dd4380a7f491dd0588584b0b6b558d636eb42720d6c839c6755182d3004b905429088413df00f82ec0fd1e
         ...

At this point, your environment is ready for experimenting with Sawtooth.
The rest of this section introduces you to Sawtooth functionality.

* To use Sawtooth client commands to create and submit transactions, view block
  information, and check state data, see :ref:`sawtooth-client-kube-label`.

* To check the Sawtooth components, see :ref:`check-status-kube-label`.

* For information on the Sawtooth logs, see :ref:`examine-logs-kube-label`.

* To stop the Sawtooth environment, see :ref:`stop-sawtooth-kube-label`.

.. important::

   Any work done in this environment will be lost once you stop Minikube and
   delete the Sawtooth cluster. In order to use this environment for application
   development, you would need to take additional steps, such as defining volume
   storage. See the
   `Kubernetes documentation <https://kubernetes.io/docs/home/>`__ for more
   information.


.. _sawtooth-client-kube-label:

Step 6: Use Sawtooth Commands as a Client
=========================================

Sawtooth includes commands that act as a client interface for an application.
This step describes how to use the ``intkey`` and ``sawtooth`` commands to
create and submit transactions, display blockchain and block data, and examine
global state data.

.. note::

   Use the ``--help`` option with any Sawtooth command to display the available
   options and subcommands.

To run the commands in this step, connect to the shell container as described in
the previous step.

Creating and Submitting Transactions with intkey
------------------------------------------------

The ``intkey`` command creates and submits IntegerKey transactions for testing
purposes.

#. Use ``intkey create_batch`` to prepare batches of transactions that set
   a few keys to random values, then randomly increment and decrement those
   values. These batches are saved locally in the file ``batches.intkey``.

   .. code-block:: console

      root@sawtooth-0# intkey create_batch --count 10 --key-count 5
      Writing to batches.intkey...

#. Use ``intkey load`` to submit the batches to the validator, which commits
   these batches of transactions as new blocks on the blockchain.

   .. code-block:: console

      root@sawtooth-0# intkey load -f batches.intkey
      batches: 11 batch/sec: 141.7800162868952

#. Display the list of blocks to verify that the new blocks appear on the
   blockchain.

   .. code-block:: console

      root@sawtooth-0# sawtooth block list
      NUM  BLOCK_ID                                                                                                                          BATS  TXNS  SIGNER
      8    b46c58121d7bf04cf8489a8b937f1478e8699edd0cf023e2cac9b44827caadd441b8c013a4f6e976d799bb59ad602cfb2ea7a765d7abeb954f9013ded464e94c  1     8     025f80...
      7    a0d0e594672c5ae45ff5dfaa9c2e26d148e80190dfe88bc9ac915ed6a9d7b33c27e24d1c891e6b24dcaf59e0e6a6128aab956010b100daf81e9307b66b04d519  1     2     025f80...
      6    0a7739e9d778d65c0fa5ba21e18a8d375072907cec2ec3cbdd8dbcd20f81f2c42d30a4a65b2a63a7aa69d398677542fbf05efbd4a9b7f4aac1fb955b7913d7aa  1     8     025f80...
      5    71efa1c3297e95b7ffb7014ab425e87ff8240a51fb30faf280038882c9bfb3a060fe3ecee12bb9b064195f13ace582c0ab0a3b25808bf87081e33987d8313472  1     3     025f80...
      4    11f177a274d893c22d9bca763a88fdbf020922c68f2231ce0ca0aaa4d80559e52fa67fa059e23ceb0d006acf0b4f2bf315b77ced24959f4a556ac59bd9312356  2     3     025f80...
      3    e3b7692bb070c3d51bf3d975e6cf974d763f893232d305d36bcdbbc2b2859ad425bb0f5aaf068114d05056133a6c8ca84cfdcda6ce7a888a6486090f1f188242  2     5     025f80...
      2    06506f0599ad59b92c13bc2a96ca0c4ca59cdc8c8065df1dc27349c88566293f498c0e3dfe3f06be9b5e889beec0369dd9b94decc309aceb6f57e238e9037e04  1     3     025f80...
      1    327aede38ab395bbdba711911414a9a68166b5378af4bdc15206089a2adf0cb62448f9fc4d749f0c8677849f7fe19c734f05f86687201666e8899437f903102d  2     8     025f80...
      0    20d7b6657721758d1ad1a3392daadd57473d84e1e1c8c58c14ec862ff7fbf44a3bef4d82c40052dd8fc2808191f830447df59fe074aea02a000ff64bc458e256  1     1     025f80...

Submitting Transactions with sawtooth batch submit
--------------------------------------------------

In the example above, the ``intkey create_batch`` command created the file
``batches.intkey``.  Rather than using ``intkey load`` to submit these
transactions, you could use ``sawtooth batch submit`` to submit them.

#. As before, create a batch of transactions:

   .. code-block:: console

      root@sawtooth-0# intkey create_batch --count 6 --key-count 3
      Writing to batches.intkey...

#. Submit the batch file with ``sawtooth batch submit``:

   .. code-block:: console

      root@sawtooth-0# sawtooth batch submit -f batches.intkey
      batches: 7,  batch/sec: 216.80369536716367

Viewing Blockchain and Block Data with sawtooth block
-----------------------------------------------------

The ``sawtooth block`` command displays information about the blocks stored on
the blockchain.

#. Use ``sawtooth block list`` again to display the list of blocks stored
   in state.

    .. code-block:: console

       root@sawtooth-0# sawtooth block list

    The output shows the block number and block ID, as in this example:

    .. code-block:: console

       NUM  BLOCK_ID                                                                                                                          BATS  TXNS  SIGNER
       8    b46c58121d7bf04cf8489a8b937f1478e8699edd0cf023e2cac9b44827caadd441b8c013a4f6e976d799bb59ad602cfb2ea7a765d7abeb954f9013ded464e94c  1     8     025f80...
       7    a0d0e594672c5ae45ff5dfaa9c2e26d148e80190dfe88bc9ac915ed6a9d7b33c27e24d1c891e6b24dcaf59e0e6a6128aab956010b100daf81e9307b66b04d519  1     2     025f80...
       6    0a7739e9d778d65c0fa5ba21e18a8d375072907cec2ec3cbdd8dbcd20f81f2c42d30a4a65b2a63a7aa69d398677542fbf05efbd4a9b7f4aac1fb955b7913d7aa  1     8     025f80...
       5    71efa1c3297e95b7ffb7014ab425e87ff8240a51fb30faf280038882c9bfb3a060fe3ecee12bb9b064195f13ace582c0ab0a3b25808bf87081e33987d8313472  1     3     025f80...
       4    11f177a274d893c22d9bca763a88fdbf020922c68f2231ce0ca0aaa4d80559e52fa67fa059e23ceb0d006acf0b4f2bf315b77ced24959f4a556ac59bd9312356  2     3     025f80...
       3    e3b7692bb070c3d51bf3d975e6cf974d763f893232d305d36bcdbbc2b2859ad425bb0f5aaf068114d05056133a6c8ca84cfdcda6ce7a888a6486090f1f188242  2     5     025f80...
       2    06506f0599ad59b92c13bc2a96ca0c4ca59cdc8c8065df1dc27349c88566293f498c0e3dfe3f06be9b5e889beec0369dd9b94decc309aceb6f57e238e9037e04  1     3     025f80...
       1    327aede38ab395bbdba711911414a9a68166b5378af4bdc15206089a2adf0cb62448f9fc4d749f0c8677849f7fe19c734f05f86687201666e8899437f903102d  2     8     025f80...
       0    20d7b6657721758d1ad1a3392daadd57473d84e1e1c8c58c14ec862ff7fbf44a3bef4d82c40052dd8fc2808191f830447df59fe074aea02a000ff64bc458e256  1     1     025f80...

#. From the output generated by ``sawtooth block list``, copy the ID of a block
   you want to view, then paste it in place of ``{BLOCK_ID}`` in the following
   command. In this example, block 1 shows the first ``intkey`` block (from
   the previous step) with 5 transactions

   .. code-block:: console

      root@sawtooth-0# sawtooth block show 327aede38ab395bbdba711911414a9a68166b5378af4bdc15206089a2adf0cb62448f9fc4d749f0c8677849f7fe19c734f05f86687201666e8899437f903102d

   The output of this command can be quite long, because it includes all data
   stored under that block. This is a truncated example:

   .. code-block:: console

      batches:
      - header:
          signer_public_key: 0383b79f4ea95d8fcb409233703fb4c0606b403f485541b62e582600a35742642a
          transaction_ids:
          - b1626c1a9ab389556208b05bc3973e82177a152b19a061be53e351884cb506a241074f36eae62de2bfd85873bc916f803b1f3c53840f2ab6f03b21513dc1ac7a
          - 2e481fd71c30d3e39399f90654ccf9c0b64e6e67f54576a7e9004fe81bf3145023e9012ec89df898e1143126b3497c5e4acf2e21ec1d27938610c0bfc73ea8c8
          - 5b8a2ff9fafa2184640b3e917b993abc5dfd07b751145c328183670c499fdc9827711a52e927a233d62d4d22e55ed1b53b9cae4caa66d0f237f0968bbe676475
          - bea74bc920297a16294b915df1fcf267f3a6e701e769539d2e33f41aee01521e6301b734ef01edc74354ab77981eb1a4527da1f64d17d446b2b33d2d58e97051
          - 020732f598e9ff3bc0b41614ab043f3d425b7a655561da313965f0dab667c48940060a3e86d2feb7c7681efa24cdf3b1c1093ca19ee5eb6d87f555e50dde9194
        header_signature: 0362c4f928d4e39b1d13746a7023b1d8c2b5e798fc968dd36b2ea13e51f7a8d21d2865f71a4a6f00c11348699047d774eb4ebb3708c914558e81db0e04c4ff03
        trace: false
        transactions:
        - header:
            batcher_public_key: 0383b79f4ea95d8fcb409233703fb4c0606b403f485541b62e582600a35742642a
            dependencies: []
            family_name: intkey
            family_version: '1.0'
             .
             .
             .

Viewing State Data with sawtooth state
--------------------------------------

The ``sawtooth state`` command lets you display state data. Sawtooth stores
state data in a :term:`Merkle-Radix tree` (for more information, see
:doc:`../architecture/global_state`).

#. Use ``sawtooth state list`` to display addresses in state with their size
   and associated data. The default output format truncates each line; use
   ``--format`` with ``csv``, ``json``, or ``yaml`` to display the entire line.

   .. code-block:: console

      root@sawtooth-0# sawtooth state list --format csv

   The output will be similar to this truncated example:

   .. code-block:: console

      ADDRESS,SIZE,DATA
      000000a87cb5eafdcca6a8cde0fb0dec1400c5ab274474a6aa82c12840f169a04216b7,110,b'\nl\n&sawtooth.settings.vote.authorized_keys\x12B03f257dee6f021b579cb59d34f2489603892d44bb2e181eaa444e1bb4f4b4b812d'
      1cf12601b514e0270939cf20cacf61ce341f68f383cd1839f0b0cbb363792ef26fb711,11,b'\xa1fxAdnqS\x19N\xaf'
      1cf12604ff7d37163341d6002ff1d8fb07611bbb2bdac0d7ce181671bc728cf2c0d849,11,b'\xa1fryxDcP\x19%\xd1'
      1cf1267f20354576067b5cd3cc53c30657a159d23a9a0bc02ee6693dae132004f73e90,13,b'\xa1fFJcKOs\x1a\x00\x01B\xbb'
      1cf126a2ef5597d9095b6dd7b65d1fa0320ec8624c8c9ad1c2195f872ab83faee0ab90,13,b'\xa1fRxmfbf\x1a\x00\x01S\x86'
      1cf126aa8fe078d07e4e1aad84d9b0c1ca192cfe4ed72cc93f2354bdecd7295c110f79,11,b'\xa1fOqcdTQ\x19\xab-'
      1cf126ab6c1df0a237b170c783b4ec6c010c379159d942f67d812edac9969496a9ff88,11,b'\xa1fvHgUhX\x19\x91\xaf'
      1cf126b3c1240bebf2a1d4ca3b3f6b83ce1ebee9764ac36f1076e6c7202bf73f0f5117,11,b'\xa1fjKLuTS\x19\xe6_'
      1cf126d3d7b97e3e3c6bc2dd3b750c17f9c311aee81aee90cd2c5bf53ed4e5ec6d73b3,11,b'\xa1fVVpUdq\x19\xd2\xc5'
      1cf126d4e2b632193b17b17ae0c9c1331f8e37915fe547568fab6322b516a57e108d88,11,b'\xa1fRoYclW\x19\xc6\x1e'
      1cf126d7a0dbe68f8ac9d207843054b24e211c9821b851cb748f1f7f9c528a37fe0e4a,13,b'\xa1fYhuGwm\x1a\x00\x01\x18\xa9'
      1cf126dbe0c0b5dc8aeaa176d4cd98046aef4d12a6921e357344a56c8520df9d04b61f,13,b'\xa1fDWtxbO\x1a\x00\x01p\n'
      1cf126ef1db314433d0a887ec7f2d105600898b486e72b9eee02160dd93c7572c450b8,11,b'\xa1fcOHrSu\x19\xd7\x92'
      1cf126f4fef1dcf6fa07442d004120f48129996b81480209252871dd51b7d851c4b216,13,b'\xa1fXqhSBG\x1a\x00\x01 \xec'
      (data for head block: "100fae26d4cd15808dc59c1221a289ccefc4ac5643bd80b2d6c7e1c55e6c349b0a1082cd5e787c32233c5048279bf8aea5c9fe2f9e495aed2d7363d1918b3f90")

#. Use ``sawtooth state show`` to view state data at a specific address (a node
   in the Merkle-Radix database). Copy the address from the output of
   ``sawtooth state list``, then paste it in place of ``{STATE_ADDRESS}`` in
   the following command:

   .. code-block:: console

      root@sawtooth-0# sawtooth state show {STATE_ADDRESS}

   The output shows the bytes stored at that address and the block ID of the
   "chain head" that the current state is tied to, as in this example:

   .. code-block:: console

      DATA: "b'\xa1fcCTdcH\x192B'"
      HEAD: "0c4364c6d5181282a1c7653038ec9515cb0530c6bfcb46f16e79b77cb524491676638339e8ff8e3cc57155c6d920e6a4d1f53947a31dc02908bcf68a91315ad5"

   You can use ``sawtooth block show`` (as described above) with block number
   of the chain head to view more information about that block.


.. _check-status-kube-label:

Step 7: Verify the Sawtooth Components
======================================

To check whether a Sawtooth component is running, connect to the component's
container and run the ``ps`` command.

1. Use the ``kubectl exec`` command from your computer to connect to a Sawtooth
   container. On the Kubernetes dashboard, the Pods page displays the container
   names.

   For example, connect to the validator container with the following command:

   .. code-block:: none

      $ kubectl exec -it $(kubectl get pods | awk '/sawtooth-0/{print $1}') --container sawtooth-validator -- bash

#. After connecting to the container, you can use ``ps`` to verify that the
   Sawtooth component is running.

   .. code-block:: none

      root@sawtooth-0# ps -A fw

   In the ``sawtooth-validator`` container, the output resembles the following
   example:

   .. code-block:: none

      PID TTY      STAT   TIME COMMAND
       77 pts/0    Ss     0:00 bash
       96 pts/0    R+     0:00  \_ ps -A fw
        1 ?        Ss     0:00 bash -c sawadm keygen && if [ ! -e config-genesis.batch ]; then sawset genesis -k /etc/sawtooth/keys/vali
       27 ?        Sl     0:17 /usr/bin/python3 /usr/bin/sawtooth-validator -vv --endpoint tcp://10.96.15.213:8800 --bind component:tcp:


.. _examine-logs-kube-label:

Step 8: Examine Sawtooth Logs
=============================

The Sawtooth log files are available on the Kubernetes dashboard.

   1. From the dashboard's overview page, click on the Sawtooth pod name.

   #. On the Sawtooth pod page, click on the LOGS button.

   #. On Logs page, select the Sawtooth component. For example, to view the
      validator log messages, select ``sawtooth-validator``.

      The following extract shows the genesis block being processed and
      committed to the blockchain.

        .. code-block:: console

           writing file: /etc/sawtooth/keys/validator.priv
           writing file: /etc/sawtooth/keys/validator.pub
           Generated config-genesis.batch
            .
            .
            .
           [2018-08-16 19:12:51.106 INFO     genesis] Producing genesis block from /var/lib/sawtooth/genesis.batch
           [2018-08-16 19:12:51.106 DEBUG    genesis] Adding 1 batches
           [2018-08-16 19:12:51.107 DEBUG    executor] no transaction processors registered for processor type sawtooth_settings: 1.0
           [2018-08-16 19:12:51.108 INFO     executor] Waiting for transaction processor (sawtooth_settings, 1.0)
           [2018-08-16 19:12:51.120 INFO     processor_handlers] registered transaction processor: connection_id=57ec10822a6345a908533ea00c44dbdacbe029e6073b3b709bd144e7275aae6f5f1a01de529664861c7598eb4e87dcd229a474fb868958cbee72b0b307311a5e, family=xo, version=1.0, namespaces=['5b7349']
           [2018-08-16 19:12:51.191 INFO     processor_handlers] registered transaction processor: connection_id=bdbf6d96c1b456a311e7a12842765d8061af1bbefb47f9923379ccdf9f07076da1b6a65028ebd31fe5f84cdb3adfdfa1cc9d98b1b46265b49e47250e04e08910, family=intkey, version=1.0, namespaces=['1cf126']
           [2018-08-16 19:12:51.198 INFO     processor_handlers] registered transaction processor: connection_id=084ecc34848d7293821a3f2c58adc4f703572a368783afd901004bfd982e82ce5fe6e1f6e6e08de9fe6fc25c98ae20e55fa493f4f510824a2bb4a5fe00210c81, family=sawtooth_settings, version=1.0, namespaces=['000000']
           [2018-08-16 19:12:51.235 DEBUG    genesis] Produced state hash 0e682c25c3390a718ec560bb45d5180924f255210d9d4521eaac019800603731 for genesis block.
           [2018-08-16 19:12:51.238 INFO     genesis] Genesis block created: 20d7b6657721758d1ad1a3392daadd57473d84e1e1c8c58c14ec862ff7fbf44a3bef4d82c40052dd8fc2808191f830447df59fe074aea02a000ff64bc458e256 (block_num:0, state:0e682c25c3390a718ec560bb45d5180924f255210d9d4521eaac019800603731, previous_block_id:0000000000000000)
           [2018-08-16 19:12:51.238 DEBUG    chain_id_manager] writing block chain id
           [2018-08-16 19:12:51.239 DEBUG    genesis] Deleting genesis data.
           [2018-08-16 19:12:51.239 DEBUG    selector_events] Using selector: ZMQSelector
           [2018-08-16 19:12:51.240 INFO     interconnect] Listening on tcp://eth0:8800
           [2018-08-16 19:12:51.241 DEBUG    dispatch] Added send_message function for connection ServerThread
           [2018-08-16 19:12:51.241 DEBUG    dispatch] Added send_last_message function for connection ServerThread
           [2018-08-16 19:12:51.243 DEBUG    gossip] Number of peers (0) below minimum peer threshold (3). Doing topology search.
           [2018-08-16 19:12:51.244 INFO     chain] Chain controller initialized with chain head: 20d7b6657721758d1ad1a3392daadd57473d84e1e1c8c58c14ec862ff7fbf44a3bef4d82c40052dd8fc2808191f830447df59fe074aea02a000ff64bc458e256 (block_num:0, state:0e682c25c3390a718ec560bb45d5180924f255210d9d4521eaac019800603731, previous_block_id:0000000000000000)
           [2018-08-16 19:12:51.244 INFO     publisher] Now building on top of block: 20d7b6657721758d1ad1a3392daadd57473d84e1e1c8c58c14ec862ff7fbf44a3bef4d82c40052dd8fc2808191f830447df59fe074aea02a000ff64bc458e256 (block_num:0, state:0e682c25c3390a718ec560bb45d5180924f255210d9d4521eaac019800603731, previous_block_id:0000000000000000)

You can also access a component's log messages by connecting to the container
and examining the local log files. In each container, the Sawtooth log files for
that component are stored in the directory ``/var/log/sawtooth``. Each component
(validator, REST API, and transaction processors) has both a debug log and an
error log.

For example, you can connect to the validator container and display the contents
of ``/var/log/sawtooth``:

.. code-block:: console

   $ kubectl exec -it $(kubectl get pods | awk '/sawtooth-0/{print $1}') --container sawtooth-validator -- bash
   root@sawtooth-0# ls -1 /var/log/sawtooth
   validator-debug.log
   validator-error.log

.. note::

   By convention, the log files for the transaction processors use a random
   string to make the log file names unique. For example:

   .. code-block:: console

      $ kubectl exec -it $(kubectl get pods | awk '/sawtooth-0/{print $1}') --container sawtooth-intkey-tp-python -- bash

      root@sawtooth-0# ls -1 /var/log/sawtooth
      intkey-ae98c3726f9743c4-debug.log
      intkey-ae98c3726f9743c4-error.log

For more information on log files, see
:doc:`../sysadmin_guide/log_configuration`.


.. _stop-sawtooth-kube-label:

Step 9: Stop the Sawtooth Kubernetes Cluster
============================================

Use the following commands to stop and reset the Sawtooth environment.

.. important::

  Any work done in this environment will be lost once you delete the Sawtooth
  cluster. To keep your work, you would need to take additional steps, such as
  defining volume storage.  See the
  `Kubernetes documentation <https://kubernetes.io/docs/home/>`_ for more
  information.

#. Log out of all Sawtooth containers.


#. Stop Sawtooth and delete the pod. Run the following command from the same
   directory where you saved the configuration file.

   .. code-block:: console

      $ kubectl delete -f sawtooth-kubernetes-default.yaml
      deployment.extensions "sawtooth-0" deleted
      service "sawtooth-0" deleted

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
