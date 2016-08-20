**********************
The Workload Simulator
**********************

Overview
--------

Sawtooth Lake has a workload simulator that can be used to generate a
synthetic transaction workload.  The workload simulator attempts to generate
transactions at a relatively steady rate across the network of validators
it has discovered, adapting to validators joining and leaving the network.
In its simplest form, the workload simulator is started as follows:

.. code-block:: console

    $ cd /project/sawtooth-core
    $ ./bin/simulator
    [22:35:28 INFO    simulator_cli] Simulator configuration:
    [22:35:28 INFO    simulator_cli] Simulator: url = http://127.0.0.1:8800
    [22:35:28 INFO    simulator_cli] Simulator: workload = txnintegration.integer_key_workload.IntegerKeyWorkload
    [22:35:28 INFO    simulator_cli] Simulator: rate = 12
    [22:35:28 INFO    simulator_cli] Simulator: discover = 15
    [22:35:28 INFO    simulator_cli] Simulator: verbose = 1
    [22:35:28 INFO    simulator] Discovered a new validator: http://127.0.0.1:8800
    [22:35:28 INFO    simulator] Discovered a new validator: http://127.0.0.1:8803
    [22:35:28 INFO    simulator] Discovered a new validator: http://127.0.0.1:8801
    [22:35:28 INFO    simulator] Discovered a new validator: http://127.0.0.1:8804
    [22:35:28 INFO    simulator] Discovered a new validator: http://127.0.0.1:8802
    [22:35:28 INFO    simulator] Simulator will generate 12 transaction(s)/minute
    [22:35:28 INFO    simulator] Simulator will discover validators every 15 minute(s)

Without any command-line options, the workload simulator attempts to load the
configuration file that controls execution from
``<USER_HOME>/.sawtooth/simulator.cfg``.  If the file does not exist, the
workload simulator will create it and populate it with the defaults shown
above.

Configuration File
------------------

An example configuration file is as follows:

.. code-block:: none

    [Simulator]
    url = http://127.0.0.1:8800
    workload = txnintegration.integer_key_workload.IntegerKeyWorkload
    rate = 12
    discover = 15
    verbose = 1

The Simulator section of the configuration file contains name/value pairs that
are used to control the execution of the workload simulator.  The names in the
name/value pairs correspond directly to command-line options that share the
same name.  If a command-line option has one or more dashes in it, the
corresponding configuration file option name will replace the dashes with
underscores.  The configuration file options are:

* ``url`` The URL of the initial validator used to prime the simulator.  The
  simulator will begin with this validator's endpoint registry to discover
  the validators in the validator network and then for each new validator
  discovered will fetch its endpoint registry and will keep doing this until
  it has discovered all of the validators in the validator network.  If this
  option is not present in the configuration file, the default is
  \http://127.0.0.1:8800.
* ``workload`` The workload generator that will be used to generate
  transactions.  This is specified as module_name.class_name.  If this option
  is not present in the configuration file, the default is
  txnintegration.integer_key_workload.IntegerKeyWorkload.
* ``rate`` The rate, in transactions per minute, that the workload simulator
  will attempt to generate transactions.  If this option is not present in the
  configuration file, the default is 12 transactions per minute.
* ``discover`` How often, in minutes, that the workload simulator will check
  for changes in the validator network.  If this options is not present in the
  configuration file, the default is once every 15 minutes.
* ``verbose`` The verbosity level for workload simulator logging messages
  that are displayed on the console.  Verbosity values correspond to the
  following:

    * 0: display messages with logging level of WARNING and above
    * 1: display messages with logging level of INFO and above
    * >= 2: display messages with logging level of DEBUG and above

  If this options is not present in the configuration file, the default
  verbosity level is 1.

.. note::

    Individual transaction workloads may also have their own sections that
    contain values.


Command-Line Options
--------------------

The workload simulator has numerous command-line options, all of which can be
seen by executing the command with the ``--help`` (or ``-h``) command-line
option.

.. note::

    Any options provided on the command-line override their corresponding
    entries in the configuration file or defaults for options that do not
    appear in the configuration file.

.. code-block:: console

    $ ./bin/simulator --help
    usage: simulator [-h] [--url] [--workload WORKLOAD] [--rate RATE]
                     [--discover DISCOVER] [--config CONFIG] [-v]

    optional arguments:
      -h, --help           show this help message and exit
      --url                Base validator URL
      --workload WORKLOAD  Transaction workload
      --rate RATE          Transaction rate in transactions per minute
      --discover DISCOVER  How often, in minutes, to refresh validators list
      --config CONFIG      Config file to provide base configuration for the
                           simulator and (possibly) the workload generator.
                           Command-line options override corresponding values in
                           the configuration file
      -v, --verbose        enable more verbose output

The verbosity of the workload simulator is controlled by the number of
occurrences of the ``--verbose`` (or ``-v``) option.  The number of occurrences
directly correspond to the numeric value described above for the ``verbose``
configuration file option.  For example, ``-vv``, ``-v -v``, and
``--verbose --verbose`` all would result in logging messages with level
DEBUG and above being displayed on the console.

The ``--config CONFIG`` option is used to specify the configuration file to
use in place of the default one.

The remaining command-line options correspond directly to their counterparts
in the configuration file.

