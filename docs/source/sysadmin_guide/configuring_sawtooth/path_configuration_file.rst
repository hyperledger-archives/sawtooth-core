-----------------------
Path Configuration File
-----------------------

.. Important::

  Changing the path settings in this file is usually unnecessary.
  For non-standard directory paths, use the ``SAWTOOTH_HOME`` environment
  variable instead of this configuration file.

The ``path.toml`` configuration changes the Sawtooth ``data_dir`` directory.
This file should be used only when installing on an operating system
distribution where the  default paths are not appropriate. For example, some
Unix-based operating systems do not use ``/var/lib``, so it would be appropriate
to use this file to set ``data_dir`` to the natural operating system default
path for application data.

An example file is in ``/etc/sawtooth/path.toml.example``. To create a path
configuration file, copy the example file to the config directory and name it
``path.toml``. Then edit the file to change the example configuration options as
necessary for your system.

This file configures the following settings:

- ``key_dir`` = `path`

  Directory path to use when loading key files

- ``data_dir`` = `path`

  Directory path for storing data files such as the block store

- ``log_dir`` = `path`

  Directory path to use to write log files
  (by default, an error log and a debug log; see :doc:`../log_configuration`).

- ``policy_dir`` = `path`

  Directory path for storing policies

The default directory paths depend on whether the ``SAWTOOTH_HOME`` environment
variable is set. When ``SAWTOOTH_HOME`` is set, the default paths are:

- ``key_dir`` = ``SAWTOOTH_HOME/keys/``
- ``data_dir`` = ``SAWTOOTH_HOME/data/``
- ``log_dir`` = ``SAWTOOTH_HOME/logs/``
- ``policy_dir`` = ``SAWTOOTH_HOME/policy/``

For example, if ``SAWTOOTH_HOME`` is set to ``/tmp/testing``, the default path
for ``data_dir`` is ``/tmp/testing/data/``.

When ``SAWTOOTH_HOME`` is not set, the operating system defaults are used.
On Linux, the default path settings are:

- ``key_dir`` = ``/etc/sawtooth/keys``
- ``data_dir`` = ``/var/lib/sawtooth``
- ``log_dir`` = ``/var/log/sawtooth``
- ``policy_dir`` = ``/etc/sawtooth/policy``

Sawtooth also uses ``config_dir`` to determine the directory path containing the
configuration files. Note that this directory is fixed; it cannot be changed in
the ``path.toml`` configuration file.

- If ``SAWTOOTH_HOME`` is set, ``conf_dir`` = ``SAWTOOTH_HOME/etc/``

- If ``SAWTOOTH_HOME`` is not set, ``conf_dir`` = ``/etc/sawtooth``

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
