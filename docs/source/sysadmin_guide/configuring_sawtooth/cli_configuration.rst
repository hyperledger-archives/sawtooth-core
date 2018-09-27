-------------------------------
Sawtooth CLI Configuration File
-------------------------------

The Sawtooth CLI configuration file specifies arguments to be used by the
``sawtooth`` command and its subcommands. For example, you can use this
file to set the URL of the REST API once, rather than entering the ``--url``
option for each subcommand.

If the config directory contains a file named ``cli.toml``, the
configuration settings are applied when the ``sawtooth`` command is run.
Specifying command-line options will override the settings in the
configuration file.

.. note::

   By default, the config directory is ``/etc/sawtooth/``.
   See :doc:`path_configuration_file` for more information.

An example configuration file is in the ``sawtooth-core`` repository at
``/sawtooth-core/cli/cli.toml.example``. To create a CLI configuration
file, download this example file to the config directory and name it
``cli.toml``.

The example file shows the format of the ``url`` option. To use it,
uncomment the line and replace the default value with the actual
URL for the REST API.

.. code-block:: none

  # The REST API URL
  #   url = "http://localhost:8008"

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
