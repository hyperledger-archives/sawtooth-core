
****************************
Creating Packages for Ubuntu
****************************

Prerequisites
=============

To create packages for Ubuntu, you need the following:

* Ubuntu 14.04 LTS with Internet access
* git Repositories

  * sawtooth-core
  * sawtooth-validator
  * sawtooth-mktplace

The remainder of these instructions assume a vanilla Ubuntu 14.04 installation
as a starting point.  An easy method to obtain such a machine is by creating
one with vagrant:

.. code-block:: console

  % vagrant init ubuntu/trusty64
  % vagrant up
  % vagrant ssh

Install Dependencies
====================

Apply the latest Ubuntu updates:

.. code-block:: console

  root@ubuntu # apt-get update -y

Install the prerequisite packages:

.. code-block:: console

  root@ubuntu # apt-get install -y -q \
      python-twisted \
      python-twisted-web \
      python-dev \
      python-setuptools \
      g++ \
      swig \
      libjson0 \
      libjson0-dev \
      libcrypto++-dev \
      git \
      python-all-dev \
      python-stdeb

Create Directory for Resulting Packages
=======================================

Create a directory to hold the packages as we build them.  For this guide, we
will use $HOME/packages.

.. code-block:: console

   vagrant@ubuntu $ mkdir $HOME/packages

Create Python Dependency Packages
=================================

cbor
----

Create the python-cbor deb package:

.. code-block:: console

  vagrant@ubuntu $ cd $HOME/projects
  vagrant@ubuntu $ wget https://pypi.python.org/packages/source/c/cbor/cbor-0.1.24.tar.gz
  vagrant@ubuntu $ tar xvfz cbor-0.1.24.tar.gz
  vagrant@ubuntu $ cd cbor-0.1.24
  vagrant@ubuntu $ python setup.py --command-packages=stdeb.command bdist_deb
  vagrant@ubuntu $ cp deb_dist/python-cbor*.deb $HOME/packages/

colorlog
--------

Create the python-colorlog deb package:

.. code-block:: console

  vagrant@ubuntu $ cd $HOME/projects
  vagrant@ubuntu $ wget https://pypi.python.org/packages/source/c/colorlog/colorlog-2.6.0.tar.gz
  vagrant@ubuntu $ tar xvfz colorlog-2.6.0.tar.gz
  vagrant@ubuntu $ cd colorlog-2.6.0
  vagrant@ubuntu $ python setup.py --command-packages=stdeb.command bdist_deb
  vagrant@ubuntu $ cp deb_dist/python-colorlog*.deb $HOME/packages/

pybitcointools
--------------

Create the python-pybitcointools deb package:

.. code-block:: console

  vagrant@ubuntu $ cd $HOME/projects
  vagrant@ubuntu $ wget https://pypi.python.org/packages/source/p/pybitcointools/pybitcointools-1.1.15.tar.gz
  vagrant@ubuntu $ tar xvfz pybitcointools-1.1.15.tar.gz
  vagrant@ubuntu $ cd pybitcointools-1.1.15
  vagrant@ubuntu $ python setup.py --command-packages=stdeb.command bdist_deb
  vagrant@ubuntu $ cp deb_dist/python-pybitcointools*.deb $HOME/packages/

Create SawtoothLake Python Packages
===================================

Clone Repositories
------------------

Clone or copy the repositories into the VM environment:

.. code-block:: console

   vagrant@ubuntu $ mkdir -p $HOME/projects
   vagrant@ubuntu $ cd $HOME/projects
   vagrant@ubuntu $ git clone git@github.com:IntelLedger/sawtooth-validator.git
   vagrant@ubuntu $ git clone git@github.com:IntelLedger/sawtooth-core.git
   vagrant@ubuntu $ git clone git@github.com:IntelLedger/sawtooth-mktplace.git

.. note::

  You will have to setup your SSH private key to directly clone the repository
  directly into the VM.

At this time, if you are using a branch other than master for any of the
repositories, check out the appropriate branch.

Create Packages
---------------

Create package from sawtooth repository:

.. code-block:: console

  vagrant@ubuntu $ cd $HOME/projects/sawtooth-core
  vagrant@ubuntu $ python setup.py --command-packages=stdeb.command bdist_deb
  vagrant@ubuntu $ cp deb_dist/python-sawtooth-core*.deb $HOME/packages/

Create package from mktplace repository:

.. code-block:: console

  vagrant@ubuntu $ cd $HOME/projects/sawtooth-mktplace
  vagrant@ubuntu $ python setup.py --command-packages=stdeb.command bdist_deb
  vagrant@ubuntu $ cp deb_dist/python-sawtooth-mktplace*.deb $HOME/packages/

Create package from sawtooth-validator repository:

.. code-block:: console

  vagrant@ubuntu $ cd $HOME/projects/sawtooth-validator
  vagrant@ubuntu $ python setup.py --command-packages=stdeb.command bdist_deb
  vagrant@ubuntu $ cp deb_dist/python-sawtooth-validator*.deb $HOME/packages/

Create tar File of Packages
===========================

To make it trivial to deliver the Ubuntu deb files, create a tar file:

.. code-block:: console

  vagrant@ubuntu $ cd $HOME
  vagrant@ubuntu $ mv packages sawtoothlake-x.y.z-ubuntu-packages
  vagrant@ubuntu $ tar cvfj sawtoothlake-x.y.z-ubuntu-packages.tar.bz2 sawtoothlake-x.y.z-ubuntu-packages

.. note::

  The x.y.z in the above tar file name should be replaced with the version of
  the overall sawtoothlake deliverable.


