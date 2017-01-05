
.. _tutorial:

********
Tutorial
********

Overview
========

This tutorial walks through the process of setting up a virtual development
environment for the Distributed Ledger using Vagrant and VirtualBox. At the
end, you will have a running validator network and be able to use client
commands to interact with it.

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

Running txnvalidator
====================

To start txnvalidator, log in to the development environment with 'vagrant ssh'
and run the following commands:

.. code-block:: console

   $ /project/sawtooth-core/docs/source/tutorial/genesis.sh
   $ cd /project/sawtooth-core
   $ ./bin/txnvalidator -v -F ledger.transaction.integer_key --config /home/ubuntu/sawtooth/v0.json

This will start txnvalidator and logging output will be printed to the
terminal window.

.. note::
  **Note on genesis block creation and clearing validator state**

    The script *genesis.sh* should be run whenever you want to start a
    validator as part of the tutorial. The script clears existing data
    files and keys, which would otherwise be loaded when starting the
    validator. The script also runs a utility that creates a genesis
    block, and creates a special configuration file needed by an initial
    node serving a genesis block (see note below for details). This
    utility is part of the sawtooth CLI. To view the available
    subcommands, run the command **sawtooth -h**. The genesis creation
    utility used in this tutorial is: **sawtooth admin poet1-genesis**
    (see script *genesis.sh* for the command line options used in the
    tutorial).


.. note::
  **Note on configuration needed for initial node serving genesis block**

    The special configuration file created using the utility *genesis.sh*
    described in the note above contains the following setting, which is
    required for the intitial node that serves the genesis block:

    **{"InitialConnectivity": 0}**

    The initial node that serves the genesis block must refrain from
    establishing initial connectivity until it assumes the role of a
    validator that can provide ledger transfers to other nodes. The
    initial validator already has the ledger, including the prefabricated
    genesis block. However, if the initial connectivity is not set to
    zero, it might attempt to  obtain the ledger from other nodes, rather
    than providing the critical genesis block to the rest of the network.




To stop the validator, press CTRL-c.
