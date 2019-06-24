The first node in a new Sawtooth network must create the `genesis block` (the
first block on the distributed ledger). When the other nodes join the network,
they use the on-chain settings that were specified in the genesis block.

The genesis block specifies the consensus algorithm and the keys for nodes (or
users) who are authorized to change configuration settings. For PBFT, the
genesis block also includes the keys for the other nodes in the initial network.

.. important::

   Use this procedure **only** for the first node on a Sawtooth
   network. Skip this procedure for a node that will join an existing network.

1. Ensure that the required user and validator keys exist on this node:

   .. code-block:: console

      $ ls ~/.sawtooth/keys/
      {yourname}.priv    {yourname}.pub

      $ ls /etc/sawtooth/keys/
      validator.priv   validator.pub

   If these key files do not exist, create them as described in the previous
   step.

#. Become the ``sawtooth`` user. Otherwise, you must preface each command with
   ``sudo -u sawtooth``.

   .. code-block:: console

      $ sudo -u sawtooth -s
      [sawtooth@system]$

   In the following commands, the prompt ``[sawtooth@system]`` shows the
   commands that must be executed as the ``sawtooth`` user.

#. Change to a writable directory such as ``/tmp``.

   .. code-block:: console

      [sawtooth@system]$ cd /tmp

#. Create a batch with a settings proposal for the genesis block.

   .. code-block:: console

      [sawtooth@system]$ sawset genesis \
      --key /etc/sawtooth/keys/validator.priv \
      -o config-genesis.batch

   This command authorizes this key (the validator key on this node) to change
   Sawtooth settings. You must use the same key for the following commands in
   this procedure. Also, any later commands to change on-chain Sawtooth settings
   must specify this key.

   .. note::

      This procedure uses the same validator key for all commands that require a
      key. In theory, some of these commands could use a different key, but
      configuring multiple keys is a complicated process. Describing how to use
      multiple keys to create the genesis block is outside the scope of this
      guide.

#. Create a batch to initialize the consensus settings.

   * For PBFT:

     .. code-block:: console

        [sawtooth@system]$ sawset proposal create \
        --key /etc/sawtooth/keys/validator.priv \
        -o config-consensus.batch \
        sawtooth.consensus.algorithm.name=pbft \
        sawtooth.consensus.algorithm.version=1.0 \
        sawtooth.consensus.pbft.members='["VAL1KEY","VAL2KEY",...,"VALnKEY"]'

       .. tip::

          The PBFT version number is in the file ``sawtooth-pbft/Cargo.toml``
          as ``version = "{major}.{minor}.{patch}"``. Use only the first two
          digits (major and minor release numbers); omit the patch number.
          For example, if the version is 1.0.3, use ``1.0`` for this setting.

     Replace ``"VAL1KEY","VAL2KEY","VAL3KEY",...,"VALnKEY"`` with the validator public
     keys of all the nodes (including this node). This information is in the
     file ``/etc/sawtooth/keys/validator.pub`` on each node. Be sure to use
     single quotes and double quotes correctly, as shown in the example.

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

   .. note::

      This is a complicated command. Here's an explanation of the options and
      arguments:

      ``--key /etc/sawtooth/keys/validator.priv``
       Signs the proposal with this node's validator key. Only this key can be
       used to change on-chain settings. For more information, see
       :doc:`../sysadmin_guide/configuring_permissions`.

      ``-o config-consensus.batch``
       Wraps the consensus proposal transaction in a batch named
       ``config-consensus.batch``.

      ``sawtooth.consensus.algorithm.name``
       Specifies the consensus algorithm for this network; this setting is
       required.

      ``sawtooth.consensus.algorithm.version``
       Specifies the version of the consensus algorithm; this setting is
       required.

      (PBFT only) ``sawtooth.consensus.pbft.members``
       Lists the member nodes on the initial network as a JSON-formatted
       string of the validators' public keys, using the following format:

       ``'["<public-key-1>","<public-key-2>",...,"<public-key-n>"]'``

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

#. (PoET only) Create a batch to register the first Sawtooth node with the PoET
   Validator Registry transaction processor. Without this command, the validator
   would not be able to publish any blocks.

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
     "On-Chain Settings" in the `Sawtooth PBFT documentation
     <https://sawtooth.hyperledger.org/docs/#sawtooth-pbft>`__.

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

     For more information, see the `Hyperledger Sawtooth Settings
     FAQ <https://sawtooth.hyperledger.org/faq/settings/>`__.

#. Combine the separate batches into a single genesis batch that will be
   committed in the genesis block.

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

   .. note::

      The ``sawtooth.consensus.algorithm.name`` and
      ``sawtooth.consensus.algorithm.version`` settings are required; ``sawadm
      genesis`` will fail if they are not present in one of the batches unless
      the ``--ignore-required-settings`` flag is used.

#. When this command finishes, the genesis block is complete. Log out of the
   ``sawtooth`` account.

   .. code-block:: console

      [sawtooth@system]$ exit
      $

The settings in the genesis block will be available after the first node has
started and the genesis block has been committed.
