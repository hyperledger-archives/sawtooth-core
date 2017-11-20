-------------------------------
Sawtooth CLI Configuration File
-------------------------------

The CLI configuration file specifies arguments to be used by the
``sawtooth`` command.

If the config directory contains a file named ``cli.toml``, the
configuration settings are applied when the ``sawtooth`` command is
run. Specifying command-line options will override the settings in the
configuration file.

Note: By default, the config directory is /etc/sawtooth/. See
:doc:`path_configuration_file` for more information.

An example configuration file is in
``/sawtooth-core/cli/cli.toml.example``. To create a CLI configuration
file, copy the example file to the config directory and name it
``cli.toml``. Then edit the file to change the example configuration
options as necessary for your system.
