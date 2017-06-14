**************************
Using Sawtooth with Docker
**************************


This document walks through the process of setting up Hyperledger Sawtooth
for application development using Docker Compose, introduces some of the basic
Sawtooth concepts necessary for application development, and walks through
performing the following tasks:

* Submit transactions to the REST API
* View blocks, transactions, and state with the sawtooth CLI tool
* Start and stop validators and transaction processors


Upon completing this tutorial, you will be prepared for the more advanced
tutorials that guide you in performing app development tasks, such as
implementing business logic with transaction families and writing clients
which use Sawtooth's REST API.

Overview Sawtooth Components
============================

A running Sawtooth network consists of the following applications or processes:

.. image:: ../images/hyperledger_sawtooth_components.*
   :width: 80%
   :align: center
   :alt: Sawtooth components

This diagram represents a simple network with just two validators and two
transaction processors. The second validator's transaction processors are not
depicted.


Installing Docker Engine and Docker Compose
===========================================

On Windows and macOS, install the latest version of `Docker Engine <https://docs.docker.com/engine/installation/>`_.

  - On Windows and macOS, Docker Compose is installed automatically
    when you install Docker Engine.

On Linux, install both `Docker Engine <https://docs.docker.com/engine/installation/>`_ and `Docker Compose <https://docs.docker.com/compose/install/>`_.

.. warning::

  Note that the minimum version of Docker Engine necessary is 17.03.0-ce.
  Linux distributions often ship with older versions of Docker.


Installation
============

Download the Docker Compose File
--------------------------------

A Docker Compose file is provided which defines the process for constructing a
simple Sawtooth environment. This environment includes the following
containers:

* A single validator using dev-mode consensus
* A REST-API connected to the validator
* Settings, IntegerKey, and XO transaction processors
* A client container for running the CLI tools

The compose file also specifies the container images to download from Docker
Hub and the network settings needed for all the containers to communicate
correctly.

This docker compose file can serve as the basis for your own multi-container
sawtooth development environment or application.

Download the docker compose file `here <./sawtooth-default.yaml>`_.

Environment Startup
-------------------

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


Downloading the docker images that comprise the Sawtooth demo
environment can take several minutes. Once you see the containers
registering and creating initial blocks you can move on to the next step.

.. code-block:: console

  Attaching to sawtooth-validator-default, sawtooth-tp_xo_python-default, sawtooth-tp_intkey_python-default, sawtooth-rest_api-default, sawtooth-tp_settings-default, sawtooth-client-default
  sawtooth-validator-default | writing file: /etc/sawtooth/keys/validator.priv
  sawtooth-validator-default | writing file: /etc/sawtooth/keys/validator.pub
  sawtooth-validator-default | creating key directory: /root/.sawtooth/keys
  sawtooth-validator-default | writing file: /root/.sawtooth/keys/my_key.priv
  sawtooth-validator-default | writing file: /root/.sawtooth/keys/my_key.pub
  sawtooth-validator-default | Generated config-genesis.batch
  sawtooth-validator-default | Processing config-genesis.batch...
  sawtooth-validator-default | Generating /var/lib/sawtooth/genesis.batch

Open a new terminal so we can connect to the client container:

.. code-block:: console

  % docker exec -it sawtooth-client-default bash

The client container is used to run sawtooth CLI commands, which is the usual
way to interact with validators or validator networks.

Your environment is ready for experimenting with Sawtooth. However, any work
done in this environment will be lost once the container exits. The demo
compose file provided is useful as a starting point for the creation of your
own Docker-based development environment. In order to use it for app
development, you need to take additional steps, such as mounting a host
directory into the container. See `Docker's documentation
<https://docs.docker.com/>`_ for details.


Resetting The Environment
-------------------------

If the environment needs to be reset for any reason, it can be returned to
the default state by logging out of the client container, then pressing
CTRL-c from the window where you originally ran docker-compose. Once the
containers have all shut down run 'docker-compose -f sawtooth-default.yaml down'.

.. code-block:: console

  sawtooth-validator-default         | [00:27:56.753 DEBUG    interconnect] message round trip: TP_PROCESS_RESPONSE 0.03986167907714844
  sawtooth-validator-default         | [00:27:56.756 INFO     chain] on_block_validated: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  sawtooth-validator-default         | [00:27:56.761 INFO     chain] Chain head updated to: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  sawtooth-validator-default         | [00:27:56.762 INFO     publisher] Now building on top of block: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  sawtooth-validator-default         | [00:27:56.763 INFO     chain] Finished block validation of: 44ccc3e6(1, S:910b9c23, P:05b2a651)
  Gracefully stopping... (press Ctrl+C again to force)
  Stopping sawtooth-tp_xo_python-default ... done
  Stopping sawtooth-tp_settings-default ... done
  Stopping sawtooth-client-default... done
  Stopping sawtooth-rest_api-default ... done
  Stopping sawtooth-tp_intkey_python-default ... done
  Stopping sawtooth-validator-default ... done

  % docker-compose -f sawtooth-default.yaml down


Confirming Connectivity
=======================

To confirm that a validator is up and running, and reachable from the client
container, you can use this curl command:

