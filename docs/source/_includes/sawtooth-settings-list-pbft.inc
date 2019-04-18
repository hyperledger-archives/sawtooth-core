* (PBFT only) Ensure that the on-chain setting
  ``sawtooth.consensus.pbft.members`` lists the validator public keys of all
  PBFT member nodes on the network.

  a. Connect to the first validator node (the one that created the genesis
     block).

  #. Display the on-chain settings.

     .. code-block:: console

        $ sawtooth settings list

  #. In the output, look for ``sawtooth.consensus.pbft.members`` and
     verify that it includes the public key for each node.

     .. code-block:: console

        sawtooth.consensus.pbft.members=[03e27504580fa15...

