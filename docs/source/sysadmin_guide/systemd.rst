*****************************
Running Sawtooth as a Service
*****************************

When you installed Sawtooth with ``apt-get``, ``systemd`` units were added for
the Sawtooth components (validator, REST API, transaction processors, and
consensus engine). This procedure describes how to use the ``systemctl``
command to start, stop, and restart Sawtooth components as ``systemd`` services.

To learn more about ``systemd`` and the ``systemctl`` command, see the `Digital
Ocean systemctl guide`_.

.. _Digital Ocean systemctl guide: https://www.digitalocean.com/community/tutorials/how-to-use-systemctl-to-manage-systemd-services-and-units

.. note::

   Each node in the Sawtooth network must run the same set of transaction
   processors. If this node will join an existing Sawtooth network, make sure
   that you know the full list of required transaction processors, and have
   installed any custom transaction processors.

   If necessary, add the additional transaction processors to all ``systemctl``
   commands in this procedure.


Start the Sawtooth Services
===========================

Use these commands to start each Sawtooth component as a service:

.. code-block:: console

    $ sudo systemctl start sawtooth-rest-api.service
    $ sudo systemctl start sawtooth-poet-validator-registry-tp.service
    $ sudo systemctl start sawtooth-validator.service
    $ sudo systemctl start sawtooth-settings-tp.service
    $ sudo systemctl start sawtooth-intkey-tp-python.service
    $ sudo systemctl start sawtooth-identity-tp.service
    $ sudo systemctl start sawtooth-poet-engine.service

These commands start the required transaction processors:
PoET Validator Registry (``sawtooth-poet-validator-registry-tp``),
Settings (``sawtooth-settings-tp``), and
Identity (``sawtooth-identity-tp``). They also start the IntegerKey
transaction processor (``sawtooth-intkey-tp-python``), which is used in a
later procedure to test basic Sawtooth functionality.
The last command starts the PoET consensus engine (``sawtooth-poet-engine``).


Check Service Status
====================

Run this command to verify that the Sawtooth services are running:

.. code-block:: console

    $ sudo systemctl status sawtooth-rest-api.service
    $ sudo systemctl status sawtooth-poet-validator-registry-tp.service
    $ sudo systemctl status sawtooth-validator.service
    $ sudo systemctl status sawtooth-settings-tp.service
    $ sudo systemctl status sawtooth-intkey-tp-python.service
    $ sudo systemctl status sawtooth-identity-tp.service
    $ sudo systemctl status sawtooth-poet-engine.service


View Sawtooth Logs
==================

Use the following command to view the log output.

.. code-block:: console

    $ sudo journalctl -f \
    -u sawtooth-validator \
    -u sawtooth-settings-tp \
    -u sawtooth-poet-validator-registry-tp \
    -u sawtooth-poet-engine \
    -u sawtooth-rest-api \
    -u sawtooth-intkey-tp-python \
    -u sawtooth-identity-tp

This command shows the output that would have been displayed on the console
if you ran the components manually.

Additional logging output can be found in ``/var/log/sawtooth/``. For more
information, see :doc:`log_configuration`.


Stop or Restart the Sawtooth Services
=====================================

If you need to stop or restart the Sawtooth services for any reason, use the
following commands:

* Stop Sawtooth services:

  .. code-block:: console

     $ sudo systemctl stop sawtooth-rest-api.service
     $ sudo systemctl stop sawtooth-poet-validator-registry-tp.service
     $ sudo systemctl stop sawtooth-validator.service
     $ sudo systemctl stop sawtooth-settings-tp.service
     $ sudo systemctl stop sawtooth-intkey-tp-python.service
     $ sudo systemctl stop sawtooth-identity-tp.service
     $ sudo systemctl stop sawtooth-poet-engine.service

* Restart Sawtooth services:

  .. code-block:: console

     $ sudo systemctl restart sawtooth-rest-api.service
     $ sudo systemctl restart sawtooth-poet-validator-registry-tp.service
     $ sudo systemctl restart sawtooth-validator.service
     $ sudo systemctl restart sawtooth-settings-tp.service
     $ sudo systemctl restart sawtooth-intkey-tp-python.service
     $ sudo systemctl restart sawtooth-identity-tp.service
     $ sudo systemctl restart sawtooth-poet-engine.service


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
