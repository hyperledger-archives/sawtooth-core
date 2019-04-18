.. _proc-multi-kube-label:

Using Kubernetes for a Sawtooth Test Network
============================================

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

About the Kubernetes Sawtooth Network Environment
-------------------------------------------------

This environment is a network of five Sawtooth node. Each node has a
:term:`validator`, a :term:`REST API`, and four
:term:`transaction processors<transaction processor>`. This environment uses
:ref:`PoET mode consensus <dynamic-consensus-label>`,
:doc:`parallel transaction processing <../architecture/scheduling>`,
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


Prerequisites
-------------

This application development environment requires
`kubectl <https://kubernetes.io/docs/concepts/overview/object-management-kubectl/overview/>`_
and
`Minikube <https://kubernetes.io/docs/setup/minikube/>`_ with a supported VM
hypervisor, such as VirtualBox.


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
