**********************
The Workload Generator
**********************

Overview
--------

Sawtooth has a workload generator that can be used to generate a
synthetic transaction workload.  The workload generator attempts to generate
transactions at a relatively steady rate across the network of validators that
are specified. In its simplest form, the workload generator is started as
follows:

.. code-block:: console

    $ cd /project/sawtooth-core
    $ ./bin/intkey workload --urls tcp://127.0.0.1:4004 --rate 1 -d 5
    [21:09:15 WARNING workload_generator] Transaction submission rate for last sample period is 0.80 tps
    [21:09:15 WARNING workload_generator] Transaction commit rate for last sample period is 0.60 tps
    [21:09:15 WARNING workload_generator] Transaction submission rate for last 1 sample(s) is 0.80 tps
    [21:09:15 WARNING workload_generator] Transaction commit rate for last 1 sample(s) is 0.60 tps
    [21:09:20 WARNING workload_generator] Transaction submission rate for last sample period is 1.00 tps
    [21:09:20 WARNING workload_generator] Transaction commit rate for last sample period is 1.00 tps
    [21:09:20 WARNING workload_generator] Transaction submission rate for last 2 sample(s) is 0.90 tps
    [21:09:20 WARNING workload_generator] Transaction commit rate for last 2 sample(s) is 0.80 tps


Command-Line Options
--------------------

The workload generator has numerous command-line options, all of which can be
seen by executing the command with the ``--help`` (or ``-h``) command-line
option.

.. code-block:: console

    $ intkey workload -h
    usage: intkey workload [-h] [-v] [--rate RATE] [-d DISPLAY_FREQUENCY]
                       [-u URLS]

    optional arguments:
    -h, --help            show this help message and exit
    -v, --verbose         enable more verbose output
    --rate RATE           Batch rate in batches per second. Should be greater
                        then 0.
    -d DISPLAY_FREQUENCY, --display-frequency DISPLAY_FREQUENCY
                        time in seconds between display of batches rate
                        updates.
    -u URLS, --urls URLS  comma separated urls of validators to connect to.


The verbosity of the workload generator is controlled by the number of
occurrences of the ``--verbose`` (or ``-v``) option. For example, ``-vv``,
``-v -v``, and ``--verbose --verbose`` all would result in logging messages
with level DEBUG and above being displayed on the console.

The default batch rate, if it is not specified, is 1 batch per second.

The default display refresh frequency is 30 seconds.

The default url to connect to is `tcp://127.0.0.1:4004`.
