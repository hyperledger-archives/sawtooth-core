**************************
Creating the Genesis Block
**************************

.. note::

   These instructions have been tested on Ubuntu 16.04 only.

The first node in a new Sawtooth network must create the genesis block to
initialize the Settings transaction processor and specify the consensus
algorithm. When other nodes join the network, they use the on-chain settings in
the genesis block.

Before you start the first Sawtooth node, use this procedure to create and
submit the genesis block.

.. important::

   Use this procedure **only** for the first validator node on a Sawtooth
   network. Skip this procedure if you are creating a node that will join an
   existing Sawtooth network.

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

      [sawtooth@system]$ sawset genesis \
      --key /etc/sawtooth/keys/validator.priv \
      -o config-genesis.batch

   This command authorizes this key (the validator key on this node) to change
   Sawtooth settings. You must use the same key for the following commands in
   this procedure. Also, any later commands to change on-chain Sawtooth settings
   must specify this key.

#. (PBFT only) Find the PBFT version number in the file
   ``sawtooth-pbft/Cargo.toml``. Locate the ``version`` setting in the
   ``[package]`` section, as in this example:

    .. code-block:: none

       [package]
       name = "pbft"
       version = "0.1"
       ...

#. Create batches for the required and optional consensus settings.

   a. Create and submit a proposal to initialize the consensus settings.

      * For PBFT:

        .. code-block:: console

           [sawtooth@system]$ sawset proposal create \
           --key /etc/sawtooth/keys/validator.priv \
           -o config-consensus.batch \
           sawtooth.consensus.algorithm.name=pbft \
           sawtooth.consensus.algorithm.version=VERSION \
           sawtooth.consensus.pbft.peers=[VAL1KEY, VAL2KEY, VAL3KEY]

        Replace ``VERSION`` with the version number from
        ``sawtooth-pbft/Cargo.toml``.

        Replace ``VAL1KEY, VAL2KEY, VAL3KEY`` with the validator public
        keys of the other nodes. This information is in the file
        ``/etc/sawtooth/keys/validator.pub`` on each node.

      * For PoET:

        .. code-block:: console

           [sawtooth@system]$ sawset proposal create \
           --key /etc/sawtooth/keys/validator.priv \
           -o config-consensus.batch \
           sawtooth.consensus.algorithm.name=PoET \
           sawtooth.consensus.algorithm.version=0.1 \
           sawtooth.poet.report_public_key_pem="$(cat /etc/sawtooth/simulator_rk_pub.pem)" \
           sawtooth.poet.valid_enclave_measurements=$(poet enclave measurement) \
           sawtooth.poet.valid_enclave_basenames=$(poet enclave basename)

      .. tip::

         This is a complicated command. Here's an explanation of the options and
         arguments:

         ``--key /etc/sawtooth/keys/validator.priv``
          Signs the proposal with this node's validator key. Only this key can be
          used to change on-chain settings. For more information, see
          :doc:`configuring_permissions`.

         ``-o config-consensus.batch``
          Wraps the consensus proposal transaction in a batch named
          ``config-consensus.batch``.

         ``sawtooth.consensus.algorithm.name``
          Specifies the consensus algorithm for this network.

         ``sawtooth.consensus.algorithm.version``
          Specifies the version of the consensus algorithm.

         (PBFT only) ``sawtooth.consensus.pbft.peers``
          Lists the peer nodes on the initial network as a JSON-formatted string
          of the validators' public keys, using the following format:

          ``[<public-key-1>, <public-key-2>, ..., <public-key-n>]``

         (PoET only) ``sawtooth.poet.report_public_key_pem="$(cat /etc/sawtooth/simulator_rk_pub.pem)"``
          Adds the public key for the PoET Validator Registry transaction
          processor to use for the PoET simulator consensus.

         (PoET only) ``sawtooth.poet.valid_enclave_measurements=$(poet enclave measurement)``
          Adds a simulated enclave measurement to the blockchain. The
          PoET Validator Registry transaction processor uses this value to check
          signup information.

         (PoET only) ``sawtooth.poet.valid_enclave_basenames=$(poet enclave basename)``
          Adds a simulated enclave basename to the blockchain. The PoET
          Validator Registry uses this value to check signup information.

   b. (PoET only) Create a batch to register the first Sawtooth node with the PoET Validator
      Registry transaction processor. Without this command, the validator would not
      be able to publish any blocks.

      .. code-block:: console

         [sawtooth@system]$ poet registration create --key /etc/sawtooth/keys/validator.priv -o poet.batch

   #. (Optional) Create a batch to configure other consensus settings.

      * For PBFT:

        .. code-block:: console

           [sawtooth@system]$ sawset proposal create \
           --key /etc/sawtooth/keys/validator.priv \
           -o pbft-settings.batch \
           SETTING-NAME=VALUE \
           ... \
           SETTING-NAME=VALUE

        For the available settings and their default values, see
        `"On-Chain Settings" in the PBFT documentation
        <https://sawtooth.hyperledger.org/docs/pbft/nightly/master/technical-information.html#on-chain-settings>`__.

      * For PoET:

        .. code-block:: console

           [sawtooth@system]$ sawset proposal create \
           --key /etc/sawtooth/keys/validator.priv \
           -o poet-settings.batch \
           sawtooth.poet.target_wait_time=5 \
           sawtooth.poet.initial_wait_time=25 \
           sawtooth.publisher.max_batches_per_block=100

        .. note::

           This example shows the default PoET settings.

        For more information, see the
        `Hyperledger Sawtooth Settings FAQ <https://sawtooth.hyperledger.org/faq/settings/>`__.

#. Combine all the batches into a single genesis batch that will be committed in
   the genesis block.

   * For PBFT:

     .. code-block:: console

        [sawtooth@system]$ sawadm genesis config-genesis.batch \
        config-consensus.batch pbft-settings.batch


   * For PoET:

     .. code-block:: console

        [sawtooth@system]$ sawadm genesis config-genesis.batch \
        config-consensus.batch poet.batch poet-settings.batch

   You’ll see some output indicating success:

   .. code-block:: console

       Processing config-genesis.batch...
       Processing config-consensus.batch...
       ...
       Generating /var/lib/sawtooth/genesis.batch

#. When this command finishes, genesis configuration is complete. Log out of the
   ``sawtooth`` account.

   .. code-block:: console

      [sawtooth@system]$ exit
      $


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
