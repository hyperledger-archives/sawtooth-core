
.. _tutorial:

********
Tutorial
********

Overview
========

This tutorial walks through the process of setting up a virtual development
environment for the Distributed Ledger using Docker or Virtualbox/Vagrant.
At the end, you will have a running validator and a running transaction
processor. You will have submitted transactions to the validator.

Additional sections guide you in the following tasks:

* `Config Transaction Family Usage`_
* `Viewing Blocks and State`_

Commands in this tutorial can be run via Terminal.app on MacOS, Git Bash on
Windows, etc.

Clone Repository
----------------

You'll need to have git installed in order to clone the Sawtooth Lake source
code repository. You can find up-to-date installation instructions here:

* `Git install instructions <https://git-scm.com/book/en/v2/Getting-Started-Installing-Git>`_

.. note:: 

  When checking out Sawtooth Lake on Windows for use with vagrant, you should
  take steps to ensure that Windows-style CRLF line endings are not added to
  the code. The bash scripts used by your vagrant VM will not run correctly 
  with CRLF line endings. Git uses a configuration setting, *core.autocrlf*,
  to control whether or not LF-style line endings are automatically converted
  to CRLF-style line endings. `This setting should be set in such a way that 
  CRLFs are not introduced into your repository 
  <https://git-scm.com/book/en/v2/Customizing-Git-Git-Configuration>`_.

Open up a terminal and run the following:

.. code-block:: console

   % cd $HOME
   % mkdir project
   % cd project
   % git clone https://github.com/hyperledger/sawtooth-core.git

.. note::

  On a Windows environment, the suggested version of the last command
  above is:

  .. code-block:: console

      C:\> git clone https://github.com/hyperledger/sawtooth-core.git
      --config core.autocrlf=false

Docker Instructions
===================

Prerequisites
-------------

The following tools are required:

* `Docker Engine <https://docs.docker.com/engine/installation/>`_ (17.03.0-ce
  or later)
* `Docker Compose <https://docs.docker.com/compose/install/>`_ (Linux only)

Environment Startup
-------------------

To start up the environment, run:

.. code-block:: console

  % cd sawtooth-core
  % docker-compose -f docker/compose/sawtooth-demo.yaml up

Downloading the docker images that comprise the Sawtooth Lake demo
environment can take serveral minutes. Once you see the containers
registering and creating intial blocks you can move on to the next step.

.. code-block:: console

  Attaching to compose_validator_1, compose_tp_xo_python_1, compose_client_1, compose_tp_intkey_python_1, compose_tp_config_1, compose_rest_api_1
  validator_1         | writing file: /etc/sawtooth/keys/validator.wif
  validator_1         | writing file: /etc/sawtooth/keys/validator.addr
  validator_1         | Generating /var/lib/sawtooth/genesis.batch
  tp_xo_python_1      | [19:03:47 DEBUG   selector_events] Using selector: ZMQSelector
  validator_1         | [19:03:47.537 INFO     path] Skipping path loading from non-existent config file: /etc/sawtooth/path.toml
  tp_xo_python_1      | [19:03:47 INFO    core] register attempt: OK
  validator_1         | [19:03:47.538 INFO     cli] config [path]: config_dir = "/etc/sawtooth"
  tp_intkey_python_1  | [19:03:47 DEBUG   selector_events] Using selector: ZMQSelector
  validator_1         | [19:03:47.538 INFO     cli] config [path]: key_dir = "/etc/sawtooth/keys"
  tp_intkey_python_1  | [19:03:47 INFO    core] register attempt: OK

Open a new terminal so we can connect to the client container:

.. code-block:: console

  % docker exec -it compose_client_1 bash

Your environment is ready! Continue on to `Multi-language support for transaction processors`_.

Resetting The Environment
-------------------------

If the environment needs to be reset for any reason, it can be returned to
the default state by logging out of the client container, then pressing
CTRL-c from the window where you originally ran docker-compose. Once the
containers have all shut down run 'docker-compose -f sawtooth-demo.yaml down'.

