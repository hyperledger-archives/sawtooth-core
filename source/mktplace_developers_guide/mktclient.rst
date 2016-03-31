
**********************
The Marketplace Client
**********************

Prerequisites
=============

To use the marketplace, you need the following:

* The sawtooth distribution installed on one or more machines, and know the url and port the validators are running on. 

The mktclient
=========================

The mktclient application provides an interactive shell interface that can be used to interact with a Sawtooth validator network. 


Configuring the mktclient
=========================
The market client needs 2 pieces of configuration to connect to a validator network,
#. A valid key - these can be generated with txnkeygen
#. The url of a Sawtooth validator on the network. 

An example command line would be:
./mktclient --keyfile <path to key>/key.wif --url http://localhost:8800

Using the mktclient
=========================

The following steps can be used to start the mktclient, create assets, and exchange them. Details on each of these commands are in the "Sawtooth Lake Distributed Marketplace" document. 

#. Register as a participant on the network

   .. code-block:: none

      participant reg

#. Register an account

   .. code-block:: none

      account reg --name /kellysaccount

#. Register an asset type

   .. code-block:: none

      assettype reg --name /kellysassets

#. Create an asset type

   .. code-block:: none

      asset reg --name /theasset --type /kellysassets

#. Create holdings of an asset 

   .. code-block:: none

      holding reg --asset /theasset --count 5 --name /kellysholdingoftheasset --account /kellysaccount
      holding reg --asset /theasset --count 0  --name /kellysholdingoftheasset2 --account /kellysaccount

#. Exchange/trade asset holdings

   .. code-block:: none

      exchange --src /kellysholdingoftheasset --dst /kellysholdingoftheasset2 --count 3

#. Check the balance of  the holding

   .. code-block:: none

      dump --name /kellysholdingoftheasset
      dump --name /kellysholdingoftheasset2

This will show "/kellysholdingoftheasset" with 2 and "/kellysholdingoftheasset2" with 3.

