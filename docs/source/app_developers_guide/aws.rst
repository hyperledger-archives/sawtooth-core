***********************
Using AWS with Sawtooth
***********************

This tutorial explains how to set up Hyperledger Sawtooth for application
development using the Amazon Elastic Compute Cloud (Amazon EC2) service.
It shows you how to launch an instance of a Sawtooth validator node from the
`Amazon Web Services (AWS) Marketplace <https://aws.amazon.com/marketplace/pp/B075TKQCC2>`_,
then walks you through the following tasks:

 * Checking the status of Sawtooth components
 * Using Sawtooth commands to submit transactions, display block data, and view
   global state
 * Examining Sawtooth logs
 * Resetting the AWS Sawtooth instance

.. note::

  This environment requires an AWS account. If you don't have one yet, Amazon
  provides free accounts so you can try the Sawtooth platform. Sign up at
  `aws.amazon.com/free <https://aws.amazon.com/free/>`_.

After completing this tutorial, you will have the application development
environment that is required for the other tutorials in this guide. The next
tutorial introduces the XO transaction family by using the ``xo`` client
commands to play a game of tic-tac-toe. The final set of tutorials describe how
to use an SDK to create a transaction family that implements your application's
business logic.


About the Application Development Environment
=============================================

The AWS application development environment is a single validator node that is
running a validator, a REST API, and three transaction processors. This
environment uses Developer mode (dev mode) consensus and serial transaction
processing.

.. figure:: ../images/appdev-environment-one-node-3TPs.*
   :width: 100%
   :align: center
   :alt: AWS: Sawtooth application environment with one node

This environment introduces basic Sawtooth functionality with the
`IntegerKey <../transaction_family_specifications/integerkey_transaction_family>`_
and
`Settings <../transaction_family_specifications/settings_transaction_family>`_
transaction processors for the business logic and Sawtooth commands as a client.
It also includes the
`XO <../transaction_family_specifications/xo_transaction_family>`_
transaction processor, which is used in the advanced tutorials.

The IntegerKey and XO families are simple examples of a transaction family, but
Settings is a reference implementation. In a production environment, you should
always run a transaction processor that supports the Settings transaction
family.

.. note::

   The Amazon Machine Image (AMI) for Sawtooth has a ``systemd`` service that
   handles environment setup steps such as generating keys and creating a
   genesis block. To learn how the typical startup process works, see
   :doc:`ubuntu`.


Step 1: Launch a Sawtooth Instance
==================================

#. Launch a Sawtooth instance from the `Hyperledger Sawtooth product page
   on the AWS Marketplace <https://aws.amazon.com/marketplace/pp/B075TKQCC2>`_.
   For more information, see the Amazon guide
   `Launching an AWS Marketplace Instance
   <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/launch-marketplace-console.html>`_.

   .. note::

      The default security group with recommended settings for Sawtooth
      allows inbound SSH traffic only.

      * To attach a transaction processor remotely, add an inbound rule to
        allow TCP traffic on port 4004.

      * To access the REST API remotely, add an inbound rule to allow TCP
        traffic on port 8008.

      * To communicate with another validator node, add an inbound rule to
        allow TCP traffic on port 8800.

      For information on editing the security group rules, see Amazon's
      Security Groups documentation,
      `Adding, Removing, and Updating Rules <http://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/VPC_SecurityGroups.html#AddRemoveRules>`_.

#. Log into this Sawtooth instance. Use the user name ``ubuntu`` when
   connecting.

   For more information, see the Amazon guide
   `Connect to Your Linux Instance <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AccessingInstances.html>`_.

Once launched, the Sawtooth instance continues to run until you stop it.
If you're uncertain about the state or would like to start over, see
:ref:`reset-aws-ubuntu-label`.


.. _confirming-connectivity-aws-label:

Step 2: Check the Status of Sawtooth Components
===============================================

#. You can use ``ps`` to check that each Sawtooth component is running:

   .. code-block:: console

      $ ps aux | grep [s]awtooth
      sawtooth 27556 32.3  2.5 5371560864 407176 ?   Ssl  15:15  15:53 /usr/bin/python3 /usr/bin/sawtooth-validator
      sawtooth 27592  1.1  0.2 305796 38816 ?        Ssl  15:15   0:33 /usr/bin/python3 /usr/bin/sawtooth-rest-api
      sawtooth 27622  0.0  0.2 278176 33708 ?        Ssl  15:15   0:00 /usr/bin/python3 /usr/bin/identity-tp -v -C tcp://localhost:4004
      sawtooth 27712  0.0  0.2 278172 33632 ?        Ssl  15:15   0:00 /usr/bin/python3 /usr/bin/settings-tp -C tcp://localhost:4004

