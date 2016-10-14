******************************
The Validator Network Launcher
******************************

Overview
--------

If you wish to start up a validator network with multiple instances of
txnvalidator, but do not want to either bring up multiple virtual machine
instances or use separate physical machines, there is a script that simplifies
the process for running multiple instances of txnvalidator on a single virtual
machine instance.  As in the single txnvalidator case, you will need to log in
to the development environment (i.e., ``vagrant ssh``).  In its simplest form,
the script is executed as follows:

.. code-block:: console

    $ cd /project/sawtooth-validator
    $ ./bin/launcher
    No config file specified, loading  /project/sawtooth-core/validator/etc/txnvalidator.js
    Overriding the following keys from validator configuration file: /project/sawtooth-core/validator/etc/txnvalidator.js
            NodeName
            Host
            HttpPort
            Port
            LogFile
            LogLevel
            KeyFile
            GenesisLedger
    Configuration:
    {   'config': '/project/sawtooth-validator/etc/txnvalidator.js',
        'count': 1,
        'data_dir': '/tmp/tmpohtWIM',
        'data_dir_is_tmp': True,
        'load_blockchain': None,
        'log_level': 'WARNING',
        'save_blockchain': None,
        'validator': '/project/sawtooth-validator/bin/txnvalidator',
        'validator_config': {   u'CertificateSampleLength': 30,
                                u'InitialWaitTime': 750.0,
                                u'LedgerType': u'poet0',
                                u'LedgerURL': u'http://localhost:8800/',
                                'LogLevel': 'WARNING',
                                u'MaxTransactionsPerBlock': 1000,
                                u'MinTransactionsPerBlock': 1,
                                u'NetworkBurstRate': 128000,
                                u'NetworkDelayRange': [0.0, 0.1],
                                u'NetworkFlowRate': 96000,
                                u'TargetConnectivity': 3,
                                u'TargetWaitTime': 30.0,
                                u'TopologyAlgorithm': u'RandomWalk',
                                u'TransactionFamilies': [   u'ledger.transaction.integer_key',
                                                            u'sawtooth_xo'],
                                u'UseFixedDelay': True}}
    Launching initial validator: .......... 10.08S
    Launching validator network:  0.00S
    Waiting for validator registration: . 1.12S

Without any command-line options, the script launches a single txnvalidator
instance.  As can be seen from the output above, the launcher reports the
configuration file used, usually
/project/sawtooth-core/validator/etc/txnvalidator.js, as well as any configuration
settings that it has overridden.

After the script launches the txnvalidator instance(s), it presents an
interactive shell command-line interface:

.. code-block:: console

    Welcome to the sawtooth txnvalidator network manager interactive console
    launcher_cli.py>

Command-Line Options
--------------------

The launcher has numerous command-line options, all of which can be seen by
executing the command with the ``--help`` (or ``-h``) command-line option.

.. code-block:: console

    $ ./bin/launcher --help

    usage: launcher [-h] [--validator VALIDATOR] [--config CONFIG] [--count COUNT]
                [--save-blockchain SAVE_BLOCKCHAIN]
                [--load-blockchain LOAD_BLOCKCHAIN] [--data-dir DATA_DIR]
                [--log-level LOG_LEVEL]

    optional arguments:
      -h, --help            show this help message and exit
      --validator VALIDATOR
                            Fully qualified path to the txnvalidator to run
      --config CONFIG       Base validator config file
      --count COUNT         Number of validators to launch
      --save-blockchain SAVE_BLOCKCHAIN
                            Save the blockchain to a file when the network is
                            shutdown. This is the name of the tar.gz file that the
                            blockchain will be saved in.
      --load-blockchain LOAD_BLOCKCHAIN
                            load an existing blockchain from file. This is a file
                            name that points to a tar.gz that was generated from a
                            previous run using the --save-blockchain option.
      --data-dir DATA_DIR   Where to store the logs, data, etc for the network
      --log-level LOG_LEVEL
                            LogLevel to run the validators at.

To initially launch, for example, two txnvalidator instances and have the
logging level set to DEBUG, execute the following:

.. code-block:: console

    $ ./bin/launcher --count 2 --log-level DEBUG

.. note::

    By default, the log files will be located in a temporary directory in /tmp,
    with each txnvalidator instance having its own log file.

Obtaining Help About Available Commands
---------------------------------------

Execute the ``help`` command to learn about the commands available via the
command-line interface.

.. code-block:: console

    launcher_cli.py> help

    Documented commands (type help <topic>):
    ========================================
    config  exit  help  launch  launch_cmd  status

    Undocumented commands:
    ======================
    EOF  err  kill  log  out

