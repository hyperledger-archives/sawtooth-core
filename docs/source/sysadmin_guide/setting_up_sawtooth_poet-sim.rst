**************************
Setting Up a Sawtooth Node
**************************

This section describes how to install, configure, and run Hyperledger Sawtooth
on a Ubuntu system for proof-of-concept or production use in a Sawtooth network.

Use this set of procedures to create the first Sawtooth node in a network or to
add a node to an existing network.  Note that certain steps are performed only
on the first node.

.. important::

   These procedures use PoET simulator consensus, which is recommended for a
   system without a Trusted Execution Environment (TEE). To configure Sawtooth
   with PoET SGX consensus on a system with |Intel (R)| Software Guard
   Extensions (SGX), see :doc:`configure_sgx`.

.. |Intel (R)| unicode:: Intel U+00AE .. registered copyright symbol

Each node in this Sawtooth network runs a validator, a REST API, the PoET
consensus engine, and the following transaction processors:

* :doc:`Settings <../transaction_family_specifications/settings_transaction_family>`
  (``settings-tp``)
* :doc:`Identity <../transaction_family_specifications/identity_transaction_family>`
  (``identity-tp``)
* :doc:`PoET Validator Registry <../transaction_family_specifications/validator_registry_transaction_family>`
  (``poet-validator-registry-tp``)
* :doc:`IntegerKey <../transaction_family_specifications/integerkey_transaction_family>`
  (``intkey-tp-python``) -- optional, but used to test basic Sawtooth
  functionality

Each node in a Sawtooth network must run the same set of transaction
processors. If this node will join an existing Sawtooth network, make sure
that you know the full list of required transaction processors, and that you
install any custom transaction processors.

.. note::

    These instructions have been tested on Ubuntu 16.04 only.


.. toctree::
   :maxdepth: 1

   installation.rst
   generating_keys.rst
   creating_genesis_block.rst
   off_chain_settings.rst
   systemd.rst
   testing_sawtooth.rst


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
