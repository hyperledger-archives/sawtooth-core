****************************
System Administrator's Guide
****************************

This guide explains how to install, configure, and run Hyperledger Sawtooth
on a Ubuntu system for proof-of-concept or production use in a Sawtooth network.

* See :doc:`sysadmin_guide/setting_up_sawtooth_network` to configure and run
  a Sawtooth node with either :term:`PBFT <PBFT consensus>` or
  :term:`PoET simulator consensus <PoET consensus>`.

* See :doc:`sysadmin_guide/configure_sgx` to configure and run a Sawtooth node
  with PoET consensus on a system with |Intel (R)| Software Guard Extensions
  (SGX).

This guide also includes optional administration procedures, such as how to
:doc:`restrict transaction types <sysadmin_guide/setting_allowed_txns>`;
:doc:`configure user, client, and validator permissions
<sysadmin_guide/configuring_permissions>`; and
:doc:`display Sawtooth metrics with Grafana <sysadmin_guide/grafana_configuration>`.

Other sections in this guide summarize
:doc:`dynamic consensus settings <sysadmin_guide/about_dynamic_consensus>`
and explain how to
:doc:`use Sawtooth configuration files <sysadmin_guide/configuring_sawtooth>`.

.. toctree::
   :maxdepth: 2

   sysadmin_guide/setting_up_sawtooth_network
   sysadmin_guide/configure_sgx
   sysadmin_guide/setting_allowed_txns
   sysadmin_guide/adding_authorized_users
   sysadmin_guide/rest_auth_proxy
   sysadmin_guide/configuring_permissions
   sysadmin_guide/grafana_configuration
   sysadmin_guide/about_dynamic_consensus
   sysadmin_guide/pbft_adding_removing_node.rst
   sysadmin_guide/configuring_sawtooth


.. |Intel (R)| unicode:: Intel U+00AE .. registered copyright symbol

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
