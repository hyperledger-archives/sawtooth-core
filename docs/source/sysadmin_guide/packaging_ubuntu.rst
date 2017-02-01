
****************************
Creating Packages for Ubuntu
****************************

Prerequisites
=============

To create packages for Ubuntu, you need the following:

* Ubuntu 16.04 LTS with Internet access
* git Repository: sawtooth-core

The remainder of these instructions assume a vanilla Ubuntu 14.04 installation
as a starting point.  An easy method to obtain such a machine is by creating
one with vagrant:

.. code-block:: console

  % vagrant init ubuntu/xenial64
  % vagrant up
  % vagrant ssh

Install Dependencies
====================

Apply the latest Ubuntu updates:

.. code-block:: console

  vagrant@ubuntu $ sudo apt-get update -y

Install the prerequisite packages:

.. code-block:: console

  vagrant@ubuntu $ sudo apt-get install -y -q \
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

  vagrant@ubuntu $ mkdir $HOME/projects
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

Clone Repository
----------------

Clone or copy the repository into the VM environment:

.. code-block:: console

   vagrant@ubuntu $ mkdir -p $HOME/projects
   vagrant@ubuntu $ cd $HOME/projects
   vagrant@ubuntu $ git clone https://github.com/IntelLedger/sawtooth-core.git
   vagrant@ubuntu $ cd sawtooth-core
   vagrant@ubuntu $ git checkout 0-7
   vagrant@ubuntu $ cd $HOME

Create Packages
---------------

Create packages from sawtooth repository:

.. code-block:: console

    vagrant@ubuntu $ for pkg in signing core extensions/mktplace extensions/arcade extensions/bond
    > do
    >     dir=$HOME/projects/sawtooth-core/$pkg
    >     if [ -d $dir ]; then
    >         cd $dir
    >         python setup.py --command-packages=stdeb.command bdist_deb
    >         cp deb_dist/*.deb $HOME/packages/
    >     fi
    > done

    vagrant@ubuntu $ cd $HOME/projects/sawtooth-core
    vagrant@ubuntu $ ./bin/package_validator
    vagrant@ubuntu $ cp python-sawtooth-validator*.deb $HOME/packages/


Create tar File of Packages
===========================

To make it easy to deliver the Ubuntu deb files, create a tar file:

.. code-block:: console

  vagrant@ubuntu $ cd $HOME
  vagrant@ubuntu $ mv packages sawtoothlake-x.y.z-ubuntu-packages
  vagrant@ubuntu $ tar cvfj sawtoothlake-x.y.z-ubuntu-packages.tar.bz2 sawtoothlake-x.y.z-ubuntu-packages

.. note::

  The x.y.z in the above tar file name should be replaced with the version of
  the overall sawtoothlake deliverable.


