**************************
Creating the Genesis Block
**************************

.. important::

   Use this procedure **only** for the first validator node on a Sawtooth
   network. Skip this procedure if you are creating a node that will join an
   existing Sawtooth network.

The first node in a new Sawtooth network must create the genesis block to
initialize the Settings transaction processor and specify the consensus
algorithm. The settings in the genesis block enable other nodes to join the
network and use these on-chain settings.

Before you start the first Sawtooth node, use this procedure to create and
submit the genesis block.

.. note::

   This procedure uses the same validator key for all commands that require a
   key. In theory, some of these commands could use a different key, but
   configuring multiple keys is a complicated process. Describing how to use
   multiple keys to create the genesis block is outside the scope of this guide.

1. Ensure that the required user and validator keys exist:

   .. code-block:: console

      $ ls ~/.sawtooth/keys/
      {yourname}.priv    {yourname}.pub

      $ ls /etc/sawtooth/keys/
      validator.priv   validator.pub

   If these key files do not exist, create them as described in
   :doc:`generating_keys`.

#. Become the ``sawtooth`` user. In the following commands, the prompt
   ``[sawtooth@system]`` shows the commands that must be executed as
   ``sawtooth``.

   .. code-block:: console

      $ sudo -u sawtooth -s
      [sawtooth@system]$ cd /tmp

#. Create a batch to initialize the Settings transaction family in the genesis
   block.

   .. code-block:: console

      [sawtooth@system]$ sawset genesis --key /etc/sawtooth/keys/validator.priv -o config-genesis.batch

   This command authorizes this key (the validator key on this node) to change
   Sawtooth settings. You must use the same key for the following commands in
   this procedure. Also, any later commands to change on-chain Sawtooth settings
   must specify this key.

#. Create and submit a proposal to initialize the PoET consensus settings. This
   command sets the consensus algorithm to PoET simulator, and then applies the
   required settings.

   .. code-block:: console

      [sawtooth@system]$ sawset proposal create --key /etc/sawtooth/keys/validator.priv \
      -o config.batch \
      sawtooth.consensus.algorithm.name=PoET \
      sawtooth.consensus.algorithm.version=0.1 \
      sawtooth.poet.report_public_key_pem="$(cat /etc/sawtooth/simulator_rk_pub.pem)" \
      sawtooth.poet.valid_enclave_measurements=$(poet enclave measurement) \
      sawtooth.poet.valid_enclave_basenames=$(poet enclave basename)

   This is a complicated command. Here's an explanation of the options:

   ``--key /etc/sawtooth/keys/validator.priv``
    Signs the proposal with this node's validator key. Only this key can be
    used to change on-chain settings. For more information, see
    :doc:`configuring_permissions`.

   ``-o config.batch``
    Wraps the proposal transaction in a batch named ``config.batch``.

   ``sawtooth.consensus.algorithm.name=PoET``
    Changes the consensus algorithm to PoET.

   ``sawtooth.consensus.algorithm.version=0.1``
    Specifies the version of the consensus algorithm.

   ``sawtooth.poet.report_public_key_pem="$(cat /etc/sawtooth/simulator_rk_pub.pem)"``
    Adds the public key for the PoET Validator Registry transaction
    processor to use for the PoET simulator consensus.

   ``sawtooth.poet.valid_enclave_measurements=$(poet enclave measurement)``
    Adds a simulated enclave measurement to the blockchain. The
    PoET Validator Registry transaction processor uses this value to check
    signup information.

   ``sawtooth.poet.valid_enclave_basenames=$(poet enclave basename)``
    Adds a simulated enclave basename to the blockchain. The PoET
    Validator Registry uses this value to check signup information.

#. Create a batch to register the first Sawtooth node with the PoET Validator
   Registry transaction processor. Without this command, the validator would not
   be able to publish any blocks.

   .. code-block:: console

      [sawtooth@system]$ poet registration create --key /etc/sawtooth/keys/validator.priv -o poet.batch

#. (Optional) Create a batch to configure other PoET settings. This example
   shows the default settings.

   .. code-block:: console

      [sawtooth@system]$ sawset proposal create --key /etc/sawtooth/keys/validator.priv \
      -o poet-settings.batch \
      sawtooth.poet.target_wait_time=5 \
      sawtooth.poet.initial_wait_time=25 \
      sawtooth.publisher.max_batches_per_block=100

#. Combine the previously created batches into a single genesis batch that will
   be committed in the genesis block.

   .. code-block:: console

      [sawtooth@system]$ sawadm genesis config-genesis.batch config.batch poet.batch poet-settings.batch

   You’ll see some output indicating success:

   .. code-block:: console

       Processing config-genesis.batch...
       Processing config.batch...
       Processing poet.batch...
       Processing poet-settings.batch...
       Generating /var/lib/sawtooth/genesis.batch

#. When this command finishes, genesis configuration is complete. Log out of the
   ``sawtooth`` account.

   .. code-block:: console

      [sawtooth@system]$ exit
      $


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
