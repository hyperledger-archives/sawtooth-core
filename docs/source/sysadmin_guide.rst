****************************
System Administrator's Guide
****************************

This guide explains how to install, configure, and run Hyperledger Sawtooth
on a Ubuntu system for proof-of-concept or production use in a Sawtooth network.

It includes steps to configure a consensus algorithm, using PoET simulator
consensus as an example, and to start the Sawtooth components as services.

It also includes optional procedures to change the user, client, and validator
permissions; set up a proxy for the REST API; and configure Grafana to display
Sawtooth metrics.

.. note::

   The instructions in this guide have been tested on Ubuntu 16.04 only.


.. toctree::
   :maxdepth: 2

   sysadmin_guide/setting_up_sawtooth_poet-sim
   sysadmin_guide/setting_allowed_txns
   sysadmin_guide/rest_auth_proxy
   sysadmin_guide/configuring_permissions
   sysadmin_guide/grafana_configuration
   sysadmin_guide/configure_sgx
   sysadmin_guide/configuring_sawtooth


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
