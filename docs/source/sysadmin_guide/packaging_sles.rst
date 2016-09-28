
**************************
Creating Packages for SLES
**************************

Prerequisites
=============

To create packages for SLES, you need the following:

* SLES 12 64-bit with Internet access
* git Repository: sawtooth-core

The remainder of these instructions assume a vanilla SLES 12 installation
as a starting point.

Install Dependencies
====================

Install the prerequisite packages:

.. code-block:: console

  root@sles # zypper install -y \
      python-setuptools \
      rpmbuild \
      swig \
      gcc-c++ \
      python-devel \
      libjson-c-devel

To get cryptopp, you must add an additional repository:

.. code-block:: console

  root@sles # zypper addrepo \
      http://download.opensuse.org/repositories/devel:libraries:c_c++/SLE_12/devel:libraries:c_c++.repo
  root@sles # zypper refresh

Then, install libcryptopp-devel:

.. code-block:: console

  root@sles # zypper install -y libcryptopp-devel

Create Directory for Resulting Packages
=======================================

Create a directory to hold the packages as we build them.  For this guide, we
will use $HOME/packages.

.. code-block:: console

   root@sles # mkdir $HOME/packages

Create Python Dependency Packages
=================================

cbor
----

Create the python-cbor RPM package:

.. code-block:: console

  root@sles # mkdir -p $HOME/projects
  root@sles # cd $HOME/projects
  root@sles # wget https://pypi.python.org/packages/source/c/cbor/cbor-0.1.24.tar.gz
  root@sles # tar xvfz cbor-0.1.24.tar.gz
  root@sles # cd cbor-0.1.24
  root@sles # python setup.py bdist_rpm
  root@sles # cp dist/cbor-*.x86_64.rpm $HOME/packages/

pybitcointools
--------------

Create the python-pybitcointools RPM package:

.. code-block:: console

  root@sles # mkdir -p $HOME/projects
  root@sles # cd $HOME/projects
  root@sles # wget https://pypi.python.org/packages/source/p/pybitcointools/pybitcointools-1.1.15.tar.gz
  root@sles # tar xvfz pybitcointools-1.1.15.tar.gz
  root@sles # cd pybitcointools-1.1.15
  root@sles # python setup.py bdist_rpm
  root@sles # cp dist/pybitcointools-*.noarch.rpm $HOME/packages/

Create SawtoothLake Python Packages
===================================

Clone Repositories
------------------

Clone or copy the repositories into the SLES environment:

.. code-block:: console

   root@sles # mkdir -p $HOME/projects
   root@sles # cd $HOME/projects
   root@sles # git clone git@github.com:IntelLedger/sawtooth-core.git

.. note::

  You will have to setup your SSH private key to directly clone the repository
  directly into the VM.

At this time, if you are using a branch other than master for any of the
repositories, check out the appropriate branch.

Create Packages
---------------

Create package from sawtooth repository:

.. code-block:: console

  root@sles # cd $HOME/projects/sawtooth-core
  root@sles # python setup.py bdist_rpm
  root@sles # cp dist/sawtooth-core*x86_64.rpm $HOME/packages
  

Create tar File of Packages
===========================

To make it trivial to deliver the SLES RPM files, create a tar file:

.. code-block:: console

  root@sles # cd $HOME
  root@sles # mv packages sawtoothlake-x.y.z-sles-packages
  root@sles # tar cvfj sawtoothlake-x.y.z-sles-packages.tar.bz2 sawtoothlake-x.y.z-sles-packages

.. note::

  The x.y.z in the above tar file name should be replaced with the version of
  the overall sawtoothlake deliverable.

