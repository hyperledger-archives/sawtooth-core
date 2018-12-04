*********************************
Transaction Family Specifications
*********************************

Sawtooth includes several transaction families as examples for developing
your own transaction family.

* The :doc:`/transaction_family_specifications/blockinfo_transaction_family`
  provides a way to store information about a configurable number of historic
  blocks. BlockInfo is written in Python.
  The family name is ``block_info``;
  the associated transaction processor is ``block-info-tp``.

* The :doc:`/transaction_family_specifications/identity_transaction_family`
  is an extensible role- and policy-based system for defining permissions in a
  way that can be used by other Sawtooth components.
  Identity is written in Python.
  The family name is ``sawtooth_identity``;
  the associated transaction processor is ``identity-tp`` (see
  :doc:`/cli/identity-tp`).

* The :doc:`/transaction_family_specifications/integerkey_transaction_family`
  simply sets, increments, and decrements the value of entries stored in a state
  dictionary. IntegerKey is available in Go, Java, and JavaScript (Node.js).
  The family name is ``intkey``;
  the associated transaction processor executables are ``intkey-tp-go``,
  and ``intkey-tp-java``;
  the processor in its own repo is
  `JavaScript <https://github.com/hyperledger/sawtooth-sdk-javascript/blob/master/examples/intkey/>`__.
  The :doc:`intkey command </cli/intkey>` provides an example CLI client.

* The :doc:`/transaction_family_specifications/validator_registry_transaction_family`
  provides a way to add new validators to the network. It is used by the PoET
  consensus algorithm implementation to keep track of other validators.
  The family name is ``sawtooth_validator_registry``.
  The transaction processor is ``poet-validator-registry-tp``.

* The :doc:`/transaction_family_specifications/settings_transaction_family`
  provides a methodology for storing on-chain configuration settings.
  Settings is written in Python.
  The family name is ``sawtooth_settings``;
  the associated transaction processor is ``settings-tp`` (see
  :doc:`/cli/settings-tp`).
  The :doc:`sawset command </cli/sawset>` provides an example CLI client.

  .. note::

    In a production environment, you should always run a transaction processor
    that supports the Settings transaction family.

* The :doc:`/transaction_family_specifications/smallbank_transaction_family`
  provides a cross-platform workload for comparing the performance of
  blockchain systems. Smallbank is written in Go.
  The family name is ``smallbank``;
  the associated transaction processor is ``smallbank-tp``.

* The :doc:`/transaction_family_specifications/xo_transaction_family`
  allows two users to play a simple game of tic-tac-toe (see
  :doc:`/app_developers_guide/intro_xo_transaction_family`).
  XO is written in Go, JavaScript/Node.js, and Python.
  The family name is ``xo``;
  the associated transaction processor executables  are ``xo-tp-go``,
  and ``xo-tp-python``;
  the processor in its own repo is
  `JavaScript <https://github.com/hyperledger/sawtooth-sdk-javascript/blob/master/examples/xo/>`__.
  The :doc:`xo command </cli/xo>` provides an example CLI client.


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
