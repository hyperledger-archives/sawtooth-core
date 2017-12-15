*****************************
Running Sawtooth as a Service
*****************************

When installing Sawtooth using apt-get, *systemd* units are added for the
following components. These can then be started, stopped, and restarted using
the *systemctl* command:

* validator
* transaction processors
* rest_api

To learn more about *systemd* and the *systemctl* command, check out `this
guide`_:

.. _this guide: https://www.digitalocean.com/community/tutorials/how-to-use-systemctl-to-manage-systemd-services-and-units


Viewing Console Output
----------------------

To view the console output that you would see if you ran the components
manually, run the following command:

.. code-block:: console

  $ sudo journalctl -f \
      -u sawtooth-validator \
      -u sawtooth-settings-tp \
      -u sawtooth-poet-validator-registry-tp \
      -u sawtooth-rest-api

Validator Start-up Process
==========================

Create Genesis Block
--------------------

The first validator created in a new network must load a genesis block on
creation to enable other validators to join the network. Prior to starting the
first validator, run the following commands to generate a genesis block that
the first validator can load:

.. code-block:: console

  $ sawtooth keygen --key-dir ~/sawtooth
  $ sawset genesis --key ~/sawtooth.priv
  $ sawadm genesis config-genesis.batch

Running Sawtooth
----------------

.. note::
  Before starting the ``validator`` component you may need to generate
  the validator keypairs using the following command:

  .. code-block:: console

    $ sudo sawadm keygen


To start a component using *systemd*, run the following command where
`COMPONENT` is one of:

  * validator
  * rest-api
  * intkey-tp-python
  * settings-tp
  * xo-tp-python

.. code-block:: console

  $ sudo systemctl start sawtooth-COMPONENT

To see the status of a component run:

.. code-block:: console

  $ sudo systemctl status sawtooth-COMPONENT

Likewise, to stop a component run:

.. code-block:: console

  $ sudo systemctl stop sawtooth-COMPONENT

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
