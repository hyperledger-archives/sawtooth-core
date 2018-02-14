******************************************
Using AWS for Your Development Environment
******************************************

This tutorial describes how to set up Hyperledger Sawtooth for application
development using the Amazon Elastic Compute Cloud (Amazon EC2) service.
This step-by-step procedure shows you how to launch an instance of a Sawtooth
validator node from the
`Amazon Web Services (AWS) Marketplace <https://aws.amazon.com/marketplace/pp/B075TKQCC2>`_,
then walks you through the following tasks:

 * Checking the status of Sawtooth components
 * Configuring transaction family settings
 * Submitting transactions to the REST API
 * Viewing blocks and state with Sawtooth commands
 * Examining Sawtooth logs
 * Resetting the AWS Sawtooth instance

.. note::

  This environment requires an AWS account. If you don't have one yet, Amazon
  provides free accounts so you can try the Sawtooth platform. Sign up at
  `aws.amazon.com/free <https://aws.amazon.com/free/>`_.

After completing this tutorial, you will be prepared for the advanced tutorials
on creating a custom transaction family to implement your business logic and
writing a client application that uses the Sawtooth REST API.


About the Demo Sawtooth Environment
===================================

The AWS demo environment is a single validator node that is
running a validator, a REST API, and three transaction processors.

.. figure:: ../images/appdev-environment-one-node-3TPs.*
   :width: 100%
   :align: center
   :alt: Demo Sawtooth environment on AWS

This demo environment introduces basic Sawtooth functionality with the
IntegerKey and Settings transaction processors for the business logic
and the Sawtooth CLI as the client. It also includes the XO transaction
processor, which is used in the advanced tutorials.

The Amazon Machine Image (AMI) for Sawtooth has a ``systemd`` service that
handles environment setup steps such as generating keys and creating a
genesis block. To learn how the typical startup process works, see
:doc:`ubuntu`.


Launching a Sawtooth Instance
=============================

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

      For information on editing the security group rules, see Amazon's
      Security Groups documentation,
      `Adding, Removing, and Updating Rules <http://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/VPC_SecurityGroups.html#AddRemoveRules>`_.

#. Log into this Sawtooth instance. Use the user name ``ubuntu`` when
   connecting.

   For more information, see the Amazon guide
   `Connect to Your Linux Instance <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AccessingInstances.html>`_.

Once launched, the Sawtooth instance continues to run until you stop it.
If you're uncertain about the state or would like to start over, see
`Resetting the Environment`_.


Checking the Status of Sawtooth Components
==========================================

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

#. Confirm that you can connect to the REST API from your host system. Enter
   the following ``curl`` command from a terminal window:

   .. code-block:: console

      $ curl http://localhost:8008/blocks


Configuring Transaction Family Settings
=======================================

By default, Sawtooth allows transactions from any transaction family. In this
step, you will change the configuration settings to allow only IntegerKey and
Settings transactions.

