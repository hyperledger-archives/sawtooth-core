**************************
Creating the Genesis Block
**************************

The first node in a new Sawtooth network must create the genesis block to
initialize the Settings transaction processor and specify the consensus
mechanism. The settings in the genesis block enable other nodes to join the
network and use these on-chain settings.

Before you start the first Sawtooth node, use this procedure to create and
submit the genesis block.

.. important::

   Use this procedure **only** for the first validator node on a Sawtooth
   network. Skip this procedure if you are creating a node that will join an
   existing Sawtooth network.

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

#. Create and submit a proposal to initialize the PoET consensus settings. This
   command sets the consensus algorithm to PoET simulator, and then applies the
   required settings.

   .. code-block:: console

      [sawtooth@system]$ sawset proposal create --key /etc/sawtooth/keys/validator.priv \
      -o config.batch \
      sawtooth.consensus.algorithm=poet \
      sawtooth.poet.report_public_key_pem="$(cat /etc/sawtooth/simulator_rk_pub.pem)" \
      sawtooth.poet.valid_enclave_measurements=$(poet enclave measurement) \
      sawtooth.poet.valid_enclave_basenames=$(poet enclave basename)

   This is a complicated command. Here's an explanation of the options:

   ``--key /etc/sawtooth/keys/validator.priv``
         Signs the proposal with this node's validator key. By default, only the
         ``sawtooth`` user on this node can change on-chain settings. A later
         step shows how you can submit a proposal that allows other users to
         change on-chain settings.

   ``sawtooth.consensus.algorithm=poet``
         Changes the consensus algorithm to PoET.

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
