
Vagrant
=======

Overview
--------

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

Layout of the sawtooth-dev-tools git Repository
------------------------------------------------

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
  code executed by Vagrant and is executed every ime a vagrant command is
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
  sawtooth-core, sawtooth-validator and sawtooth-mktplace.

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

Configuration Options
---------------------

There is a rudimentary configuration system in place which can impact
how the Vagrant environment is provisioned.

The files involved are:

.. code-block:: console

  conf-defaults.sh
  conf-local.sh
  conf-local.sh.example

The conf-local.sh file, which is not checked into the git repository,
is the one that should be modified locally.  This file can be
initialized by copying conf-local.sh.example to conf-local.sh.

The conf-default.sh file defines the defaults for configuration
values which are not set.

The valid config values are:

INSTALL_TYPE
  By default, this is set to 'none'.  It can be set to one of:

    * none - do not install anything by default
    * setup.py - build and install sawtooth-core, sawtooth-validator,
      sawtooth-mktplace from the git repositories using 'python setup.py install'
    * deb - build and install sawtooth-core, sawtooth-validator, sawtooth-mktplace from
      the git repositories by first creating deb packages and then installing
      those deb packages.

START_TXNVALIDATOR
  By default, this is set to 'no'.  If set to 'yes', then txnvalidator
  will be started with upstart or systemd.  For this option to work,
  INSTALL_TYPE must be set to 'deb'.

PLUGINS
  By default, set to "build_ubuntu_deps install_ubuntu_deps install_sphinx".
  Specify a space-separated list of plugins to run.  The plugins are contained
  in the plugins directory.

The following plugins are available:

build_ubuntu_deps
  This plugin builds the debian packages for cbor, colorlog, and
  pybitcointools.  They are placed in /project/build/packages/.

install_latex
  This plugin installs Latex, which is required for building a PDF of the
  documentation.  This is disabled by default because it takes a fairly
  long time to download.

install_ubuntu_deps
  This plugin installs the debian packages built by build_ubuntu_deps.

install_sphinx
  This plugin installs sphinx, which is required for building the sawtooth
  documentation.

