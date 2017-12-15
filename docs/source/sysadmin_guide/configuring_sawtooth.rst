********************
Configuring Sawtooth
********************

Each Sawtooth component, such as the validator or the REST API, has an optional
configuration file that controls the component's behavior. You can also specify
configuration options on the command line when starting the component. For more
information, see :doc:`/cli`.

When a Sawtooth component starts, it looks for a
`TOML <https://github.com/toml-lang/toml>`_ configuration file in the config
directory (``config_dir``). By default, configuration files are stored in
``/etc/sawtooth``; see :doc:`configuring_sawtooth/path_configuration_file` for
more information on the config directory location.

In addition, the Sawtooth log output can be configured with a log config file
in `TOML <https://github.com/toml-lang/toml>`_ or `YAML <http://yaml.org>`_
format. By default, Sawtooth stores error and debug log messages
for each component in the log directory. For more information,
see :doc:`log_configuration`.

The following sections describe each component's configuration file.

.. toctree::
   :maxdepth: 1

   configuring_sawtooth/validator_configuration_file
   configuring_sawtooth/rest_api_configuration_file
   configuring_sawtooth/cli_configuration
   configuring_sawtooth/poet_sgx_enclave_configuration_file
   configuring_sawtooth/path_configuration_file
   configuring_sawtooth/identity_tp_configuration
   configuring_sawtooth/settings_tp_configuration
   configuring_sawtooth/xo_tp_configuration
   log_configuration

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
