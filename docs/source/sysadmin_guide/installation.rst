*******************
Installing Sawtooth
*******************

The easiest way to install Sawtooth is with apt-get.

.. note::

  These instructions have been tested on Ubuntu 16.04 only.

Add the signing key:

.. code-block:: console

  $ sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 6B58B1AC10FB5F63

Stable Builds:

.. code-block:: console

  $ sudo echo "deb http://repo.sawtooth.me/ubuntu/0.8/stable xenial universe" >> /etc/apt/sources.list

Nightly Builds:

If you'd like the latest and greatest version of Sawtooth, we also
provide a repository of nightly builds. These builds may incorporate
undocumented features and should be used for testing purposes only.

.. code-block:: console

  $ sudo echo "deb http://repo.sawtooth.me/ubuntu/nightly xenial universe" >> /etc/apt/sources.list

Update your package lists and install Sawtooth:

.. code-block:: console

  $ sudo apt-get update
  $ sudo apt-get install -y sawtooth
