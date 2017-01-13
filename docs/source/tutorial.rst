
.. _tutorial:

********
Tutorial
********

Overview
========

This tutorial walks through the process of setting up a virtual development
environment for the Distributed Ledger using Vagrant and VirtualBox. At the
end, you will have a running validator network and a running transaction
processor. You will have submitted transactions to the validator. 

Commands in this tutorial can be run via Terminal.app on MacOS, Git Bash on
Windows, etc.

Prerequisites
=============

The following tools are required:

* `Vagrant <https://www.vagrantup.com/downloads.html>`_ (1.9.0 or later)
* `VirtualBox <https://www.virtualbox.org/wiki/Downloads>`_ (5.0.10 r104061
  or later)

On Windows, you will also need to install:

* `Git for Windows <http://git-scm.com/download/win>`_

Git for Windows will provide not only git to clone the repositories, but also
ssh which is required by Vagrant. During installation, accept all defaults.

.. note:: 

  When checking out Sawtooth Lake on Windows for use with vagrant, you should
  take steps to ensure that Windows-style CRLF line endings are not added to
  the code. The bash scripts used by your vagrant VM will not run correctly 
  with CRLF line endings. Git uses a configuration setting, *core.autocrlf*,
  to control whether or not LF-style line endings are automatically converted
  to CRLF-style line endings. `This setting should be set in such a way that 
  CRLFs are not introduced into your repository 
  <https://git-scm.com/book/en/v2/Customizing-Git-Git-Configuration>`_. 


Clone Repository
================

Open up a terminal and run the following:

.. code-block:: console

   % cd $HOME
   % mkdir project
   % cd project
   % git clone https://github.com/IntelLedger/sawtooth-core.git

Environment Startup
===================

In order to start the vagrant VM, change the current working directory to
sawtooth-core/tools on the host and run:

.. code-block:: console

  % cd sawtooth-core/tools
  % vagrant up

.. note::

   We have encountered an intermittent problem on Windows hosts which
   presents as an 'Operation not permitted' error in the vagrant startup
   output. If you encounter this error, perform a 'vagrant destroy' and
   then run 'vagrant up' again.

Downloading the Vagrant box file, booting the VM, and running through
the bootstrap scripts will take several minutes.

Once the 'vagrant up' command has finished executing, run:

.. code-block:: console

  % vagrant ssh

By default, Vagrant sets up ssh keys so that users can log into the VM
without setting up additional accounts or credentials. The logged in user,
vagrant (uid 1000), also has permissions to execute sudo with no password
required. Any number of `vagrant ssh` sessions can be established from the
host.

Resetting the Environment
=========================

If the VM needs to be reset for any reason, it can be returned to the default
state by running the following commands from the sawtooth-core/tools directory
on the host:

.. code-block:: console

  % vagrant destroy
  % vagrant up

.. caution::

   vagrant destroy will delete all contents within the VM. However,
   /vagrant and /project are shared with the host and will be preserved.

Building sawtooth-core
======================

The vagrant environment is setup in such a way that installation of the
software is not required.  However, the C++/swig code must be built.  To
build, run the following inside vagrant:

.. code-block:: console

  $ /project/sawtooth-core/bin/build_all

Running validator
=================

To start a validator, log in to the development environment with 'vagrant ssh'
and run the following commands:

.. code-block:: console

   $ cd sawtooth-core/
   $ sawtooth cluster start --count 3 -m daemon 

This will start validator and logging output will be printed to the
terminal window. The validator outputs the following to the terminal window:

.. code-block:: console

  database file is /home/ubuntu/merkle.lmdb
  block store file is /home/ubuntu/block.lmdb


Running a transaction processor
===============================

To start a transaction processor, log in to the development environment with 
'vagrant ssh' and run the following commands:

.. code-block:: console

  $ cd sawtooth-core/
  $ tp_intkey_python 127.0.0.1:40000

This will start a transaction processor that includes an **intkey** handler, 
which can understand and process transactions that use the built-in intkey
transaction family. The processor communicates with the validator on 
TCP port 40000. 

The transaction processor produces the following output:

.. code-block:: console

  future result: <bound method Future.result of <sawtooth_sdk.client.future.Future object at 0x7f145f5fc668>>

Multi-language support for transaction processors
-------------------------------------------------

Sawtooth Lake includes additional transaction processors:

* tp_intkey_java

  - An intkey transaction processor written in Java

* tp_intkey_javascript

  - An intkey transaction processor written in JavaScript
  - Requires node.js 

* tp_intkey_jvm_sc

  - An intkey transaction processor implemented as a smart contract.
  - The bytecode to run a transaction is stored in state and the blockchain.
  - Requires Java


Creating and submitting transactions
====================================

Commands to create sample transactions of the intkey transaction type are
included for testing purposes.

The commands in this section guide you through the following tasks:

1. Prepare a batch of intkey transactions that set the keys to random values
   with the 'intkey populate' command.
2. Generate *inc* (increment) and *dec* (decrement) transactions to apply to
   the existing state stored in the blockchain using the 'intkey generate'
   command. 
3. Submit these transactions to the validator using the 'intkey load' command.

Enter the following series of commands after logging in to the development 
environment with 'vagrant ssh':

.. code-block:: console

  $ intkey populate -o initial_state -P 100
  $ intkey generate -o inc_dec_transactions -c 100
  $ intkey load -f initial_state
  $ intkey load -f inc_dec_transactions

You can monitor the activity of the validator as it processes the batches, and
the activity of the transaction processor as it processes the transactions, by
switching to the respective terminal windows. 

To stop the validator, press CTRL-c in the terminal window from which
you ran the validator. The transaction processor can be stopped the same way.


Using sawtooth cluster to start a network
=========================================

The 'sawtooth cluster' command can be used to start a network of validators
and transaction processors. 

The following command will start a network of two validators and two transaction processors:

.. code-block:: console

  $ sawtooth cluster start --count 2 -m subprocess -P tp_intkey_python

You can view the running processes that are part of the network with the
following command:

.. code-block:: console

  $ ps -ef | grep python
  ubuntu   26036 22422 14 22:59 pts/0    00:00:02 python /project/sawtooth-core/bin/sawtooth cluster start --count 2 -m subprocess -P tp_intkey_python
  ubuntu   26039 26036  7 23:00 pts/0    00:00:00 python3 /project/sawtooth-core/bin/validator --component-endpoint 0.0.0.0:40000 --network-endpoint tcp://0.0.0.0:8800
  ubuntu   26040 26036  8 23:00 pts/0    00:00:00 python3 /project/sawtooth-core/bin/tp_intkey_python 0.0.0.0:40000
  ubuntu   26041 26036  7 23:00 pts/0    00:00:00 python3 /project/sawtooth-core/bin/validator --component-endpoint 0.0.0.0:40001 --network-endpoint tcp://0.0.0.0:8801
  ubuntu   26042 26036  7 23:00 pts/0    00:00:00 python3 /project/sawtooth-core/bin/tp_intkey_python 0.0.0.0:40001


To submit sample transactions, follow the steps above under
`Creating and submitting transactions`_.

To stop a running network that was started using the subprocess management
method, simply press CTRL-c.