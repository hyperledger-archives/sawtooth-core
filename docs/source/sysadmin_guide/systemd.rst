*****************************
Running Sawtooth as a Service
*****************************

.. note::

    These instructions have been tested on Ubuntu 18.04 (Bionic) only.

When you installed Sawtooth with ``apt-get``, ``systemd`` units were added for
the Sawtooth components (validator, REST API, transaction processors, and
consensus engines). This procedure describes how to use the ``systemctl``
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

#. Start the basic Sawtooth components as services: REST API, validator, and
   transaction processors.

   .. code-block:: console

       $ sudo systemctl start sawtooth-rest-api.service
       $ sudo systemctl start sawtooth-validator.service
       $ sudo systemctl start sawtooth-settings-tp.service
       $ sudo systemctl start sawtooth-identity-tp.service
       $ sudo systemctl start sawtooth-intkey-tp-python.service

   The transaction processors ``sawtooth-settings-tp`` (Settings) and
   ``sawtooth-identity-tp`` (Identity) are required.
   ``sawtooth-intkey-tp-python`` (IntegerKey) is used in a later procedure to
   test basic Sawtooth functionality.

#. Start the consensus-related components as services.

   * For PBFT:

     .. code-block:: console

         $ sudo systemctl start sawtooth-pbft-engine.service

   * For PoET:

     .. code-block:: console

         $ sudo systemctl start sawtooth-poet-validator-registry-tp.service
         $ sudo systemctl start sawtooth-poet-engine.service

#. Verify that all the Sawtooth services are running.

   * Check the basic services:

     .. code-block:: console

         $ sudo systemctl status sawtooth-rest-api.service
         $ sudo systemctl status sawtooth-validator.service
         $ sudo systemctl status sawtooth-settings-tp.service
         $ sudo systemctl status sawtooth-identity-tp.service
         $ sudo systemctl status sawtooth-intkey-tp-python.service

   * (PBFT only) Check the PBFT consensus service:

     .. code-block:: console

        $ sudo systemctl status sawtooth-pbft-engine.service

   * (PoET only) Check the PoET consensus services:

     .. code-block:: console

        $ sudo systemctl status sawtooth-poet-validator-registry-tp.service
        $ sudo systemctl status sawtooth-poet-engine.service


View Sawtooth Logs
==================

Use the following command to see the log output that would have been displayed
on the console if you ran the components manually.

* For PBFT:

  .. code-block:: console

      $ sudo journalctl -f \
      -u sawtooth-rest-api \
      -u sawtooth-validator \
      -u sawtooth-settings-tp \
      -u sawtooth-identity-tp \
      -u sawtooth-intkey-tp-python \
      -u sawtooth-pbft-engine

* For PoET:

  .. code-block:: console

      $ sudo journalctl -f \
      -u sawtooth-rest-api \
      -u sawtooth-validator \
      -u sawtooth-settings-tp \
      -u sawtooth-identity-tp \
      -u sawtooth-intkey-tp-python \
      -u sawtooth-poet-validator-registry-tp \
      -u sawtooth-poet-engine

Additional logging output can be found in ``/var/log/sawtooth/``. For more
information, see :doc:`log_configuration`.

.. _stop-restart-sawtooth-services-label:

Stop or Restart the Sawtooth Services
=====================================

If you need to stop or restart the Sawtooth services for any reason, use the
following procedures.

Stop Sawtooth Services
----------------------

  1. Stop the basic services.

     .. code-block:: console

        $ sudo systemctl stop sawtooth-rest-api.service
        $ sudo systemctl stop sawtooth-validator.service
        $ sudo systemctl stop sawtooth-settings-tp.service
        $ sudo systemctl stop sawtooth-identity-tp.service
        $ sudo systemctl stop sawtooth-intkey-tp-python.service

  #. Stop the consensus services.

     * For PBFT:

       .. code-block:: console

          $ sudo systemctl stop sawtooth-pbft-engine.service

     * For PoET:

       .. code-block:: console

          $ sudo systemctl stop sawtooth-poet-validator-registry-tp.service
          $ sudo systemctl stop sawtooth-poet-engine.service

Restart Sawtooth Services
-------------------------

  1. Restart the basic services.

     .. code-block:: console

        $ sudo systemctl restart sawtooth-rest-api.service
        $ sudo systemctl restart sawtooth-validator.service
        $ sudo systemctl restart sawtooth-settings-tp.service
        $ sudo systemctl restart sawtooth-identity-tp.service
        $ sudo systemctl restart sawtooth-intkey-tp-python.service

  #. Restart the consensus services.

     * For PBFT:

       .. code-block:: console

          $ sudo systemctl restart sawtooth-pbft-engine.service

     * For PoET:

       .. code-block:: console

          $ sudo systemctl restart sawtooth-poet-validator-registry-tp.service
          $ sudo systemctl restart sawtooth-poet-engine.service


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
