
*****************
Environment Setup
*****************


Overview
========

This tutorial walks through the process of setting up a virtual environment
useful for core development of the Hyperledger Sawtooth distributed ledger using
Vagrant and VirtualBox. At the end, you will have an environment capable of
running a validator, transaction processor, and other components. You will
have cloned the Sawtooth repository.


Prerequisites
=============

The following tools are required:

* `Vagrant <https://www.vagrantup.com/downloads.html>`_ (1.9.0 or later)
* `VirtualBox <https://www.virtualbox.org/wiki/Downloads>`_ (5.1.16 r113841
  or later)

These tools are available for the following platforms:

* Linux
* Windows
* macOS


Vagrant
-------

Vagrant is a tool which installs and configures virtual development
environments. It allows development teams to easily specify and share
consistent virtual machine configurations.

The dev tools directory (path ''sawtooth-core/tools'') of the sawtooth-core
repository contains a Vagrant configuration which is specifically tailored to
Sawtooth development.  A new developer with installed copies of Vagrant and
VirtualBox can clone the sawtooth-core repository and have a functional VM
which can run validators within a few minutes.

A quick introduction to using dev tools is available as a
quickstart in this Developer's Guide.


Layout of Dev Tools 
===================

The dev tools directory is structured as follows:

.. code-block:: console

 tools/
    bootstrap.d/
    guest-files/
    plugins/
    scripts/
    tests/
    win-bin/
    Vagrantfile


Vagrantfile
  Vagrantfile is the main configuration file for Vagrant.  It is ruby
  code executed by Vagrant and is executed every time a Vagrant command is
  executed.

bootstrap.d
  The bootstrap.d directory contains a set of bash scripts which are
  executed in order during the provisioning step of 'vagrant up'.  These
  scripts are always executed.

guest-files
  The guest-files directory contains configuration files which are used by
  the bootstrap.d scripts.

  There is also a local-env.sh script which contains environment specific
  variables for Sawtooth  development, such as PYTHONPATH.

plugins
  The plugins directory contains bash scripts which can be easily configured
  to execute during the provisioning step of 'vagrant up'.  These scripts
  run after bootstrap.d scripts.

scripts
  This scripts directory contains scripts which are sometimes useful to the
  developer after provisioning has been completed and the developer has a
  shell in the virtual machine.  For example, there are scripts which
  help build Ubuntu packages.

tests
  The tests directory includes tests run within the Vagrant environment. These are
  in addition to the unit and integration tests found in the tests directory of
  sawtooth-core and sawtooth-validator.

win-bin
  The win-bin directory includes scripts for running Sawtooth natively
  under Windows and is not used in the Vagrant environment.


Layout in the Virtual Machine
-----------------------------

A convenient feature of Vagrant is the easy sharing of directories between
the host machine and the guest virtual machine. By default the Vagrant
configuration directory is mounted under /vagrant in the virtual machine.

In the dev tools configuration a /project mount point is also
defined which provides access to the Sawtooth repositories.


Step One: Clone Repository
==========================

You'll need to have git installed in order to clone the Sawtooth source
code repository. You can find up-to-date installation instructions here:

* `Git install instructions <https://git-scm.com/book/en/v2/Getting-Started-Installing-Git>`_

.. note:: 

  When checking out Sawtooth on Windows for use with Vagrant, you should
  take steps to ensure that Windows-style CRLF line endings are not added to
  the code. The bash scripts used by your Vagrant VM will not run correctly
  with CRLF line endings. Git uses a configuration setting, *core.autocrlf*,
  to control whether or not LF-style line endings are automatically converted
  to CRLF-style line endings. `This setting should be set so that 
  CRLFs are not introduced into your repository 
  <https://git-scm.com/book/en/v2/Customizing-Git-Git-Configuration>`_.

Open up a terminal and run the following:

.. code-block:: console

   % cd $HOME
   % mkdir project
   % cd project
   % git clone https://github.com/hyperledger/sawtooth-core.git

.. note::

  On a Windows environment, the suggested version of the last command
  above is:

  .. code-block:: console

      C:\> git clone https://github.com/hyperledger/sawtooth-core.git
      --config core.autocrlf=false


Configure Proxy (Optional)
==========================

If you are behind a network proxy, follow these steps before continuing:

1. Set the following environment variables:

  * http_proxy
  * https_proxy

If you are using the Bash shell, run the following commands:

.. warning::

  The example URLs and port numbers used below are examples only.
  Please substitute the actual URL, with actual port numbers, used
  in your environment. Contact your network administrator for the
  information if necessary.

.. code-block:: console

  % export http_proxy=http://example-proxy-server.com:3128
  % export https_proxy=https://example-proxy-server.com:3129

If you are using Windows, run the following commands:

.. code-block:: console

  % set http_proxy=http://example-proxy-server.com:3128
  % set https_proxy=https://example-proxy-server.com:3129


2. Install the vagrant-proxyconf plugin:

.. code-block:: console

  % cd sawtooth-core/tools
  % vagrant plugin install vagrant-proxyconf


Build and Run Virtual Machine
=============================

In order to start the Vagrant VM, run:

.. code-block:: console

  % cd sawtooth-core/tools
  % vagrant up

.. note::

   We have encountered an intermittent problem on Windows hosts which
   presents as an 'Operation not permitted' error in the Vagrant startup
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

.. note::

   Occasionally, the configuration files used to create the Vagrant
   environment change and this can result in Vagrant asking for a password when
   doing `vagrant up` or `vagrant ssh`. This is usually a sign that your
   environment is out of date. If this happens, please follow the instructions
   below to reset your environment. This is especially common when switching
   between versions of Sawtooth, eg. 0.7 -> 0.8.



Reset The Environment (Optional)
================================

If the VM needs to be reset for any reason, it can be returned to the default
state by running the following commands from the sawtooth-core/tools directory
on the host:

.. code-block:: console

  % vagrant destroy
  % vagrant up

.. warning::

   Vagrant destroy will delete all contents within the VM. However,
   /vagrant and /project are shared with the host and will be preserved.


Build Components
================

Some of the components of Sawtooth depend partially on code that must
first be built. This includes generating protobuf classes
for each language. To build all of the components of Sawtooth within
Vagrant, do:

.. code-block:: console

  $ /project/sawtooth-core/bin/build_all


Building Individual Components
------------------------------

If you need to build a component related to a single language or componenent,
you can save time by running the build command for that component rather than
`build all`. For example, to build only Python components, run:

.. code-block:: console

  $ /project/sawtooth-core/bin/build_python


Running Tests (Optional)
========================

The automated tests for python and all other languages rely on docker to
ensure reproducibility. To run the automated tests for python, first run the
following:

.. code-block:: console

  $ /project/sawtooth-core/bin/build_all -l python

This will create docker images for all the python components and run
`build_python` inside a build container. You can then run the automated tests
for python components, while excluding java and javascript components,
with:

.. code-block:: console

  $ /project/sawtooth-core/bin/run_tests -x java_sdk -x javascript_sdk

.. note::

  The `run_tests` command provides the -x flag to allow you to exclude
  various components from tests. You can also specify which tests to run
  with the -m flag. Run the command `run_tests -h` for help.


If you are not behind a proxy, you can build and test everything Sawtooth
has to offer with:

.. code-block:: console

  $ /project/sawtooth-core/bin/build_all
  $ /project/sawtooth-core/bin/run_tests

