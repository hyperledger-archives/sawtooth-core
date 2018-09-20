**********************************
Generating User and Validator Keys
**********************************

1.  Generate your user key for Sawtooth.

    .. code-block:: console

       $ sawtooth keygen

    This command stores user keys in ``$HOME/.sawtooth/keys/{yourname}.priv``
    and ``$HOME/.sawtooth/keys/{yourname}.pub``.

#. Generate the key for the validator, which runs as root.

   .. code-block:: console

       $ sudo sawadm keygen

   By default, this command stores the validator key files in
   ``/etc/sawtooth/keys/validator.priv`` and
   ``/etc/sawtooth/keys/validator.pub``.
   However, settings in the path configuration file could change this location;
   see :doc:`configuring_sawtooth/path_configuration_file`.

Sawtooth also includes a network key pair that is used to encrypt communication
between the validators in a Sawtooth network. The network keys are described in
a later procedure.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/