.. code-block:: console

  validator_1         | [00:27:56.753 DEBUG    interconnect] message round trip: TP_PROCESS_RESPONSE 0.03986167907714844
  validator_1         | [00:27:56.756 INFO     chain] on_block_validated: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  validator_1         | [00:27:56.761 INFO     chain] Chain head updated to: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  validator_1         | [00:27:56.762 INFO     publisher] Now building on top of block: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  validator_1         | [00:27:56.763 INFO     chain] Finished block validation of: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  Gracefully stopping... (press Ctrl+C again to force)
  Stopping compose_tp_xo_python_1 ... done
  Stopping compose_tp_config_1 ... done
  Stopping compose_client_1 ... done
  Stopping compose_rest_api_1 ... done
  Stopping compose_tp_intkey_python_1 ... done
  Stopping compose_validator_1 ... done

  % docker-compose -f sawtooth-demo.yaml down

Vagrant and Virtualbox Instructions
===================================

Prerequisites
-------------

The following tools are required:

* `Vagrant <https://www.vagrantup.com/downloads.html>`_ (1.9.0 or later)
* `VirtualBox <https://www.virtualbox.org/wiki/Downloads>`_ (5.1.16 r113841
  or later)

Environment Startup
-------------------

In order to start the vagrant VM, run:

.. code-block:: console

  % cd sawtooth-core/tools
  % vagrant up

.. note::

   We have encountered an intermittent problem on Windows hosts which
   presents as an 'Operation not permitted' error in the vagrant startup
   output. If you encounter this error, perform a 'vagrant destroy' and
   then run 'vagrant up' again.

Downloading the Vagrant box file, booting the VM, and running through
the bootstrap scripts will take several minutes.

Once the 'vagrant up' command has finished executing, run:

.. code-block:: console

  % vagrant ssh

By default, Vagrant sets up ssh keys so that users can log into the VM
without setting up additional accounts or credentials. The logged in user,
vagrant (uid 1000), also has permissions to execute sudo with no password
required. Any number of `vagrant ssh` sessions can be established from the
host.

.. note::

   Occasionally, the configuration files used to create the vagrant
   environment change and this can result in vagrant asking for a password when
   doing `vagrant up` or `vagrant ssh`. This is usually a sign that your
   environment is out of date. If this happens, please follow the instructions
   below to reset your environment. This is especially common when switching
   between versions of Sawtooth Lake, eg. 0.7 -> 0.8.

Resetting The Environment
-------------------------

If the VM needs to be reset for any reason, it can be returned to the default
state by running the following commands from the sawtooth-core/tools directory
on the host:

.. code-block:: console

  % vagrant destroy
  % vagrant up

.. warning::

   vagrant destroy will delete all contents within the VM. However,
   /vagrant and /project are shared with the host and will be preserved.

Building sawtooth-core
----------------------

Most of the components of Sawtooth Lake depend partially on code that must
first be built. This includes C++/swig code and generating protobuf classes for
each language. Sawtooth Lake also includes SDKs for other languages, including
Java and JavaScript, which require building. To build the python portion of
Sawtooth Lake within vagrant, do:

.. code-block:: console

  $ /project/sawtooth-core/bin/build_python

This will allow you to run and test Sawtooth Lake components manually. The
automated tests for python and all other languages rely on docker to ensure
reproducibility. To run the automated tests for python, first run the
following:

.. code-block:: console

  $ /project/sawtooth-core/bin/build_all -l python

This will create docker images for all the python components and run
`build_python` inside a build container. You can then run the automated tests
with:

.. code-block:: console

  $ /project/sawtooth-core/bin/run_tests -x java_sdk -x javascript_sdk

If you are not behind a proxy, you can build and test everything Sawtooth Lake
has to offer with:

.. code-block:: console

  $ /project/sawtooth-core/bin/build_all
  $ /project/sawtooth-core/bin/run_tests


Validator Start-up Process
==========================

.. caution::

  Genesis block and validator startup are handled for you if you're using the
  Docker workflow. You can skip to `Multi-language support for transaction processors`_
  if you'd like, or keep reading to better understand the startup process.

Create Genesis Block
--------------------

