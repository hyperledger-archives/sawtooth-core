**********************
Log Configuration File
**********************

The validator and the Python SDK make it easy to customize Sawtooth
logging output.  This is done by creating a log config file in
`TOML <https://github.com/toml-lang/toml>`_ or `YAML <http://yaml.org>`_
format and passing it to the built-in Python logging module.

.. Note::

  You must use YAML to configure a remote syslog service. Due to a limitation in
  the TOML spec, you cannot configure a remote syslog service using TOML.

About Sawtooth Log Files
========================

If there is no log configuration file provided, Sawtooth creates an error log
and a debug log by default. These files are stored in the log directory
(``log_dir``), which is ``/var/log/sawtooth`` by default. However, the location
``SAWTOOTH_HOME`` environment variable, if set, can change the default location.
For more information, see :doc:`configuring_sawtooth/path_configuration_file`.

For Sawtooth core components, such as the validator or REST API, the log file
names are ``{component}-debug.log`` and ``{component}-error.log``. For example,
the validator log files are:

- ``validator-debug.log``
- ``validator-error.log``

For Python transaction processors, the author determines the name of the log
file. Because a Sawtooth node can run several instances of the same transaction
processor, it is important to create unique log file names for each running
transaction processor to avoid naming conflicts.

The example transaction processors included in Sawtooth use the following
naming convention:

- ``{TPname}-{zmqID}-debug.log``
- ``{TPname}-{zmqID}-error.log``

For example, an instance of the IntegerKey (``intkey``) transaction processor
could have the following log files:

-  ``intkey-18670799cbbe4367-debug.log``
-  ``intkey-18670799cbbe4367-error.log``

Log Configuration
=================

To change the default logging behavior of a Sawtooth component, such as the
validator or REST API, put a log configuration file in the config directory
(``/var/log/sawtooth`` by default; see
:doc:`configuring_sawtooth/path_configuration_file`).

Sawtooth provides an example log configuration file in
``/etc/sawtooth/log_config.toml.example``. To create a log configuration file,
copy the example file to the config directory and name it ``log_config.toml``.

Each transaction processor can define its own config file. The name of
this file is determined by the author. The transaction processors included in
the Python SDK use the following naming convention:

 - ``{TransactionFamilyName}_log_config.toml``

For example, the IntegerKey (``intkey``) log configuration file is
``intkey_log_config.toml``.

Example: Configure a Specific Logger
====================================
If the default logs give too much information, you can configure a specific
logger that will only report on the area of the code you are interested in.

This example ``log_config.toml`` file creates a handler that only writes
interconnect logs to the directory and file specified.

.. code-block:: none

  version = 1
  disable_existing_loggers = false

  [formatters.simple]
  format = "[%(asctime)s.%(msecs)03d [%(threadName)s] %(module)s %(levelname)s] %(message)s"
  datefmt = "%H:%M:%S"

  [handlers.interconnect]
  level = "DEBUG"
  formatter = "simple"
  class = "logging.FileHandler"
  filename = "path/filename.log"

  [loggers."sawtooth_validator.networking.interconnect"]
  level = "DEBUG"
  propagate = true
  handlers = [ "interconnect"]

The formatter and log level can also be specified to provide the exact
information you want in your logs.

Example: Create a Rotating File Handler
=======================================
This example shows how to set up rotating logs. This is useful when the logs
may grow very large, such as with a long-running network. For example:

.. code-block:: none

  [formatters.simple]
  format = "[%(asctime)s.%(msecs)03d [%(threadName)s] %(module)s %(levelname)s] %(message)s"
  datefmt = "%H:%M:%S"

  [handlers.interconnect]
  level = "DEBUG"
  formatter = "simple"
  class = "logging.handlers.RotatingFileHandler"
  filename = "example-interconnect.log"
  maxBytes = 50000000
  backupCount=20

 [loggers."sawtooth_validator.networking.interconnect"]
  level = "DEBUG"
  propagate = true
  handlers = [ "interconnect"]

If one file exceeds the ``maxBytes`` set in the config file, that file will be
renamed to ``filename.log.1`` and logs will be written to a new
``filename.log``.
This process continues for the number of files plus one (the value set in
``backupCount``). After that point, the file being written to is rotated.
The current log file is always ``filename.log``.

For more Python configuration options, see the Python documentation at
`<https://docs.python.org/3/library/logging.config.html>`_.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