#. Or you can use ``systemctl``:

   .. code-block:: console

      $ systemctl | grep [s]awtooth
      sawtooth-identity-tp.service
           loaded active running   Sawtooth TP Identity
      sawtooth-rest-api.service
           loaded active running   Sawtooth REST API
      sawtooth-settings-tp.service
           loaded active running   Sawtooth TP Settings
      sawtooth-validator.service
           loaded active running   Sawtooth Validator Server

Step 3: Confirm Connectivity to the REST API
============================================

Confirm that you can connect to the REST API from your host system. Enter
the following ``curl`` command from a terminal window:

.. code-block:: console

   $ curl http://localhost:8008/blocks


.. _configure-tf-settings-aws-label:

Step 4: Use Sawtooth Commands as a Client
=========================================

Sawtooth includes commands that act as a client application. This step describes
how to use the ``intkey`` and ``sawtooth`` commands to create and submit
transactions, display blockchain and block data, and examine global state data.

.. note::

   Use the ``--help`` option with any Sawtooth command to display the available
   options and subcommands.

Creating and Submiting Transactions with intkey
-----------------------------------------------

The ``intkey`` command creates sample IntegerKey transactions for testing
purposes.

#. Use ``intkey create_batch`` to prepare batches of transactions that set
   a few keys to random values, then randomly increment and decrement those
   values. These batches are saved locally in the file ``batches.intkey``.

   .. code-block:: console

      $ intkey create_batch --count 10 --key-count 5
      Writing to batches.intkey...

#. Use ``intkey load`` to submit the batches to the validator.

   .. code-block:: console

      $ intkey load
      batches: 11 batch/sec: 141.7800162868952

#. The validator displays many log messages showing that the validator is
   handling the submitted transactions and processing blocks, as in
   this truncated example:

   .. code-block:: console

      ...
      78c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a)^[[0m
      [2018-03-14 16:24:49.621 INFO     chain] Starting block validation of : 60c0c348a00cde622a3664d6d4fb949736b78f8bcb6b77bd0300cdc7675ca9d4116ee23ec18c7cfee5978c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a)
      [2018-03-14 16:24:49.646 INFO     chain] Comparing current chain head 'f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a (block_num:12, state:c30ed78dde19d9ff58587a8bdd4aa435e09212cd1fee3e95d88faafe44f207cc, previous_block_id:dc98ce9029e6e3527bca18060cbb1325b545054b1589f2df7bf200fb0a09d0572491a3837dea1baf2981f5a960bd108f198806c974efcb3b69d2712809cc6065)' against new block '60c0c348a00cde622a3664d6d4fb949736b78f8bcb6b77bd0300cdc7675ca9d4116ee23ec18c7cfee5978c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a)'
      [2018-03-14 16:24:49.647 INFO     chain] Fork comparison at height 13 is between - and 60c0c348
      [2018-03-14 16:24:49.647 INFO     chain] Chain head updated to: 60c0c348a00cde622a3664d6d4fb949736b78f8bcb6b77bd0300cdc7675ca9d4116ee23ec18c7cfee5978c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a)
      [2018-03-14 16:24:49.648 INFO     publisher] Now building on top of block: 60c0c348a00cde622a3664d6d4fb949736b78f8bcb6b77bd0300cdc7675ca9d4116ee23ec18c7cfee5978c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a)
      [2018-03-14 16:24:49.649 DEBUG    chain] Verify descendant blocks: 60c0c348a00cde622a3664d6d4fb949736b78f8bcb6b77bd0300cdc7675ca9d4116ee23ec18c7cfee5978c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a) ([])
      [2018-03-14 16:24:49.651 INFO     chain] Finished block validation of: 60c0c348a00cde622a3664d6d4fb949736b78f8bcb6b77bd0300cdc7675ca9d4116ee23ec18c7cfee5978c295614594319ece3fac71145c05ca36fadc3bd6e65 (block_num:13, state:addbd88bc80ecb05793750b7c80b91588043a1287cd8d4b6e0b1e6a68a0e4017, previous_block_id:f4323dfc238938db834aa5d40b4e6c2825bf7eae5cdaf73a9da28cb308a765707e85ac06e72b01e3d7d529132329b55b18d0cc71ab026506edd63bc6b718e80a)