In most use cases, it is not necessary to create a genesis block when starting
a validator, because the validator joins an existing distributed ledger
network. However, as a developer, you may often need to create short-lived
test networks. In this case, you need to create a genesis block when
instantiating a new network.

The genesis block contains some initial values that are necessary when a
Sawtooth Lake distributed ledger is created and used for the first time.

To create the genesis block, log in to the development environment with the
command `vagrant ssh` and run the following command:

.. code-block:: console

  $ sawtooth admin genesis
  Generating /home/ubuntu/sawtooth/data/genesis.batch


.. note:: 

  If you need to delete previously existing block-chain data before running a
  validator in the vagrant environment, simply run the following command: 
  `rm /home/ubuntu/sawtooth/data/*`


Start Validator
---------------

To start a validator, log in to the development environment with `vagrant ssh`
and run the following commands:

.. code-block:: console

   $ cd sawtooth-core/
   $ sawtooth keygen --key-dir /home/ubuntu/sawtooth/keys/ validator
   $ validator -vv

.. note::

  To run the validator with less verbose logging, use the command `validator -v`.

This will start the validator. Logging output will be printed to the
terminal window. The validator outputs something similar to this to
the terminal window:

.. code-block:: console

  [16:18:30.145 INFO    chain] Chain controller initialized with chain head: None
  [16:18:30.145 INFO    publisher] Now building on top of block: None

To stop the validator, press CTRL-c.


Running a transaction processor
===============================

.. caution::

  The necessary transaction processors are started automatically if you're
  using Docker with this tutorial. Keep reading if for more information about
  transaction processors or skip ahead to
  `Multi-language support for transaction processors`_.

Transaction processors can be started either before or after the validator is
started.

To start an intkey transaction processor, log in to the development
environment with  `vagrant ssh` and run the following commands:

.. code-block:: console

  $ cd sawtooth-core/
  $ tp_intkey_python -v tcp://127.0.0.1:40000

This will start a transaction processor that includes an **intkey** handler, 
which can understand and process transactions that use the built-in intkey
transaction family. The processor communicates with the validator on 
TCP port 40000. 

The endpoint (`tcp://127.0.0.1:40000` in this example) to connect to must be
specified when starting the transaction processor. This tells the transaction
processor which validator to connect to. This is useful, because it is
possible to run transaction processors on separate machines.

The transaction processor produces the following output:

.. code-block:: console

  [23:07:57 INFO    core] register attempt: OK

.. note:: 

  In a production environment, you should always run a transaction processor
  that supports the config transaction family. See `Config Transaction
  Family Usage`_ for more information.

To stop the transaction processor, press CTRL-c.


Multi-language support for transaction processors
=================================================

Sawtooth Lake includes additional transaction processors:

* tp_config

  - A config family transaction processor written in Python

* tp_intkey_java

  - An intkey transaction processor written in Java

* tp_intkey_javascript

  - An intkey transaction processor written in JavaScript
  - Requires node.js 

* tp_intkey_jvm_sc

  - An intkey transaction processor implemented as a smart contract.
  - The bytecode to run a transaction is stored in state and the blockchain.
  - Requires Java

* tp_validator_registry

  - A transaction family used by the PoET consensus algorithm implementation 
    to keep track of other validators.

* tp_xo_python

  - An XO transaction processor written in Python


Creating And Submitting Transactions
====================================

The **intkey** command is provided to create sample transactions of the intkey
transaction type for testing purposes.

This section guide you through the following tasks:

1. Prepare a batch of intkey transactions that set the keys to random values.

2. Generate *inc* (increment) and *dec* (decrement) transactions to apply to
   the existing state stored in the blockchain.

3. Submit these transactions to the validator.

Run the following commands from the Vagrant CLI:

.. code-block:: console

  $ intkey create_batch
  $ intkey load -f batches.intkey

Or from the Docker CLI:

.. code-block:: console

  $ intkey create_batch
  $ intkey load -f batches.intkey -U tcp://validator:40000

You can observe the processing of the intkey transactions by observing the
logging output of the validator. A truncated example of the validator's output
is shown below:

