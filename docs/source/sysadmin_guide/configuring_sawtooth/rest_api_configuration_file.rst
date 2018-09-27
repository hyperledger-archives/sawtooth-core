---------------------------
REST API Configuration File
---------------------------

The REST API configuration file specifies network connection settings and an
optional timeout value.

If the config directory contains a file named ``rest_api.toml``, the
configuration settings are applied when the REST API starts.
Specifying a command-line option will override the setting
in the configuration file.

.. note::

   By default, the config directory is ``/etc/sawtooth/``.
   See :doc:`path_configuration_file` for more information.

An example configuration file is in the ``sawtooth-core`` repository at
``/sawtooth-core/rest_api/packaging/rest_api.toml.example``.
To create a REST API configuration file, download this example file to the
config directory and name it ``rest_api.toml``. Then edit the file to change the
example configuration options as necessary for your system.

The ``rest_api.toml`` configuration file has the following options:

- ``bind`` = ["`HOST:PORT`"]

  Sets the port and host for the REST API to run on.
  Default: ``127.0.0.1:8008``. For example:

  .. code-block:: none

    bind = ["127.0.0.1:8008"]

- ``connect`` = "`URL`"

  Identifies the URL of a running validator. Default: ``tcp://localhost:4004``.
  For example:

  .. code-block:: none

    connect = "tcp://localhost:4004"

- ``timeout`` = `value`

  Specifies the time, in seconds, to wait for a validator response.
  Default: 300. For example:

  .. code-block:: none

    timeout = 900

- ``client_max_size`` = `value`

  Specifies the size, in bytes, that the REST API will accept for the body of
  requests. If the body is larger a ``413: Request Entity Too Large`` will be
  returned
  Default: 10485760 (or 10 MB). For example:

  .. code-block:: none

    client_max_size = 10485760

- ``opentsdb_url`` = "`value`"

  Sets the host and port for Open TSDB database (used for metrics).

- ``opentsdb_db`` = "`name`"

  Sets the name of the Open TSDB database. Default: none.

- ``opentsdb_username`` = `username`

  Sets the username for the Open TSDB database. Default: none.

- ``opentsdb_password`` = `password`

  Sets the password for the Open TSDB database. Default: none.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
