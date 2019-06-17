**************************
Creating the Genesis Block
**************************

.. note::

   These instructions have been tested on Ubuntu 18.04 (Bionic) only.

**Prerequisites**:

* For PBFT, the genesis block requires the validator keys for at least four
  nodes (or all nodes in the initial network, if known). Before continuing,
  ensure that three (or more) other nodes have installed Sawtooth and generated
  the keys. Gather these keys from ``/etc/sawtooth/keys/validator.pub`` on each
  node.

.. include:: ../_includes/create-genesis-block.inc

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
