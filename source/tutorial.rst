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

* `Vagrant <https://www.vagrantup.com/downloads.html>`_ (1.7.4 or later)
* `VirtualBox <https://www.virtualbox.org/wiki/Downloads>`_ (5.0.10 r104061
  or later)

On Windows, you will also need to install:

* `Git for Windows <http://git-scm.com/download/win>`_ 

Git for Windows will provide not only git to clone the repositories, but also
ssh which is required by Vagrant. During installation, accept all defaults.

Clone Repositories
==================

All four repositories (sawtooth-vagrant, sawtooth-core, sawtooth-validator, and
sawtooth-mktplace) must be cloned into the same parent directory as follows:

.. code-block:: console

  project/
    sawtooth-core/
    sawtooth-dev-tools/
    sawtooth-mktplace/
    sawtooth-validator/

This can be done by opening up a terminal and running the following:

.. code-block:: console

   % cd $HOME
   % mkdir project
   % cd project
   % git clone https://github.com/IntelLedger/sawtooth-core.git
   % git clone https://github.com/IntelLedger/sawtooth-dev-tools.git
   % git clone https://github.com/IntelLedger/sawtooth-mktplace.git
   % git clone https://github.com/IntelLedger/sawtooth-validator.git

.. note::

   When Vagrant is started (covered in the next section), the configuration
   will check for the presence of these repositories. If any of the
   repositories are missing, Vagrant will print an error to stderr and exit:

   .. code-block:: console

      % vagrant up
      ...
      Repository ../sawtooth-core needs to exist

Environment Startup
===================

In order to start the vagrant VM, change the current working directory to
sawtooth-dev-tools on the host and run:

.. code-block:: console

  % cd sawtooth-dev-tools
  % vagrant up

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
state by running the following commands from the sawtooth-dev-tools directory
on the host:

.. code-block:: console

  % vagrant destroy
  % vagrant up

.. caution::

   vagrant destroy will delete all contents within the VM. However,
   /vagrant and /project are shared with the host and will be preserved.