.. code-block:: console

  [19:29:26 INFO    core] register attempt: OK
  [19:31:06 INFO    handler] processing: Verb=set Name=eBuPof Value=99811 address=1cf126c584128aaf1837c90c83748ab222c11b8bbd2fe6cc30f17fe35f2acb9af8efd4ee3f092b676546316cf85b2e929b68d9c5314e93ac318ba527ec74aa3ed1bc2e
  [19:31:06 INFO    handler] processing: Verb=set Name=HOUUQS Value=10140 address=1cf126380fa9e716a05ac815741fd1960d5952e60f8747e13334f79504c57d0287b77cf9b78284d0e1544f6f0366d66c6e6eb99dc5c154b84175b2d20008d721c7b623
  [19:31:06 INFO    handler] processing: Verb=set Name=lrnuDC Value=92318 address=1cf12617c797cf8c27254bbdb5c9bda09f9405b9494ae32b79b9b6d30881ca8552d5932a68f703d1b6754b9feb2edafa76a797fc0826110381b0f8614f2c6853316b47
  [19:31:06 INFO    handler] processing: Verb=set Name=BKaiql Value=94175 address=1cf12669cbc17d076a1accb4b0bb61f40ed4f999173b90e3ca2591875a55fee2947661e60fa1c57b41ef0f2660176b945a01c85ff645543297068a3fb1306324a19612
  [19:31:06 INFO    handler] processing: Verb=set Name=wpMQmE Value=47316 address=1cf1260f6bdf66b65ff7c00ec58c4deccffd167bfee7a85698880dfa485df3de1ec18a5b2d1dc12849743d1c74320108360a2d40d223b35fbc1c4ea03bbd8306480c62
  [19:31:06 INFO    handler] processing: Verb=set Name=GTgrvP Value=31921 address=1cf12606ac7db03c756133c07d7d02b59f3ef9eae6774fe59c75c88ab66a9fabbbaef9975dbf9aa197d1090ed126d7b18e2


Config Transaction Family Usage
===============================

Sawtooth Lake provides a :doc:`config transaction family
<transaction_family_specifications/config_transaction_family>` that stores on-
chain configuration settings, along with a config family transaction
processor written in Python.

.. caution::

  A config transaction processor container and rest api container are started
  for you if you're using the Docker workflow. You can skip to
  `Step Three: Create And Submit Batch`_ or read on to learn how to start
  the config transaction processor and rest api.

One of the on-chain settings is the list of supported transaction families. 
To configure this setting, follow these steps:

Step One: Start Config Family Processor
---------------------------------------

To start the config family transaction processor, run the following commands from the 
Vagrant CLI:

.. code-block:: console

  $ tp_config tcp://localhost:40000

Confirm that the transaction processor registers with the validator by viewing the Vagrant shell 
in which the validator is running. A successful registration event produces the following output:

.. code-block:: console
  
  [21:03:55.955 INFO    processor_handlers] registered transaction processor: identity=b'6d2d80275ae280ea', family=sawtooth_config, version=1.0, encoding=application/protobuf, namespaces=<google.protobuf.pyext._message.RepeatedScalarContainer object at 0x7e1ff042f6c0>
  [21:03:55.956 DEBUG   interconnect] ServerThread sending TP_REGISTER_RESPONSE to b'6d2d80275ae280ea'


Step Two: Starting the Rest API
-------------------------------

In order to configure a running validator, you must start the REST API
application. Run the following command to start the rest api:

.. code-block:: console
  
  rest_api --stream-url tcp://127.0.0.1:40000


Step Three: Create And Submit Batch
-----------------------------------

In the example below, a JSON array is submitted to the `sawtooth config`
command, which creates and submits a batch of transactions containing the
configuration change.

The JSON array used tells the validator or validator network to accept transactions of the following types:

* intkey
* sawtooth_config

To create and submit the batch containing the new configuration, enter the
following commands from the Vagrant CLI:

.. code-block:: console

  $ sawtooth keygen my_key
  $ sawtooth config proposal create --key /home/ubuntu/.sawtooth/keys/my_key.wif sawtooth.validator.transaction_families='[{"family": "intkey", "version": "1.0", "encoding": "application/protobuf"}, {"family":"sawtooth_config", "version":"1.0", "encoding":"application/protobuf"}]'
  