.. note::

  If you have reset your environment as described above in
  `Resetting The Environment`_, then be sure to restart_ your environment
  again before trying this command.

.. code-block:: console

	root@75b380886502:/# curl http://rest_api:8080/blocks

If the validator is running and reachable, the output should be similar to:

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
	        "signer_pubkey": "03061436bef428626d11c17782f9e9bd8bea55ce767eb7349f633d4bfea4dd4ae9",
	        "state_root_hash": "708ca7fbb701799bb387f2e50deaca402e8502abe229f705693d2d4f350e1ad6"
	      },
	      "header_signature": "119f076815af8b2c024b59998e2fab29b6ae6edf3e28b19de91302bd13662e6e43784263626b72b1c1ac120a491142ca25393d55ac7b9f3c3bf15d1fdeefeb3b"
	    }
	  ],
	  "head": "119f076815af8b2c024b59998e2fab29b6ae6edf3e28b19de91302bd13662e6e43784263626b72b1c1ac120a491142ca25393d55ac7b9f3c3bf15d1fdeefeb3b",
	  "link": "http://rest_api:8080/blocks?head=119f076815af8b2c024b59998e2fab29b6ae6edf3e28b19de91302bd13662e6e43784263626b72b1c1ac120a491142ca25393d55ac7b9f3c3bf15d1fdeefeb3b",
	  "paging": {
	    "start_index": 0,
	    "total_count": 1
	  }
	}root@75b380886502:/#

If the validator process, or the validator container, is not running, the curl
command will return nothing, or time out.


Transaction Processors
======================

The Docker Compose file (*sawtooth-default.yaml*) starts the following
transaction processors automatically:

* tp_settings
* tp_intkey_python
* tp_xo_python

These transaction processors handle transactions for the config, intkey, and XO transaction families, and are written in Python.


Creating And Submitting Transactions
====================================

The **intkey** command is provided to create sample transactions of the intkey
transaction type for testing purposes.

This section will show you how to:

1. Prepare a batch of intkey transactions that set some keys to random values.

2. Generate *inc* (increment) and *dec* (decrement) transactions to modify the
   the existing state stored in the blockchain.

3. Submit these transactions to the validator.

Run the following commands from the client container:

.. code-block:: console

  $ intkey create_batch --count 10 --key-count 5
  $ intkey load -f batches.intkey -U http://rest_api:8080

The terminal window in which you ran the docker-compose command will begin
logging output as the validator and intkey transaction processor handle the
transactions just submitted:

.. code-block:: console

  tp_intkey_python_1  | [21:02:53.164 DEBUG    handler] Incrementing "VaUEPt" by 1
  sawtooth-validator-default         | [21:02:53.169 DEBUG    interconnect] ServerThread receiving TP_STATE_SET_REQUEST message: 194 bytes
  sawtooth-validator-default         | [21:02:53.171 DEBUG    tp_state_handlers] SET: ['1cf126d8a50604ea6ab1b82b33705fc3eeb7199f09ff2ccbc52016bbf33ade68dc23f5']
  sawtooth-validator-default         | [21:02:53.172 DEBUG    interconnect] ServerThread sending TP_STATE_SET_RESPONSE to b'63cf2e2566714070'
  sawtooth-validator-default         | [21:02:53.176 DEBUG    interconnect] ServerThread receiving TP_PROCESS_RESPONSE message: 69 bytes
  sawtooth-validator-default         | [21:02:53.177 DEBUG    interconnect] message round trip: TP_PROCESS_RESPONSE 0.042026519775390625
  sawtooth-validator-default         | [21:02:53.182 DEBUG    interconnect] ServerThread sending TP_PROCESS_REQUEST to b'63cf2e2566714070'
  tp_intkey_python_1  | [21:02:53.185 DEBUG    core] received message of type: TP_PROCESS_REQUEST
  sawtooth-validator-default         | [21:02:53.191 DEBUG    interconnect] ServerThread receiving TP_STATE_GET_REQUEST message: 177 bytes
  sawtooth-validator-default         | [21:02:53.195 DEBUG    tp_state_handlers] GET: [('1cf126721fff0dc4ccb345fb145eb9e30cb7b046a7dd7b51bf7393998eb58d40df5f9a', b'\xa1fZeuYwh\x1a\x00\x019%')]
  sawtooth-validator-default         | [21:02:53.200 DEBUG    interconnect] ServerThread sending TP_STATE_GET_RESPONSE to b'63cf2e2566714070'
  tp_intkey_python_1  | [21:02:53.202 DEBUG    handler] Incrementing "ZeuYwh" by 1


Settings Transaction Family Usage
=================================

Sawtooth provides a :doc:`settings transaction family
<../transaction_family_specifications/settings_transaction_family>` that stores
on-chain configuration settings, along with a config family transaction
processor written in Python.

One of the on-chain settings is the list of supported transaction families.
In the example below, a JSON array is submitted to the `sawtooth config`
command, which creates and submits a batch of transactions containing the
configuration change.

The JSON array used tells the validator or validator network to accept
transactions of the following types:

* intkey
* sawtooth_config

