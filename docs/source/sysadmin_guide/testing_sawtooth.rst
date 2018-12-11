Testing Sawtooth Functionality
==============================

After :doc:`starting Sawtooth services <systemd>`, you can use this procedure
to test basic Sawtooth functionality.

#. Confirm that the REST API is reachable.

   .. code-block:: console

      $ curl http://localhost:8008/blocks

   .. note::

      The Sawtooth environment described this guide runs a local REST API on
      each validator node. For a node that is not running a local REST API,
      replace ``localhost:8008`` with the externally advertised IP address and
      port.

   You should see a JSON response that is similar to this example:

   .. code-block:: console

      {
        "data": [
          {
            "batches": [
              {
                "header": {
                  "signer_public_key": . . .

   If not, check the status of the REST API service and restart it, if
   necessary; see :doc:`systemd`.

#. If this node has joined an existing network, use the following steps to
   confirm network functionality.

   a. To check whether peering has occurred on the network, submit a peers query
      to the REST API on this node.

      .. code-block:: console

         $ curl http://localhost:8008/peers

      .. note::

         If this node is not running a local REST API, replace
         ``localhost:8008`` with the externally advertised IP address and port
         of the REST API.

      You should see a JSON response that includes the IP address and port for
      the validator and REST API, as in this example:

      .. code-block:: console

         {
             "data": [
             "tcp://validator-1:8800",
           ],
           "link": "http://rest-api:8008/peers"
         }

      If this query returns a 503 error, the node has not yet peered with the
      Sawtooth network. Repeat the query until you see the JSON response.

   #. (Optional) You can run the following Sawtooth commands to show the other
      nodes on the network.

      * Run ``sawtooth peer list`` to show the peers of this node.

      * (Release 1.1 and later) Run ``sawnet peers list`` to display a complete
        graph of peers on the network.

   If there are problems, check the validator and REST API configuration files
   for errors in the IP addresses, ports, or peer settings. For more
   information, see :doc:`configuring_sawtooth`.

#. Check the list of blocks on the blockchain.

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
   initial transactions for on-chain settings, such as setting PoET consensus.

#. Make sure that new blocks of transactions are added to the blockchain.

   #. Use the IntegerKey transaction processor to submit a test transaction.
      The following command uses ``intkey`` (the command-line client for
      IntegerKey) to set a key named ``MyKey`` to the value 999.

      .. code-block:: console

         $ intkey set MyKey 999

   #. Next, check that this transaction appears on the blockchain.

      .. code-block:: console

         $ intkey show MyKey
         MyKey: 999

   #. Repeat the ``block list`` command to verify that there is now one more
      block on the blockchain, as in this example:

      .. code-block:: console

         $ sawtooth block list

         NUM  BLOCK_ID                                                                                                                          BATS  TXNS  SIGNER
         N    1b7f121a82e73ba0e7f73de3e8b46137a2e47b9a2d2e6566275b5ee45e00ee5a06395e11c8aef76ff0230cbac0c0f162bb7be626df38681b5b1064f9c18c76e5  3     3     02d87a...
         .
         .
         .
         2    f40b90d06b4a9074af2ab09e0187223da7466be75ec0f472f2edd5f22960d76e402e6c07c90b7816374891d698310dd25d9b88dce7dbcba8219d9f7c9cae1861  3     3     02e56e...
         1    4d7b3a2e6411e5462d94208a5bb83b6c7652fa6f4c2ada1aa98cabb0be34af9d28cf3da0f8ccf414aac2230179becade7cdabbd0976c4846990f29e1f96000d6  1     1     034aad...
         0    0fb3ebf6fdc5eef8af600eccc8d1aeb3d2488992e17c124b03083f3202e3e6b9182e78fef696f5a368844da2a81845df7c3ba4ad940cee5ca328e38a0f0e7aa0  3     11    034aad...

   If there is a problem, examine the logs for the validator, REST API, and
   transaction processors for possible clues. For more information, see
   :doc:`log_configuration`.

.. tip::

   For help with problems, see the `Hyperledger Sawtooth FAQ
   <https://sawtooth.hyperledger.org/faq/>`__
   or ask a question on the Hyperledger Chat `#sawtooth channel
   <https://chat.hyperledger.org/channel/sawtooth>`__.

After verifying that Sawtooth is running correctly, you can continue with
the optional configuration and customization steps that are described in the
following procedures.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
