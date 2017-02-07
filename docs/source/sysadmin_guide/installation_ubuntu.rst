
**********************
Installation on Ubuntu
**********************

Prerequisites
=============

To install onto Ubuntu, you need the following:

* Ubuntu 16.04 LTS
* SawtoothLake Distribution (sawtoothlake-x.y.z-ubuntu-packages.tar.gz)

Dependency Installation
=======================

First, you will need to become root for all these commands:

.. code-block:: console

  vagrant@ubuntu $ sudo su

Apply all Ubuntu updates:

.. code-block:: console

  root@ubuntu # apt-get update -y

As root, install the necessary dependecies with apt-get:

.. code-block:: console

  root@ubuntu # apt-get install -y \
        python-twisted \
        python-twisted-web \
        libjson0 \
        libcrypto++ \
        python-yaml \
        python-bs4 \
        python-ipaddr \
        python-numpy \
        python-psutil \
        python-requests \
        python-urllib3

SawtoothLake Installation
=========================

As root, unpack the SawtoothLake Distribution:

.. code-block:: console

  root@ubuntu # tar xvfj sawtoothlake-x.y.z-ubuntu-packages.tar.bz2

Install the SawtoothLake .deb files:

.. code-block:: console

  root@ubuntu # cd sawtoothlake-x.y.z-ubuntu-packages
  root@ubuntu # dpkg -i *.deb

Starting and Stopping the Validator
===================================

The validator is run via Systemd and can be started and stopped with Systemd
commands.

To start the validator:

.. code-block:: console

  root@ubuntu # systemctl start sawtooth-validator

To stop the validator:

.. code-block:: console

  root@ubuntu # systemctl stop sawtooth-validator

You can also view the Systemd status with:

.. code-block:: console

  root@ubuntu # systemctl status sawtooth-validator

The process name will be 'txnvalidator' and you can verify it is running
with ps:

.. code-block:: console

  root@ubuntu # ps -ef | grep txnvalidator

Configuring the Validator
=========================

When run via systemd, the txnvalidator options can be changed in
/etc/defaults/sawtooth-validator with the TXNVALIDATOR_OPTIONS environment
variable.  This includes specifying which configuration file the
txnvalidator should use.


Configuration Files Location 
----------------------------

Configuration files are placed in /etc/sawtooth-validator.


Configuration File Parameters
-----------------------------

By default, the validator will start up as a 'base' validator.
It will not reach out to other validator nodes, and it will initialize
a new set of data files in the data directory, /var/lib/sawtooth-validator
by default.

In order to join the new validator to an existing network of validators,
the "LedgerURL" setting must be changed in the configuration file to
point to a valid URL for an existing http validator in the network.

.. code-block:: none

  {
      "HttpPort" : 0,
      "Host" : "localhost",
      "Port" : 0,
      "NodeName" : "node000",
      "LedgerURL" : "http://base-validator.domain.com:8800/",

It is also important to set the "NodeName" value to a unique value based
on your naming convention. The node's key, which must be generated using
the command *sawtooth keygen*, must be named {node name}.wif and placed 
in the keys directory.

Several other settings are important for correct functionality of the
new validator node. The configuration file must contain the list of
valid transaction families supported by the validator network.

.. code-block:: none

  "TransactionFamilies" : [
      "IntegerKey",
      "MarketPlace"
  ]

Lastly, the "AdministrationNode" setting must contain the address of the
administration node on the validator network. This instructs the validator
to listen for and act on administrative transactions (like shutdown)
received from the administration node. The administration node address
can be found in the keys directory on the adminstration node in a file
called {node name}.addr.

.. code-block:: none

  "AdministrationNode" : "19ns29kWDTX8vNeHNzJbJy6S9HZiqHZyEE"


Security 
--------

You can instruct the validator to check whether or not the validator is being
run under a user with elevated privileges (root in Linux, or administrator in
Windows). If elevated privileges are being used, the validator stops with a
warning.

To run the privilege level check, change the "CheckElevated" setting to "true"
in the configuration file:

.. code-block:: none

  "CheckElevated" : true

This setting applies only to Linux and Windows operating systems.


Log Files
=========

The primary directory for log files is /var/log/sawtooth-validator.  In
addition, Systemd captures stdout and stderr. These can be viewed with:

.. code-block:: none

   vagrant@ubuntu $ sudo journalctl -u sawtooth-validator
