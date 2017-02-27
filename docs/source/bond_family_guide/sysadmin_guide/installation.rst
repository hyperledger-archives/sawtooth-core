
************
Installation
************

Overview
========

This article is part of the Sawtooth Lake Bond Family documentation.

Installation
============

The bond transaction family is included with Sawtooth Lake. See the main
Sawtooth Lake :doc:`../../tutorial` for information on installation.


Networking
==========

Networking for your validator node must be set up before your node will be able
to communicate with other nodes in the network:

- Your computer or device must be connected to your LAN/WAN via the integrated 
  network interface.
- The node requires a publicly-addressable IP address or fully-qualified 
  domain name (FQDN).
- The node may be located behind a NAT firewall, may be given a fully exposed 
  public network address, or may be on a DMZ.

The following additional requirements apply:

- An open TCP port on the publicly addressable IP address that maps to the 
  node's configured TCP/http port.
  
  + The default TCP port is 8800, but your configuration may differ. 

- An open UDP port on the publicly addressable IP address that maps to 
  node's configured UDP/gossip layer. 
  
  + The default UDP port is 5500, but your configuration may differ. 

Configuration of the validator node, including networking, is covered in
:doc:`configuration`.




Next Steps
----------
Configuring and starting the validator is covered next, in :doc:`configuration`.