Or from the Docker CLI:

.. code-block:: console

  $ sawtooth keygen my_key
  $ sawtooth config proposal create --key /root/.sawtooth/keys/my_key.wif sawtooth.validator.transaction_families='[{"family": "intkey", "version": "1.0", "encoding": "application/protobuf"}, {"family":"sawtooth_config", "version":"1.0", "encoding":"application/protobuf"}]' --url http://rest_api:8080

A TP_PROCESS_REQUEST message appears in the logging output of the validator.


Viewing Blocks and State
========================

You can view the blocks stored in the block-chain, and the nodes of the Markle
tree, using the sawtooth CLI.

.. note::
  
  The sawtooth CLI provides help for all subcommands. For example, to get help
  for the `block` subcommand, enter the command `sawtooth block -h`.

Log in to the Vagrant environment with the command `vagrant ssh` to run the commands below.


Starting the Rest API
---------------------

.. caution::

  As with the transaction processors above, a rest api container is
  started for you with the Docker workflow.


In order to submit queries to the validator, you must start the REST API
application. Run the following command to start the rest api:

.. code-block:: console
  
  rest_api --stream-url tcp://127.0.0.1:40000


Viewing List Of Blocks
----------------------

Enter the command `sawtooth block list` to view the blocks stored by the state:

In Vagrant:

.. code-block:: console

  $ sawtooth block list

In Docker:

.. code-block:: console

  $ sawtooth block list --url http://rest_api:8080

.. code-block:: console

  NUM  BLOCK_ID  
  8    22e79778855768ea380537fb13ad210b84ca5dd1cdd555db7792a9d029113b0a183d5d71cc5558e04d10a9a9d49031de6e86d6a7ddb25325392d15bb7ccfd5b7  2     8     02a0e049...
  7    c84346f5e18c6ce29f1b3e6e31534da7cd538533457768f86a267053ddf73c4f1139c9055be283dfe085c94557de24726191eee9996d4192d21fa6acb0b29152  2     20    02a0e049...
  6    efc0d6175b6329ac5d0814546190976bc6c4e18bd0630824c91e9826f93c7735371f4565a8e84c706737d360873fac383ab1cf289f9bf640b92c570cb1ba1875  2     27    02a0e049...
  5    840c0ef13023f93e853a4555e5b46e761fc822d4e2d9131581fdabe5cb85f13e2fb45a0afd5f5529fbde5216d22a88dddec4b29eeca5ac7a7b1b1813fcc1399a  2     16    02a0e049...
  4    4d6e0467431a409185e102301b8bdcbdb9a2b177de99ae139315d9b0fe5e27aa3bd43bda6b168f3ac8f45e84b069292ddc38ec6a1848df16f92cd35c5bd6e6c9  2     20    02a0e049...
  3    9743e39eadf20e922e242f607d847445aba18dacdf03170bf71e427046a605744c84d9cb7d440d257c21d11e4da47e535ba7525afcbbc037da226db48a18f4a8  2     22    02a0e049...
  2    6d7e641232649da9b3c23413a31db09ebec7c66f8207a39c6dfcb21392b033163500d367f8592b476e0b9c1e621d6c14e8c0546a7377d9093fb860a00c1ce2d3  2     38    02a0e049...
  1    7252a5ab3440ee332aef5830b132cf9dc3883180fb086b2a50f62bf7c6c8ff08311b8009da3b3f6e38d3cfac1b3ac4cfd9a864d6a053c8b27df63d1c730469b3  2     120   02a0e049...
  0    8821a997796f3e38a28dbb8e418ed5cbdd60b8a2e013edd20bca7ebf9a58f1302740374d98db76137e48b41dc404deda40ca4d2303a349133991513d0fec4074  0     0     02a0e049...


Viewing A Particular Block
--------------------------

Using the `sawtooth block list` command as shown above, copy the block id you want to 
view, then use the `sawtooth block show` command (truncated output shown):

In Vagrant:

