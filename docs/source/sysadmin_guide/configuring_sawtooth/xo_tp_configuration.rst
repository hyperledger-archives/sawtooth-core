-------------------------------------------------
XO Transaction Processor Configuration File
-------------------------------------------------

The XO transaction processor configuration file specifies the validator
endpoint connection to use.

If the config directory contains a file named ``xo.toml``, the
configuration settings are applied when the transaction processor starts.
Specifying a command-line option will override the setting in the configuration
file.

.. note::

   By default, the config directory is ``/etc/sawtooth/``.
   See :doc:`path_configuration_file` for more information.

An example configuration file is in the ``sawtooth-core`` repository at
``/sawtooth-core/sdk/examples/xo_python/packaging/xo.toml.example``.
To create a XO transaction processor configuration file, download this example
file to the config directory and name it ``xo.toml``. Then edit the file
to change the example configuration options as necessary for your system.

The ``xo.toml`` configuration file has the following option:

- ``connect`` = "`URL`"

  Identifies the URL of a running validator. Default: ``tcp://localhost:4004``.
  For example:

  .. code-block:: none

    connect = "tcp://localhost:4004"

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
