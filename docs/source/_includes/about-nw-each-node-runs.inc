Each node in this Sawtooth network runs a validator, a REST API, a consensus
engine, and the following transaction processors:

* :doc:`Settings <../transaction_family_specifications/settings_transaction_family>`
  (``settings-tp``)
* :doc:`Identity <../transaction_family_specifications/identity_transaction_family>`
  (``identity-tp``)
* :doc:`IntegerKey <../transaction_family_specifications/integerkey_transaction_family>`
  (``intkey-tp-python``) -- optional, but used to test basic Sawtooth
  functionality
* (PoET only) :doc:`PoET Validator Registry <../transaction_family_specifications/validator_registry_transaction_family>`
  (``poet-validator-registry-tp``)

.. important::

   Each node in a Sawtooth network must run the same set of transaction
   processors.