This configuration change is itself a transaction that is submitted in a batch.
Sawtooth configuration settings are stored on the blockchain so that all
validator nodes in a Sawtooth network know the configuration.

 #. The ``sawset proposal`` command creates and submits a batch containing
    the new settings. This batch submits a JSON array that tells the validator
    to accept only transactions of specified transaction type (in this case,
    ``intkey`` and ``sawtooth_settings``).

    Enter the following command:

    .. code-block:: console

       $ sawset proposal create sawtooth.validator.transaction_families='[{"family": "intkey", "version": "1.0"}, {"family":"sawtooth_settings", "version":"1.0"}]'

    A ``TP_PROCESS_REQUEST`` message appears in the logging output of the
    validator, and output similar to the following appears in the
    ``validator-debug.log`` file in ``/var/log/sawtooth``:

    .. code-block:: console

       [21:11:55.356 [Thread-9] tp_state_handlers DEBUG] GET: [('000000a87cb5eafdcca6a8cde0fb0dec1400c5ab274474a6aa82c12840f169a04216b7',b'\nl\n&sawtooth.settings.vote.authorized_keys\x12B03e3ccf73dd618ef1abe18da84d3cf5838a5d292d36ef8857a60b5ad04fd4ab517')]
       [21:11:55.356 [Thread-9] interconnect DEBUG] ServerThread sending TP_STATE_GET_RESPONSE to b'afb61daaa87a4c70'
       [21:11:55.362 [InterconnectThread-1] interconnect DEBUG] ServerThread receiving TP_STATE_GET_REQUEST message: 177 bytes
       [21:11:55.371 [InterconnectThread-1] interconnect DEBUG] message round trip: TP_PROCESS_RESPONSE 0.021718978881835938
       [21:11:55.373 [Thread-23] chain INFO] on_block_validated: 5da8c003(12, S:eb09cdf9, P:dab828cd)
       [21:11:55.374 [Thread-23] chain INFO] Chain head updated to: 5da8c003(12, S:eb09cdf9, P:dab828cd)
       [21:11:55.374 [Thread-23] publisher INFO] Now building on top of block: 5da8c003(12, S:eb09cdf9, P:dab828cd)
       [21:11:55.375 [Thread-23] chain DEBUG] Verify descendant blocks: 5da8c003(12, S:eb09cdf9, P:dab828cd) ([])
       [21:11:55.375 [Thread-23] state_delta_processor DEBUG] Publishing state delta from 5da8c003(12, S:eb09cdf9, P:dab828cd)
       [21:11:55.376 [Thread-23] chain INFO] Finished block validation of: 5da8c003(12, S:eb09cdf9, P:dab828cd)

 #. Use ``sawtooth settings list`` to verify that the change was successfully
    applied.

    .. code-block:: console

       $ sawtooth settings list
       sawtooth.settings.vote.authorized_keys: 03e3ccf73dd618ef1abe18da84d3cf5838a5d292d36ef8857a60b5ad04fd4ab517
       sawtooth.validator.transaction_families: [{"family": "intkey", "version": "1.0"}, {"family":"sawtooth_settings", "version":"1.0"} "...


Creating and Submitting Transactions
====================================

Sawtooth includes commands that act as a client application. This section
describes how to use the ``intkey`` and ``sawtooth batch`` commands to
create and submit transactions.

.. note::

   Use the ``--help`` flag with any Sawtooth command to display the available
   options and subcommands.

Using intkey to Create and Submit Transactions
----------------------------------------------

The ``intkey`` command creates and submits IntegerKey transactions for testing
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

 #. This output doesn't tell us much, so let's look at the Sawtooth logs to see
    what happened. Examine the log files ``validator-*-debug.log`` and
    ``intkey-*-debug.log`` in the directory ``/var/log/sawtooth``.

    .. note::

       Sawtooth log files contain a string to make the file names unique. The
       file names on your system may be different than the examples below.

 #. Display the last 10 entries in the validator log. These entries show that
    state is being updated and that a new block has been published.

    .. code-block:: console

       $ tail -10 /var/log/sawtooth/validator-d1cf3f4ffff81f50-debug.log
       [20:52:07.835 [Thread-8] tp_state_handlers DEBUG] SET: ['1cf1263d536e5febddb1d9804041192faea99c5cd784788a1e3e444d2db93ba60baa08']
       [20:52:07.836 [Thread-8] interconnect DEBUG] ServerThread sending TP_STATE_SET_RESPONSE to b'ae98c3726f9743c4'
       [20:52:07.837 [InterconnectThread-1] interconnect DEBUG] ServerThread receiving TP_PROCESS_RESPONSE message: 69 bytes
       [20:52:07.837 [InterconnectThread-1] interconnect DEBUG] message round trip: TP_PROCESS_RESPONSE 0.006524801254272461
       [20:52:07.843 [Thread-23] chain INFO] on_block_validated: a2ea3764(5, S:8e87d579, P:62f7c965)
       [20:52:07.844 [Thread-23] chain INFO] Chain head updated to: a2ea3764(5, S:8e87d579, P:62f7c965)
       [20:52:07.844 [Thread-23] publisher INFO] Now building on top of block: a2ea3764(5, S:8e87d579, P:62f7c965)
       [20:52:07.845 [Thread-23] chain DEBUG] Verify descendant blocks: a2ea3764(5, S:8e87d579, P:62f7c965) ([])
       [20:52:07.845 [Thread-23] state_delta_processor DEBUG] Publishing state delta from a2ea3764(5, S:8e87d579, P:62f7c965)
       [20:52:07.846 [Thread-23] chain INFO] Finished block validation of: a2ea3764(5, S:8e87d579, P:62f7c965)

 #. Display the last 10 entries in the intkey log. These entries show that
    values are being incremented and decremented.

    .. code-block:: console

       $ tail -10 /var/log/sawtooth/intkey-ae98c3726f9743c4-debug.log
       [20:52:07.803 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
       [20:52:07.805 [MainThread] handler DEBUG] Decrementing "zhUyYM" by 6
       [20:52:07.810 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
       [20:52:07.812 [MainThread] handler DEBUG] Incrementing "ARqIDG" by 8
       [20:52:07.817 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
       [20:52:07.820 [MainThread] handler DEBUG] Decrementing "FxVRRq" by 6
       [20:52:07.824 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
       [20:52:07.827 [MainThread] handler DEBUG] Incrementing "hTnaor" by 9
       [20:52:07.832 [MainThread] core DEBUG] received message of type: TP_PROCESS_REQUEST
       [20:52:07.834 [MainThread] handler DEBUG] Incrementing "ARqIDG" by 6

Using sawtooth batch submit to Submit Transactions
--------------------------------------------------

In the example above, the ``intkey create_batch`` command created the file
``batches.intkey``.  Rather than using ``intkey load`` to submit these
transactions, you could use the following command to submit them:

.. code-block:: console

  $ sawtooth batch submit -f batches.intkey


Viewing Blockchain and Block Data
=================================

The ``sawtooth block`` command displays information about the blocks stored on
the blockchain.

 #. Use ``sawtooth block list`` to display the list of blocks stored in state.

    .. code-block:: console

       $ sawtooth block list

    The output shows the block number and block ID, as in this example:

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

 #. Use ``sawtooth block show`` to view a specific block. Copy the block ID from
    the output of ``sawtooth block list``, then specify this ID in place of
    ``{BLOCK_ID}`` in the following command.

    .. code-block:: console

       $ sawtooth block show {BLOCK_ID}

    The output of this command can be quite long, because it includes all data
    stored under that block. For example:

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


Viewing State Data
==================

The ``sawtooth state`` command lets you display state data. Sawtooth stores state data in a :term:`Merkle-Radix tree`; for more information, see
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


Examining Sawtooth Logs
========================

By default, Sawtooth logs are stored in the directory ``/var/log/sawtooth``.
Each component (validator, REST API, and transaction processors) has both a
debug log and an error log. This example shows the log files for the demo
environment:

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
   The transaction processor log files contain a string to make the file names
   unique. The file names on your system may be different than these examples.

For more information on log files, see
:doc:`../sysadmin_guide/log_configuration`.


Resetting the Environment
=========================

When you are done with the AWS demo environment (or if you want to reset it),
you can use the following commands to restore the Sawtooth instance to its
original state.

.. code-block:: console

  $ sudo rm /var/lib/sawtooth/config-genesis.batch
  $ sudo systemctl restart sawtooth-setup.service

The first command removes the file ``config-genesis.batch``. The second command
restarts the ``sawtooth-setup`` service, which cleans up your validator, creates
a new genesis block, and restarts the ``sawtooth-validator`` service so that
you're ready to build on a new blockchain.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
