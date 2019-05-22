Each node in this Sawtooth network runs a :term:`validator`, a :term:`REST API`,
a consensus engine, and the following
:term:`transaction processors<transaction processor>`:

* :doc:`Settings <../transaction_family_specifications/settings_transaction_family>`
  (``settings-tp``): Handles Sawtooth's on-chain configuration settings. The
  Settings transaction processor (or an equivalent) is required for all Sawtooth
  networks.

* :doc:`IntegerKey <../transaction_family_specifications/integerkey_transaction_family>`
  (``intkey-tp-python``): Demonstrates basic Sawtooth functionality. The
  associated ``intkey`` client includes shell commands to perform integer-based
  transactions.

* :doc:`XO <../transaction_family_specifications/xo_transaction_family>`
  (``sawtooth-xo-tp-python``: Simple application for playing a game of
  tic-tac-toe on the blockchain. The assocated ``xo`` client provides shell
  commands to define players and play a game. XO is described in a later
  section, :doc:`intro_xo_transaction_family`.

* (PoET only) :doc:`PoET Validator Registry <../transaction_family_specifications/validator_registry_transaction_family>`
  (``poet-validator-registry-tp``): Configures PoET consensus and handles a
  network with multiple nodes.

.. important::

   Each node in a Sawtooth network must run the same set of transaction
   processors.

