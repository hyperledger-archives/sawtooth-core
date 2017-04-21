*********************
Installation with APT
*********************

.. note::

  These instructions have been tested on Ubuntu 16.04 only.

Add the Sawtooth Lake signing key:

.. code-block:: console

  $ sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 6B58B1AC10FB5F63

Stable Builds
-------------

Add the Sawtooth Lake repository to your ``/etc/apt/sources.list``:

.. code-block:: console

  $ sudo echo "deb http://repo.sawtooth.me/ubuntu/0.8/stable xenial universe" >> /etc/apt/sources.list

Update your repositories and install Sawtooth Lake:

.. code-block:: console

  $ sudo apt-get update
  $ sudo apt-get install -y -q \
    python3-sawtooth-cli \
    python3-sawtooth-config \
    python3-sawtooth-intkey \
    python3-sawtooth-manage \
    python3-sawtooth-poet-cli \
    python3-sawtooth-poet-common \
    python3-sawtooth-poet-core \
    python3-sawtooth-poet-families \
    python3-sawtooth-poet-simulator \
    python3-sawtooth-rest-api \
    python3-sawtooth-sdk \
    python3-sawtooth-signing \
    python3-sawtooth-validator \
    python3-sawtooth-xo


Nightly Builds
--------------

If you'd like the latest and greatest version of Sawtooth Lake, we also
provide a repository of nightly builds. These builds may incorporate
undocumented features and should be used for testing purposes only.

Add the Sawtooth Lake nightly repository to your ``/etc/apt/sources.list``:

.. code-block:: console

  $ sudo echo "deb http://repo.sawtooth.me/ubuntu/nightly xenial universe" >> /etc/apt/sources.list

Update your repositories and install Sawtooth Lake:

.. code-block:: console

  $ sudo apt-get update
  $ sudo apt-get install -y -q \
    python3-sawtooth-cli \
    python3-sawtooth-config \
    python3-sawtooth-intkey \
    python3-sawtooth-manage \
    python3-sawtooth-poet-cli \
    python3-sawtooth-poet-common \
    python3-sawtooth-poet-core \
    python3-sawtooth-poet-families \
    python3-sawtooth-poet-simulator \
    python3-sawtooth-rest-api \
    python3-sawtooth-sdk \
    python3-sawtooth-signing \
    python3-sawtooth-validator \
    python3-sawtooth-xo