.. code-block:: console

    $ sawtooth block show 22e79778855768ea380537fb13ad210b84ca5dd1cdd555db7792a9d029113b0a183d5d71cc5558e04d10a9a9d49031de6e86d6a7ddb25325392d15bb7ccfd5b7

In Docker:

.. code-block:: console

    $ sawtooth block show --url http://rest_api:8080 22e79778855768ea380537fb13ad210b84ca5dd1cdd555db7792a9d029113b0a183d5d71cc5558e04d10a9a9d49031de6e86d6a7ddb25325392d15bb7ccfd5b7

.. code-block:: console

    batches:
  - header:
      signer_pubkey: 0380be3421629849b1d03af520d7fa2cdc24c2d2611771ddf946ef3aaae216be84
      transaction_ids:
      - c498c916da09450597053ada1938858a11d94e2ed5c18f92cd7d34b865af646144d180bdc121a48eb753b4abd326baa3ea26ee8a29b07119052320370d24ab84
      - c68de164421bbcfcc9ea60b725bae289aecd02ddde6f520e6e85b3227337e2971e89bbff468bdebe408e0facc343c612a32db98e5ac4da2296a7acf4033073cd
      - faf9121f9744716363253cb0ff4b6011093ada6e19dae63ae04a58a1fca25424779a13628a047c009d2e73d0e7baddc95b428b4a22cf1c60961d6dcae8ee60fa
    header_signature: 2ff874edfa80a8e6b718e7d10e91970150fcc3fcfd46d38eb18f356e7a733baa40d9e816247985d7ea7ef2492c09cd9c1830267471c6e35dca0d19f5c6d2b61e
    transactions:
    - header:
        batcher_pubkey: 0380be3421629849b1d03af520d7fa2cdc24c2d2611771ddf946ef3aaae216be84
        dependencies:
        - 19ad647bd292c980e00f05eed6078b471ca2d603b842bc4eaecf301d61f15c0d3705a4ec8d915ceb646f35d443da43569f58c906faf3713853fe638c7a0ea410
        family_name: intkey
        family_version: '1.0'
        inputs:
        - 1cf126c15b04cb20206d45c4d0e432d036420401dbd90f064683399fae55b99af1a543f7de79cfafa4f220a22fa248f8346fb1ad0343fcf8d7708565ebb8a3deaac09d
        nonce: 0x1.63021cad39ceep+30
        outputs:
        - 1cf126c15b04cb20206d45c4d0e432d036420401dbd90f064683399fae55b99af1a543f7de79cfafa4f220a22fa248f8346fb1ad0343fcf8d7708565ebb8a3deaac09d
        payload_encoding: application/cbor
        payload_sha512: 942a09c0254c4a5712ffd152dc6218fc5453451726d935ac1ba67de93147b5e7be605da7ab91245f48029b41f493a1cc8dfc45bb090ac97420580eb1bdded01f
        signer_pubkey: 0380be3421629849b1d03af520d7fa2cdc24c2d2611771ddf946ef3aaae216be84
      header_signature: c498c916da09450597053ada1938858a11d94e2ed5c18f92cd7d34b865af646144d180bdc121a48eb753b4abd326baa3ea26ee8a29b07119052320370d24ab84
      payload: o2ROYW1lZnFrbGR1emVWYWx1ZQFkVmVyYmNpbmM=



Viewing The State
-----------------

Use the command `sawtooth state list` to list the nodes in the Merkle tree (truncated list):

In Vagrant:

.. code-block:: console

  $ sawtooth state list

In Docker:

.. code-block:: console

  $ sawtooth state list --url http://rest_api:8080

