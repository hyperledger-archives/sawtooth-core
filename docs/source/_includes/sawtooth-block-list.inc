* Check the list of blocks on the blockchain.

  .. code-block:: console

     $ sawtooth block list

  For the first node on a network, this list will contain only a few blocks.
  If this node has joined an existing network, the block list could be quite
  long. In both cases, the list should end with output that resembles this
  example:

  .. code-block:: console

     NUM  BLOCK_ID                                                                                                                          BATS  TXNS  SIGNER
     .
     .
     .
     2    f40b90d06b4a9074af2ab09e0187223da7466be75ec0f472f2edd5f22960d76e402e6c07c90b7816374891d698310dd25d9b88dce7dbcba8219d9f7c9cae1861  3     3     02e56e...
     1    4d7b3a2e6411e5462d94208a5bb83b6c7652fa6f4c2ada1aa98cabb0be34af9d28cf3da0f8ccf414aac2230179becade7cdabbd0976c4846990f29e1f96000d6  1     1     034aad...
     0    0fb3ebf6fdc5eef8af600eccc8d1aeb3d2488992e17c124b03083f3202e3e6b9182e78fef696f5a368844da2a81845df7c3ba4ad940cee5ca328e38a0f0e7aa0  3     11    034aad...

  Block 0 is the :term:`genesis block`. The other two blocks contain the
  initial transactions for on-chain settings, such as setting the consensus
  algorithm.