#. The REST API displays a log message as it communicates with the intkey
   transaction processor.

      .. code-block:: console

         [2018-03-14 16:24:49.587 INFO     helpers] POST /batches HTTP/1.1: 202 status, 1639 size, in 0.030922 s

#. You can also look at the Sawtooth log files to see what happened. Use the
   following command to display the last 10 entries in the intkey log file,
   which show that values have been changed.

      .. code-block:: console

         user@client$ sudo bash -c "tail -10 /var/log/sawtooth/intkey-*-debug.log"
         [2018-03-14 16:24:49.587 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
         [2018-03-14 16:24:49.588 [MainThread] handler DEBUG] incrementing "MvRznE" by 1
         [2018-03-14 16:24:49.624 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
         [2018-03-14 16:24:49.625 [MainThread] handler DEBUG] incrementing "iJWCRq" by 5
         [2018-03-14 16:24:49.629 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
         [2018-03-14 16:24:49.630 [MainThread] handler DEBUG] incrementing "vJJL1N" by 8
         [2018-03-14 16:24:49.634 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
         [2018-03-14 16:24:49.636 [MainThread] handler DEBUG] incrementing "vsTbBo" by 4
         [2018-03-14 16:24:49.639 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
         [2018-03-14 16:24:49.641 [MainThread] handler DEBUG] incrementing "MvRznE" by 1

      .. note::

         The log file names for the transaction processors contain a random
         string that is unique for each instance of the transaction processor.
         For more information, see :ref:`examine-logs-ubuntu-label`.

Submitting Transactions with sawtooth batch submit
--------------------------------------------------

In the example above, the ``intkey create_batch`` command created the file
``batches.intkey``.  Rather than using ``intkey load`` to submit these
transactions, you could use the following command to submit them.

#. As before, create a batch of transactions.

   .. code-block:: console

      $ intkey create_batch --count 10 --key-count 5
      Writing to batches.intkey...

#.  Submit the batch file with the following command:

   .. code-block:: console

     $ sawtooth batch submit -f batches.intkey
     batches: 11,  batch/sec: 216.80369536716367

Viewing Blockchain and Block Data with sawtooth block
-----------------------------------------------------

The ``sawtooth block`` command displays information about the blocks stored on
the blockchain.

#. Use ``sawtooth block list`` to display the list of blocks stored in state.

   .. code-block:: console

      $ sawtooth block list

   The output incudes the block ID, as in this example:

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

#. From the output generated by ``sawtooth block list``, copy the ID of a block
   you want to view, then paste it in place of ``{BLOCK_ID}`` in the following
   command.

   .. code-block:: console

      $ sawtooth block show {BLOCK_ID}

   The output of this command can be quite long, because it includes all data
   stored under that block. This is a truncated example:

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
      ...
      header:
        batch_ids:
        - a93731646a8fd2bce03b3a17bc2cb3192d8597da93ce735950dccbf0e3cf0b005468fadb94732e013be0bc2afb320be159b452cf835b35870db5fa953220fb35
        block_num: 3
        consensus: RGV2bW9kZQ==
        previous_block_id: 042f08e1ff49bbf16914a53dc9056fb6e522ca0e2cff872547eac9555c1de2a6200e67fb9daae6dfb90f02bef6a9088e94e5bdece04f622bce67ccecd678d56e
        signer_public_key: 033fbed13b51eafaca8d1a27abc0d4daf14aab8c0cbc1bb4735c01ff80d6581c52
        state_root_hash: 5d5ea37cbbf8fe793b6ea4c1ba6738f5eee8fc4c73cdca797736f5afeb41fbef
      header_signature: ff4f6705bf57e2a1498dc1b649cc9b6a4da2cc8367f1b70c02bc6e7f648a28b53b5f6ad7c2aa639673d873959f5d3fcc11129858ecfcb4d22c79b6845f96c5e3

Viewing State Data with sawtooth state
--------------------------------------

The ``sawtooth state`` command lets you display state data. Sawtooth stores
state data in a :term:`Merkle-Radix tree`; for more information, see
:doc:`../architecture/global_state`.

#. Use ``sawtooth state list`` to list the nodes (addresses) in state:

   .. code-block:: console

      $ sawtooth state list

   The output will be similar to this truncated example:

   .. code-block:: console

      ADDRESS                                                                                                                                SIZE DATA
      1cf126ddb507c936e4ee2ed07aa253c2f4e7487af3a0425f0dc7321f94be02950a081ab7058bf046c788dbaf0f10a980763e023cde0ee282585b9855e6e5f3715bf1fe 11   b'\xa1fcCTdcH\x...
      1cf1260cd1c2492b6e700d5ef65f136051251502e5d4579827dc303f7ed76ddb7185a19be0c6443503594c3734141d2bdcf5748a2d8c75541a8e568bae063983ea27b9 11   b'\xa1frdLONu\x...
      1cf126ed7d0ac4f755be5dd040e2dfcd71c616e697943f542682a2feb14d5f146538c643b19bcfc8c4554c9012e56209f94efe580b6a94fb326be9bf5bc9e177d6af52 11   b'\xa1fAUZZqk\x...
      1cf126c46ff13fcd55713bcfcf7b66eba515a51965e9afa8b4ff3743dc6713f4c40b4254df1a2265d64d58afa14a0051d3e38999704f6e25c80bed29ef9b80aee15c65 11   b'\xa1fLvUYLk\x...
      1cf126c4b1b09ebf28775b4923e5273c4c01ba89b961e6a9984632612ec9b5af82a0f7c8fc1a44b9ae33bb88f4ed39b590d4774dc43c04c9a9bd89654bbee68c8166f0 13   b'\xa1fXHonWY\x...
      1cf126e924a506fb2c4bb8d167d20f07d653de2447df2754de9eb61826176c7896205a17e363e457c36ccd2b7c124516a9b573d9a6142f031499b18c127df47798131a 13   b'\xa1foWZXEz\x...
      1cf126c295a476acf935cd65909ed5ead2ec0168f3ee761dc6f37ea9558fc4e32b71504bf0ad56342a6671db82cb8682d64689838731da34c157fa045c236c97f1dd80 13   b'\xa1fadKGve\x...

#. Use ``sawtooth state show`` to view state data at a specific address (a node
   in the Merkle-Radix database). Copy the address from the output of
   ``sawtooth state list``, then paste it in place of ``{STATE_ADDRESS}`` in
   the following command:

   .. code-block:: console

      $ sawtooth state show {STATE_ADDRESS}

   The output shows the bytes stored at that address and the block ID of the
   "chain head" that the current state is tied to, as in this example:

   .. code-block:: console

      DATA: "b'\xa1fcCTdcH\x192B'"
      HEAD: "0c4364c6d5181282a1c7653038ec9515cb0530c6bfcb46f16e79b77cb524491676638339e8ff8e3cc57155c6d920e6a4d1f53947a31dc02908bcf68a91315ad5"


.. _examine-logs-aws-label:

Step 5: Examine Sawtooth Logs
=============================

By default, Sawtooth logs are stored in the directory ``/var/log/sawtooth``.
Each component (validator, REST API, and transaction processors) has both a
debug log and an error log. This example shows the log files for this
application development environment:

  .. code-block:: console

     $ ls -1 /var/log/sawtooth
     identity-f5c42a08548c4ffa-debug.log
     identity-f5c42a08548c4ffa-error.log
     intkey-ae98c3726f9743c4-debug.log
     intkey-ae98c3726f9743c4-error.log
     rest_api-debug.log
     rest_api-error.log
     settings-6d591c44915b465c-debug.log
     settings-6d591c44915b465c-error.log
     validator-debug.log
     validator-error.log
     xo-9b8b55265ca0d546-error.log
     xo-9b8b55265ca0d546-debug.log

.. note::

   For the transaction processors, the log file names contain a random string to
   make the names unique. This string changes for each instance of a transaction
   processor. The file names on your system will be different than these
   examples.

For more information on log files, see
:doc:`../sysadmin_guide/log_configuration`.


.. _reset-aws-ubuntu-label:

Step 6: Reset the AWS Environment (Optional)
============================================

When you are done with the AWS environment (or if you want to reset it), you can
use the following commands to restore the Sawtooth instance to its original
state.

.. code-block:: console

  $ sudo rm /var/lib/sawtooth/config-genesis.batch
  $ sudo systemctl restart sawtooth-setup.service

The first command removes the file ``config-genesis.batch``. The second command
restarts the ``sawtooth-setup`` service, which cleans up your validator, creates
a new genesis block, and restarts the ``sawtooth-validator`` service so that
you're ready to build on a new blockchain.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