.. code-block:: console

  ADDRESS                                                                                                                                SIZE DATA
  1cf126ddb507c936e4ee2ed07aa253c2f4e7487af3a0425f0dc7321f94be02950a081ab7058bf046c788dbaf0f10a980763e023cde0ee282585b9855e6e5f3715bf1fe 11   b'\xa1fcCTdcH\x...
  1cf1260cd1c2492b6e700d5ef65f136051251502e5d4579827dc303f7ed76ddb7185a19be0c6443503594c3734141d2bdcf5748a2d8c75541a8e568bae063983ea27b9 11   b'\xa1frdLONu\x...
  1cf126ed7d0ac4f755be5dd040e2dfcd71c616e697943f542682a2feb14d5f146538c643b19bcfc8c4554c9012e56209f94efe580b6a94fb326be9bf5bc9e177d6af52 11   b'\xa1fAUZZqk\x...
  1cf126c46ff13fcd55713bcfcf7b66eba515a51965e9afa8b4ff3743dc6713f4c40b4254df1a2265d64d58afa14a0051d3e38999704f6e25c80bed29ef9b80aee15c65 11   b'\xa1fLvUYLk\x...
  1cf126c4b1b09ebf28775b4923e5273c4c01ba89b961e6a9984632612ec9b5af82a0f7c8fc1a44b9ae33bb88f4ed39b590d4774dc43c04c9a9bd89654bbee68c8166f0 13   b'\xa1fXHonWY\x...
  1cf126e924a506fb2c4bb8d167d20f07d653de2447df2754de9eb61826176c7896205a17e363e457c36ccd2b7c124516a9b573d9a6142f031499b18c127df47798131a 13   b'\xa1foWZXEz\x...
  1cf126c295a476acf935cd65909ed5ead2ec0168f3ee761dc6f37ea9558fc4e32b71504bf0ad56342a6671db82cb8682d64689838731da34c157fa045c236c97f1dd80 13   b'\xa1fadKGve\x...



Viewing Data In A Node
----------------------

Using the `sawtooth state list` command show above, copy the node id you want to view, then use the `sawtooth state show` command to view the node:

In Vagrant:

.. code-block:: console

  $ sawtooth state show 1cf126ddb507c936e4ee2ed07aa253c2f4e7487af3a0425f0dc7321f94be02950a081ab7058bf046c788dbaf0f10a980763e023cde0ee282585b9855e6e5f3715bf1fe

In Docker:

.. code-block:: console

  $ sawtooth state show --url http://rest_api:8080 1cf126ddb507c936e4ee2ed07aa253c2f4e7487af3a0425f0dc7321f94be02950a081ab7058bf046c788dbaf0f10a980763e023cde0ee282585b9855e6e5f3715bf1fe

.. code-block:: console

  DATA: "b'\xa1fcCTdcH\x192B'"
  HEAD: "0c4364c6d5181282a1c7653038ec9515cb0530c6bfcb46f16e79b77cb524491676638339e8ff8e3cc57155c6d920e6a4d1f53947a31dc02908bcf68a91315ad5"


Using Sawtooth Cluster To Start A Network
=========================================

.. caution::

  The sawtooth cluster command is not intended for use inside the Docker
  environment.

The `sawtooth cluster` command can be used to start a network of validators
and transaction processors. 

The following command will start a network of two validators and two transaction processors:

.. code-block:: console

  $ sawtooth cluster start --count 2 -m subprocess -P tp_intkey_python

You can view the running processes that are part of the network with the
following command:

.. code-block:: console

  $ ps -ef | grep python
  ubuntu   26036 22422 14 22:59 pts/0    00:00:02 python /project/sawtooth-core/bin/sawtooth cluster start --count 2 -m subprocess -P tp_intkey_python
  ubuntu   26039 26036  7 23:00 pts/0    00:00:00 python3 /project/sawtooth-core/bin/validator --component-endpoint 0.0.0.0:40000 --network-endpoint tcp://0.0.0.0:8800
  ubuntu   26040 26036  8 23:00 pts/0    00:00:00 python3 /project/sawtooth-core/bin/tp_intkey_python 0.0.0.0:40000
  ubuntu   26041 26036  7 23:00 pts/0    00:00:00 python3 /project/sawtooth-core/bin/validator --component-endpoint 0.0.0.0:40001 --network-endpoint tcp://0.0.0.0:8801
  ubuntu   26042 26036  7 23:00 pts/0    00:00:00 python3 /project/sawtooth-core/bin/tp_intkey_python 0.0.0.0:40001


To submit sample transactions, follow the steps above under
`Creating and submitting transactions`_.

To stop a running network that was started using the subprocess management
method, simply press CTRL-c.
