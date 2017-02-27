

*************
Configuration
*************

Overview
========

This article guides you through the configuration and startup of the Sawtooth
Lake Bond Family validator service that you installed in :doc:`installation`.


Prerequisites
=============

Networking
----------

1. Your node must be able to communicate with other nodes in the network, as
covered in the networking section of :doc:`installation`.

2. You need the values for your NodeName and LedgerURL entries.


Step 1: Customize the Config File for Your Environment 
======================================================

The configuration file, ``txnvalidator.js``, is located in the folder with the
path ``sawtooth-core/validator/etc/``.  This file has a
number of sections, but you only need to configure the following entries:

1. Listen

  - Required for all configurations
  - Tells the validator which interface and ports to listen on

2. Endpoint

  - Required only for NAT environments
  - Provides the publicly accessible network address and ports 
  - Leave commented out if not needed

3. NodeName: The name of your node on the validator network

4. LedgerURL: The node or nodes with which your node communicates with directly 

To configure your validator node: 


1. Run the following commands to rename the provided example config file and
   open it in a text editor:

  .. code-block:: console

    % cd sawtooth-core/validator/etc/
    % mv txnvalidator.js.example txnvalidator.js
    % vi txnvalidator.js 

2. Modify the **Listen** entry of the configuration file if necessary.

  - The defaults will work for most cases
  - Default entry: 

  .. code-block:: console

   "Listen" : [
          "0.0.0.0:5500/UDP gossip",
          "0.0.0.0:8800/TCP"
      ],

3.  Modify the **Endpoint** entry to reflect your network environment. This
    section must be filled in correctly in order to proceed. This section 
    tells the other nodes in the network how to communicate with you rnode.

    .. note:: Do not proceed without completing this step!

  - **Host**: This is the publicly addressable IP address or FQDN of your 
    validator node. 
  - **Port**: This port must allow UDP traffic to reach the UDP port configured
    in the **Listen** entry of the config file.
  - **HttpPort**: This port must allow TCP traffic to reach the TCP/Http port 
    configured in the **Listen** entry of the config file.

4. **NodeName**: Modify the value of "NodeName" to match the correct value.

5. **LedgerUrl**: This value will be provided to you. Example value:

  - ``"http://192.0.2.1:38804/"``
  - Technical note: this value is an array that can contain multiple IP addresses.

6. (Optional) Modify the https proxy setting:
  
    *If your device requires a proxy to communicate with other nodes, then 
    perform this step:*

    - Modify the value of "HttpsProxy" to the IP address or value supplied by
      your network administrator.

7. Save the config file.
  
.. note:: 
  
  Do not uncomment any lines that make up the internal documentation or 
  explanatory notes within the config file.



