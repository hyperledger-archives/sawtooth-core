*****************
Log Configuration
*****************

Overview
========
The validator and the Python SDK make it easy to customize the logging output.
This is done by creating a TOML (`<https://github.com/toml-lang/toml>`_)
formatted log config file and passing it to the built-in Python logging module.

Default
=======

If there is no log configuration file provided, the default is to create an
error log and a debug log. Theses files will be stored in the log directory that
is configured by the SAWTOOTH_HOME environment variable. For example, if
`SAWTOOTH_HOME="/home/ubuntu/sawtooth"`, the logs will be written
to `/home/ubuntu/sawtooth/logs`.

If SAWTOOTH_HOME is not set, the default location is OS-specific. On Linux,
it's `/var/log/sawtooth`. On Windows, it is one level up from the where the
command is installed. For example, if `C:\\sawtooth\\bin\\validator.exe`
starts the validator, the log directory is `C:\\sawtooth\\logs\\`. The log
directory can also be set in the path.toml file, however, this file should
rarely be used.

The name of the validator logs will look like the following:

- validator-{first 8 characters of the validator's pubkey}-debug.log
- validator-{first 8 characters of the validator's pubkey}-error.log

Examples:

- *validator-03aa0272-debug.log*
- *validator-03aa0272-error.log*

For Python transaction processors, the author determines the name of the log
file. It is highly encouraged that the file names are unique for each running
processor to avoid naming conflicts.  The example transaction processors
provided with the SDK uses the following:

- {tp_name}-{zmq_identity}-debug.log
- {tp_name}-{zmq_identity}-error.log

Examples:

-  *intkey-18670799cbbe4367-debug.log*
-  *intkey-18670799cbbe4367-error.log*

Configuration
=============

To change the default behavior, a log configuration file can be placed in the
config directory (see below).

The validator log config file should be named `log_config.toml`.

Each transaction processor may also define its own config file. The name of
this file is determined by the author. The transaction processors included in
the Python SDK follow the convention `{Transaction_Family_Name}_log_config.toml`.
For example, intkey's log config file is named `intkey_log_config.toml`.

Config Directory
----------------

If `$SAWTOOTH_HOME` is set the config directory is found at
`$SAWTOOTH_HOME/etc/` . Otherwise it is defined by the OS being used. On Linux the
config directory is located at `/etc/sawtooth`. On Windows, the config
directory is located one directory up from where the command is installed.
For example, if `C:\\sawtooth\\bin\\validator.exe` starts the validator, the config
directory is `C:\\sawtooth\\conf\\`. As long as the log configuration file is
present, the validator and transaction processors will automatically find it
and load the configuration.

Examples
========

Configure Specific Logger
-------------------------
If the default logs give too much information, you can configure a specific
logger that will only report on the area of the code you are interested in.

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

The above log_config.toml file creates a handler that only writes
interconnect logs to the directory and file specified. The formatter and log level
can also be specified to provide the exact information you want in your logs.


Rotating File Handler
---------------------
Below is an example of how to setup rotating logs. This is useful when the logs
may grow very large, such as with a long running network.

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

If one file exceeds the maxBytes set in the config file, that file will be
renamed to filename.log.1 and a new filename.log will be written to. This
process continues for the number of files plus one set in the backupCount.
After that point, the file that is being written to is rotated. The current
file being written to is always filename.log.

For further configuration options see the Python docs:
`<https://docs.python.org/3/library/logging.config.html>`_
