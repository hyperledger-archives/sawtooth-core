*********************************
Transaction Family Specifications
*********************************

Sawtooth includes several transaction families as examples for developing
your own transaction family. These transaction families are available in the
``sawtooth-core`` repository unless noted below.

* The :doc:`/transaction_family_specifications/blockinfo_transaction_family`
  provides a way to store information about a configurable number of historic
  blocks.
  The family name is ``block_info``.
  The transaction processor is ``block-info-tp``.

* The :doc:`/transaction_family_specifications/identity_transaction_family`
  is an extensible role- and policy-based system for defining permissions in a
  way that can be used by other Sawtooth components.
  The family name is ``sawtooth_identity``;
  the associated transaction processor is ``identity-tp`` (see
  :doc:`/cli/identity-tp`).

* The :doc:`/transaction_family_specifications/integerkey_transaction_family`
  (also called "intkey") simply sets, increments, and decrements the value of
  entries stored in a state dictionary.
  The :doc:`intkey command </cli/intkey>` command provides an example CLI client.

  intkey is available in several languages, including Go, Java, and JavaScript
  (Node.js); see the ``sawtooth-sdk-{language}`` repositories under
  ``examples``.

  The family name is ``intkey``.
  The transaction processor is ``intkey-tp-{language}``.

* The :doc:`/transaction_family_specifications/validator_registry_transaction_family`
  provides a way to add new validators to the network. It is used by the PoET
  consensus algorithm implementation to keep track of other validators.

  This transaction family is in the
  `sawtooth-poet <https://github.com/hyperledger/sawtooth-poet>`__ repository.

  The family name is ``sawtooth_validator_registry``.
  The transaction processor is ``poet-validator-registry-tp``.

* The :doc:`/transaction_family_specifications/settings_transaction_family`
  provides a methodology for storing on-chain configuration settings.
  The :doc:`sawset command </cli/sawset>` provides an example CLI client.

  The family name is ``sawtooth_settings``.
  The transaction processor is :doc:`/cli/settings-tp`.

  .. note::

    In a production environment, you should always run a transaction processor
    that supports the Settings transaction family.

* The :doc:`/transaction_family_specifications/smallbank_transaction_family`
  provides a cross-platform workload for comparing the performance of
  blockchain systems.
  The family name is ``smallbank``.
  The transaction processor is ``smallbank-tp``.

* The :doc:`/transaction_family_specifications/xo_transaction_family`
  allows two users to play a simple game of tic-tac-toe (see
  :doc:`/app_developers_guide/intro_xo_transaction_family`).
  The :doc:`xo command </cli/xo>` provides an example CLI client.

  XO is available in several languages. The Rust and Python implementations are
  in `sawtooth-core/sdk/examples
  <https://github.com/hyperledger/sawtooth-core/tree/master/sdk/examples>`__.
  The others are in separate ``sawtooth-sdk-{language}`` repositories under
  ``examples``.

  The family name is ``xo``.
  The transaction processor is ``xo-tp-{language}``.


.. toctree::
   :maxdepth: 3

   transaction_family_specifications/settings_transaction_family.rst
   transaction_family_specifications/identity_transaction_family.rst
   transaction_family_specifications/blockinfo_transaction_family.rst
   transaction_family_specifications/integerkey_transaction_family.rst
   transaction_family_specifications/xo_transaction_family.rst
   transaction_family_specifications/validator_registry_transaction_family.rst
   transaction_family_specifications/smallbank_transaction_family.rst

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