As the help command indicates, you can learn more about a specific command by
executing ``help <command_name>``.

Retrieving the Status of the Validator Network
----------------------------------------------

Execute the ``status`` command to get information about the running
txnvalidator instances.

.. code-block:: console

    launcher_cli.py> status
    0:  pid:8827   log: 18.77 KB
    1:  pid:8831   log: 19.23 KB

Based upon the initial execution of the script with an instance count of two
and the log level set to DEBUG, the ``status`` command, as expected, presents
information about two txnvalidator instances.  For each txnvalidator instance,
the following information is presented:

* Instance ID, which is used for all commands that are specific to a txnvalidator instance
* Process ID
* Log file size

Adding a Validator to the Validator Network
-------------------------------------------

To add another txnvalidator instance to the existing validator network, execute
the ``launch`` command.  When the status command is run, there are now three
txnvalidator instances.

.. code-block:: console

    launcher_cli.py> launch
    Validator validator-2 launched.
    launcher_cli.py> status
    0:  pid:8827   log: 31.71 KB
    1:  pid:8831   log: 30.31 KB
    2:  pid:8959   log: 16.76 KB

Retrieving a Validator's Configuration
--------------------------------------

To see the configuration information for the txnvalidator instance that was
just launched to, for example, get the HTTP port it is listening on, execute
the ``config`` command, providing the txnvalidator instance ID.

.. code-block:: console

    launcher_cli.py> config 2
    {
        "NodeName": "validator-2",
        "TransactionFamilies": ["ledger.transaction.integer_key", "sawtooth_xo"],
        "TargetConnectivity": 3,
        "TargetWaitTime": 30.0,
        "GenesisLedger": false,
        "HttpPort": 8802,
        "id": 2,
        "LogFile": "/tmp/tmpylbmp_/validator-2.log",
        "MaxTransactionsPerBlock": 1000,
        "NetworkFlowRate": 96000,
        "CertificateSampleLength": 30,
        "InitialWaitTime": 750.0,
        "DataDirectory": "/tmp/tmpylbmp_",
        "LogLevel": "DEBUG",
        "LedgerType": "poet0",
        "UseFixedDelay": true,
        "Host": "localhost",
        "LedgerURL": "http://localhost:8800",
        "NetworkBurstRate": 128000,
        "NetworkDelayRange": [0.0, 0.1],
        "AdministrationNode": "1EQFYqvMRLpjTjL5Bv3vSAMrZdnRY6e5uk",
        "MinTransactionsPerBlock": 1,
        "KeyFile": "/tmp/tmp4K9qEd/validator-2.wif",
        "Port": 8902,
        "TopologyAlgorithm": "RandomWalk"
    }

As can be seen from the configuration information above, the newly-launched
txnvalidator instance is listening on port 8802.

Viewing a Validator's Log File
------------------------------

To view the log file for a txnvalidator instance, navigate to the data
directory, which can either be specified as a command-line parameter to the
script, or can be obtained by executing the config command for a particular
txnvalidator instance.  Alternatively, execute the ``log`` command for a
particular txnvalidator instance:

.. code-block:: console

    launcher_cli.py> log 2
    [21:10:14, 10, validator_cli] CONFIG: TransactionFamilies = ['ledger.transaction.integer_key', 'sawtooth_xo']
    [21:10:14, 10, validator_cli] CONFIG: TargetConnectivity = 3
    <numerous lines removed>
    [21:10:14, 20, connect_message] received connect confirmation from node validator-0
    [21:10:14, 20, node] enabling node 16rgLPPvsGdbCkanmfWnXo8RQxjKVYyHoQ
    [21:10:15, 10, gossip_core] clean up processing 1 unacked packets

Removing a Validator from the Validator Network
-----------------------------------------------

To remove a txnvalidator instance from the validator network, execute the
``kill`` command, providing its instance ID.  For example, to remove the
txnvalidator instance that was just launched, execute the following:

.. code-block:: console

    launcher_cli.py> kill 2
    Validator validator-2 killed.

Tearing Down the Validator Network
----------------------------------

To tear down the validator network, execute the ``exit`` command.  It will take
care of stopping each of the txnvalidator instances as well as cleaning up any
temporary files/directories that were created.

.. code-block:: console

    launcher_cli.py> exit
    Sending shutdown message to validators: : ... 0.04S
    Giving validators time to shutdown: : .......... 10.02S
    Killing 2 intransigent validators: : ... 0.00S
    Cleaning temp data store /tmp/tmpylbmp_
