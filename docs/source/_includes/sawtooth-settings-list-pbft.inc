* (PBFT only) Ensure that the on-chain setting
  ``sawtooth.consensus.pbft.members`` lists the validator public keys of all
  PBFT member nodes on the network.

  a. Connect to the first node (the one that created the genesis
     block).

  #. Display the on-chain settings.

     .. code-block:: console

        $ sawtooth settings list

  #. In the output, look for ``sawtooth.consensus.pbft.members`` and
     verify that it includes the public key for each node.

     .. code-block:: console

        sawtooth.consensus.pbft.members=["03e27504580fa15...


     .. tip::

        You can use the ``sawset proposal create`` command to change this
        setting. For more information, see
        :doc:`/sysadmin_guide/pbft_adding_removing_node`.