To create and submit the batch containing the new configuration, enter the
following commands:

.. note::

  The config command needs to use a key generated in the validator container.
  Thus, you must open a terminal window running in the validator container,
  rather than the client container (for the following command only).
  Run the following command from your host machine's CLI:

.. code-block:: console

  % docker exec -it sawtooth-validator-default bash

Then run the following commands from the validator container:

.. code-block:: console

  $ sawtooth config proposal create --key /root/.sawtooth/keys/my_key.priv sawtooth.validator.transaction_families='[{"family": "intkey", "version": "1.0", "encoding": "application/protobuf"}, {"family":"sawtooth_config", "version":"1.0", "encoding":"application/protobuf"}]' --url http://rest_api:8080
  $ sawtooth config settings list --url http://rest_api:8080


A TP_PROCESS_REQUEST message appears in the logging output of the validator,
and output similar to the following appears in the validator terminal:

.. code-block:: console

  sawtooth.settings.vote.authorized_keys: 0276023d4f7323103db8d8683a4b7bc1eae1f66fbbf79c20a51185f589e2d304ce
  sawtooth.validator.transaction_families: [{"family": "intkey", "version": "1.0", "encoding": "application/protobuf"}, {"family":"sawtooth_settings", "versi...


Viewing Blocks And State
========================

You can view the blocks stored in the blockchain, and the nodes of the Merkle
tree, using the sawtooth CLI.

.. note::

  The sawtooth CLI provides help for all subcommands. For example, to get help
  for the `block` subcommand, enter the command `sawtooth block -h`.

Viewing List Of Blocks
----------------------

Enter the command `sawtooth block list` to view the blocks stored by the state:

.. code-block:: console

  $ sawtooth block list --url http://rest_api:8080

The output of the command will be similar to this:

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

.. code-block:: console

    $ sawtooth block show --url http://rest_api:8080 22e79778855768ea380537fb13ad210b84ca5dd1cdd555db7792a9d029113b0a183d5d71cc5558e04d10a9a9d49031de6e86d6a7ddb25325392d15bb7ccfd5b7

The output of the command will be similar to this:

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



Viewing Global State
--------------------

Use the command `sawtooth state list` to list the nodes in the Merkle tree
(truncated list):

.. code-block:: console

  $ sawtooth state list --url http://rest_api:8080

The output of the command will be similar to this:

.. code-block:: console

  ADDRESS                                                                                                                                SIZE DATA
  1cf126ddb507c936e4ee2ed07aa253c2f4e7487af3a0425f0dc7321f94be02950a081ab7058bf046c788dbaf0f10a980763e023cde0ee282585b9855e6e5f3715bf1fe 11   b'\xa1fcCTdcH\x...
  1cf1260cd1c2492b6e700d5ef65f136051251502e5d4579827dc303f7ed76ddb7185a19be0c6443503594c3734141d2bdcf5748a2d8c75541a8e568bae063983ea27b9 11   b'\xa1frdLONu\x...
  1cf126ed7d0ac4f755be5dd040e2dfcd71c616e697943f542682a2feb14d5f146538c643b19bcfc8c4554c9012e56209f94efe580b6a94fb326be9bf5bc9e177d6af52 11   b'\xa1fAUZZqk\x...
  1cf126c46ff13fcd55713bcfcf7b66eba515a51965e9afa8b4ff3743dc6713f4c40b4254df1a2265d64d58afa14a0051d3e38999704f6e25c80bed29ef9b80aee15c65 11   b'\xa1fLvUYLk\x...
  1cf126c4b1b09ebf28775b4923e5273c4c01ba89b961e6a9984632612ec9b5af82a0f7c8fc1a44b9ae33bb88f4ed39b590d4774dc43c04c9a9bd89654bbee68c8166f0 13   b'\xa1fXHonWY\x...
  1cf126e924a506fb2c4bb8d167d20f07d653de2447df2754de9eb61826176c7896205a17e363e457c36ccd2b7c124516a9b573d9a6142f031499b18c127df47798131a 13   b'\xa1foWZXEz\x...
  1cf126c295a476acf935cd65909ed5ead2ec0168f3ee761dc6f37ea9558fc4e32b71504bf0ad56342a6671db82cb8682d64689838731da34c157fa045c236c97f1dd80 13   b'\xa1fadKGve\x...



Viewing Data At An Address
--------------------------

Using the `sawtooth state list` command show above, copy the address want to
view, then use the `sawtooth state show` command to view the address:

.. code-block:: console

  $ sawtooth state show --url http://rest_api:8080 1cf126ddb507c936e4ee2ed07aa253c2f4e7487af3a0425f0dc7321f94be02950a081ab7058bf046c788dbaf0f10a980763e023cde0ee282585b9855e6e5f3715bf1fe


The output of the command will be similar to this:

.. code-block:: console

  DATA: "b'\xa1fcCTdcH\x192B'"
  HEAD: "0c4364c6d5181282a1c7653038ec9515cb0530c6bfcb46f16e79b77cb524491676638339e8ff8e3cc57155c6d920e6a4d1f53947a31dc02908bcf68a91315ad5"
