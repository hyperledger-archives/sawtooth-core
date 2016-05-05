********
Tutorial
********

Overview
========

This tutorial walks through the process of setting up a virtual development
environment for the Distributed Ledger using Vagrant and VirtualBox. At the
end, you will have a running validator network and be able to use client
commands to interact with it.

Commands in this tutorial can be run via Terminal.app on MacOS, Git Bash on
Windows, etc.

Prerequisites
=============

The following tools are required:

* `Vagrant <https://www.vagrantup.com/downloads.html>`_ (1.7.4 or later)
* `VirtualBox <https://www.virtualbox.org/wiki/Downloads>`_ (5.0.10 r104061
  or later)

On Windows, you will also need to install:

* `Git for Windows <http://git-scm.com/download/win>`_

Git for Windows will provide not only git to clone the repositories, but also
ssh which is required by Vagrant. During installation, accept all defaults.

Clone Repositories
==================

All five repositories (sawtooth-core, sawtooth-dev-tools, sawtooth-docs,
sawtooth-mktplace, and sawtooth-validator) must be cloned into the same parent
directory as follows:

.. code-block:: console

  project/
    sawtooth-core/
    sawtooth-dev-tools/
    sawtooth-docs/
    sawtooth-mktplace/
    sawtooth-validator/

This can be done by opening up a terminal and running the following:

.. code-block:: console

   % cd $HOME
   % mkdir project
   % cd project
   % git clone https://github.com/IntelLedger/sawtooth-core.git
   % git clone https://github.com/IntelLedger/sawtooth-dev-tools.git
   % git clone https://github.com/IntelLedger/sawtooth-docs.git
   % git clone https://github.com/IntelLedger/sawtooth-mktplace.git
   % git clone https://github.com/IntelLedger/sawtooth-validator.git

.. note::

   When Vagrant is started (covered in the next section), the configuration
   will check for the presence of these repositories. If any of the
   repositories are missing, Vagrant will print an error to stderr and exit:

   .. code-block:: console

      % vagrant up
      ...
      Repository ../sawtooth-core needs to exist

Environment Startup
===================

In order to start the vagrant VM, change the current working directory to
sawtooth-dev-tools on the host and run:

.. code-block:: console

  % cd sawtooth-dev-tools
  % vagrant up

.. note::

   We have encountered an intermittent problem on Windows hosts which
   presents as an 'Operation not permitted' error in the vagrant startup
   output. If you encounter this error, perform a 'vagrant destroy' and
   then run 'vagrant up' again.

Downloading the Vagrant box file, booting the VM, and running through
the bootstrap scripts will take several minutes.

Once the 'vagrant up' command has finished executing, run:

.. code-block:: console

  % vagrant ssh

By default, Vagrant sets up ssh keys so that users can log into the VM
without setting up additional accounts or credentials. The logged in user,
vagrant (uid 1000), also has permissions to execute sudo with no password
required. Any number of `vagrant ssh` sessions can be established from the
host.

Resetting the Environment
=========================

If the VM needs to be reset for any reason, it can be returned to the default
state by running the following commands from the sawtooth-dev-tools directory
on the host:

.. code-block:: console

  % vagrant destroy
  % vagrant up

.. caution::

   vagrant destroy will delete all contents within the VM. However,
   /vagrant and /project are shared with the host and will be preserved.

Building sawtooth-core
======================

The vagrant environment is setup in such a way that installation of the
software is not required.  However, the C++/swig code must be built.  To
build, run the following inside vagrant:

.. code-block:: console

  $ cd /project/sawtooth-core
  $ python setup.py build

Running txnvalidator
====================

To start txnvalidator, log in to the development environment with 'vagrant ssh'
and run the following command:

.. note::

    There are two underscores before and after the word screen in the command
    below.

.. code-block:: console

   $ cd /project/sawtooth-validator
   $ ./bin/txnvalidator --logfile=__screen__ --http 8800

This will startup txnvalidator and logging output will be printed to the
terminal window.

To stop the validator, press CTRL-c.

.. caution::

   When run as above, txnvalidator will start a new blockchain each time
   it starts.  If you want to start txnvalidator with the previous
   blockchain, use the '--restore' flag.

Running Multiple Validators
===========================

If you wish to start up a validator network with multiple instances of txnvalidator,
but do not want to either bring up multiple virtual machine instances or use separate
physical machines, there is a script that simplifies the process or running multiple
instances of txnvalidator on a single virtual machine instance.  As in the single
txnvalidator case, you will need to log in to the development environment
(i.e., 'vagrant ssh').  In its simplest form, the script is executed as follows:

.. code-block:: console

    $ cd /project/sawtooth-validator
    $ ./bin/launcher
    No config file specified, loading  /project/sawtooth-validator/etc/txnvalidator.js
    Overriding the following keys from validator configuration file: /project/sawtooth-validator/etc/txnvalidator.js
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
                                u'LedgerType': u'lottery',
                                u'LedgerURL': u'http://localhost:8800/',
                                'LogLevel': 'WARNING',
                                u'MaxTransactionsPerBlock': 1000,
                                u'MinTransactionsPerBlock': 1,
                                u'NetworkBurstRate': 128000,
                                u'NetworkDelayRange': [0.0, 0.1],
                                u'NetworkFlowRate': 96000,
                                u'Restore': False,
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
/project/sawtooth-validator/etc/txnvalidator.js, as well as any configuration
settings that it has overridden.

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

To initially launch, for example, two txnvalidator instances and have the logging
level set to DEBUG, execute the following:

.. code-block:: console

    $ ./bin/launcher --count 2 --log-level DEBUG

.. note::

    By default, the log files will be located in a temporary directory in /tmp,
    with each txnvalidator instance having its own log file.

After the script launches the requested number of txnvalidator instances, it
presents a command-line interface.

.. code-block:: console

    Welcome to the sawtooth txnvalidator network manager interactive console
    launcher_cli.py>

Execute the ``help`` command to learn about the commands available via the command-line
interface.

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

Execute the ``status`` command to get information about the running txnvalidator
instances.

.. code-block:: console

    launcher_cli.py> status
    0:  pid:8827   log: 18.77 KB
    1:  pid:8831   log: 19.23 KB

Based upon the initial execution of the script with an instance count of two and
the log level set to DEBUG, the ``status`` command, as expected, presents information
about two txnvalidator instances.  For each txnvalidator instance, the following
information is presented:

* Instance ID, which is used for all commands that are specific to a txnvalidator instance
* Process ID
* Log file size

To add another txnvalidator instance to the existing validator network, execute the ``launch``
command.  When the status command is run, there are now three txnvalidator instances.

.. code-block:: console

    launcher_cli.py> launch
    Validator validator-2 launched.
    launcher_cli.py> status
    0:  pid:8827   log: 31.71 KB
    1:  pid:8831   log: 30.31 KB
    2:  pid:8959   log: 16.76 KB

To see the configuration information for the txnvalidator instance that was just
launched to, for example, get the HTTP port it is listening on, execute the ``config``
command, providing the txnvalidator instance ID.

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
        "Restore": false,
        "InitialWaitTime": 750.0,
        "DataDirectory": "/tmp/tmpylbmp_",
        "LogLevel": "DEBUG",
        "LedgerType": "lottery",
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

To view the log file for a txnvalidator instance, navigate to the data directory,
which can either be specified as a command-line parameter to the script,
or can be obtained by executing the config command for a particular txnvalidator
instance.  Alternatively, execute the ``log`` command for a particular txnvalidator
instance:

.. code-block:: console

    launcher_cli.py> log 2
    [21:10:14, 10, validator_cli] CONFIG: TransactionFamilies = ['ledger.transaction.integer_key', 'sawtooth_xo']
    [21:10:14, 10, validator_cli] CONFIG: TargetConnectivity = 3
    <numerous lines removed>
    [21:10:14, 20, connect_message] received connect confirmation from node validator-0
    [21:10:14, 20, node] enabling node 16rgLPPvsGdbCkanmfWnXo8RQxjKVYyHoQ
    [21:10:15, 10, gossip_core] clean up processing 1 unacked packets

To remove a txnvalidator instance from the validator network, execute the ``kill`` command,
providing its instance ID.  For example, to remove the txnvalidator instance that was
just launched, execute the following:

.. code-block:: console

    launcher_cli.py> kill 2
    Validator validator-2 killed.

To tear down the validator network, execute the ``exit`` command.  It will take care of
stopping each of the txnvalidator instances as well as cleaning up any temporary
files/directories that were created.

.. code-block:: console

    launcher_cli.py> exit
    Sending shutdown message to validators: : ... 0.04S
    Giving validators time to shutdown: : .......... 10.02S
    Killing 2 intransigent validators: : ... 0.00S
    Cleaning temp data store /tmp/tmpylbmp_

Working with the MarketPlace Transaction Family
===============================================

In this section of the tutorial, we will walk though the process of starting
a single validator node and working with mktclient to create users, accounts,
and perform an exchange.

We will setup a couple participants, Alice and Bob, who will exchange goods
(in this case, cookies) for currency (US Dollars).

Configure txnvalidator.js and Start txnvalidator
------------------------------------------------

By default, the validator is not configured to support the MarketPlace
transaction family or operate efficiently as a single node network. 
The default validator config is in: sawtooth-validator/etc/. 

Let's instead work with a config file specific to this tutorial. 
Most of the the edits are done already, but let's add the marketplace 
transaction family. 

Edit /project/sawtooth-docs/source/tutorial/txnvalidator.js
and add "mktplace.transactions.market_place" to the list of transaction
families:

.. note::
     Don't miss the comma at the end of the integer_key line, before your new
     line for market_place!

.. code-block:: json

    "TransactionFamilies" : [
        "ledger.transaction.integer_key",
        "mktplace.transactions.market_place"
    ],

To test the changes, startup txnvalidator:

.. code-block:: console

   $ cd /project/sawtooth-validator
   $ ./bin/txnvalidator --logfile=__screen__ --config /project/sawtooth-docs/source/tutorial/txnvalidator.js

Keep txnvalidator running while we interact with it using mktclient below.
Open a new terminal in your **host** OS and type:

.. code-block:: console

   $ cd $HOME/project/sawtooth-dev-tools
   $ vagrant ssh

Key Generation
--------------

First, we need to create key files for each participant that we are going
to use:

  * The Marketplace
  * Alice
  * Bob

Normally these participants may be on different machines talking to different
validators, but for this tutorial we control all the participants, so we
generate a key for each of them:

.. code-block:: console

   $ cd /project/sawtooth-validator
   $ ./bin/txnkeygen --keydir keys mkt
   $ ./bin/txnkeygen --keydir keys alice
   $ ./bin/txnkeygen --keydir keys bob

Object Names
------------

Objects within MarketPlace are referenced (named) using paths separated by a
slash (/).  The number of leading slashes determines whether the reference
is an absolute path, a relative path, or an identifier. 

============ =================== =============================================
Count        Format              Description
============ =================== =============================================
Single (/)   /<PATH>             Relative to the current key in use
Double (//)  //<CREATOR>/<PATH>  Fully qualified name
Triple (///) ///<IDENTIFIER>     The object identifier
============ =================== =============================================

In this tutorial, we will stick to the relative paths when possible and specify
absolute paths when referencing objects created by another key (another user).

For example, both Alice and Bob will end up with "/USD" (a relative path), and
the associated absolute paths will be "//bob/USD" and "//alice/USD".

Market Initialization
---------------------

We will use The Marketplace participant (mkt) to setup our example market
so that Alice and Bob can exchange cookies for USD (US dollars).  Bob will
start with a lot of freshly baked cookies and sell them to Alice.

Start mktclient as The Marketplace participant:

.. code-block:: console

   $ cd /project/sawtooth-mktplace
   $ ./bin/mktclient --name mkt

Now execute commands as The Marketplace participant (mkt) using the
mktclient shell you just opened.  As you perform these commands, you will
see activity in the txnvalidator output.

To start, let's register the mkt participant, create mkt's account, and
a holding for tokens (a special asset only covered briefly below).

.. code-block:: none

   //UNKNOWN> participant reg --name mkt --description "The Marketplace"
   //mkt> account reg --name /market/account
   //mkt> holding reg --name /market/holding/token --count 1 --account /market/account --asset //marketplace/asset/token

The special token asset is useful for bootstrapping purposes.  Tokens are
non-consumable, in that they are never deducted from a holding even when
exchanged for another asset.  The /market/holding/token as defined has 1 token,
but since it will never be deducted during an exchange, it really has an
infinite number of tokens in practice.  We use it below to create an inital
one-time offer of USD to new participants (an offer which Bob and Alice will
accept later).

Now let's add the currency asset type and USD asset.  Note the count of USD
below is a fixed amount.  By default, asset types are restricted and only the
creator of the asset type can create assets of that type; so here, USD can only
be created by the mkt participant.  The holding will initially contain 20000000
USD.  The sell offer allows new participants to do a one-time exchange for 1000
USD, for the purposes of new participant initialization.

.. code-block:: none

   //mkt> assettype reg --name /asset-type/currency
   //mkt> asset reg --name /asset/currency/USD --type /asset-type/currency
   //mkt> holding reg --name /market/holding/currency/USD --count 20000000 --account /market/account --asset /asset/currency/USD
   //mkt> selloffer reg --name /offer/provision/USD --minimum 1 --maximum 1 --modifier ExecuteOncePerParticipant --output /market/holding/currency/USD --input /market/holding/token --ratio 1 1000

Now that we have USD setup, we need to add the concept of cookies, and
specifically Chocolate Chip cookies, into our blockchain.  To do this, let's
create a cookie asset-type and a Chocolate Chip asset.  If we had different
type of cookies, such as Peanut Butter, we could create additional assets
to represent them.  The cookie asset type is unrestricted, so anyone in the
market place can create cookies.  (Later, Bob will bake a batch.)

.. code-block:: none

   //mkt> assettype reg --name /asset-type/cookie --no-restricted
   //mkt> asset reg --name /asset/cookie/choc_chip --type /asset-type/cookie --no-restricted

The commands above are sent to the validator and applied to the network
asynchronously and may not yet be committed.  You can use the 'waitforcommit'
to have the client block until the changes have been committed:

.. code-block:: none

   //mkt> waitforcommit

.. note::

   :command:`waitforcommit` can potentially take several minutes with a small
   number of validators.  For this section of the tutorial, we are running with
   a single validator and have updated the configuration such that it will
   usually return within a reasonable amount of time.  PoET (the consensus
   mechanism) is optimized for more realistic use cases (not a single
   validator).  The amount of time to wait is related to several factors,
   including a random number mapped to an exponential distribution.  So, if you
   get unlucky, :command:`waitforcommit` might take a while.  As the number of
   validators increases, the average wait time becomes more stable and
   predictable.

Market initialization is complete, so you can now exit mktclient:

.. code-block:: none

   //mkt> exit

Registering Accounts
--------------------

In the previous section, we registered the mkt account.  In this section, we
will register, create accounts, and create initial holdings for both Bob and
Alice.

First, let's register Bob.  Startup mktclient using the name of Bob's key file
(bob):

.. code-block:: console

   $ cd /project/sawtooth-mktplace
   $ ./bin/mktclient --name bob

Register Bob as a participant and create his account:

.. code-block:: none

   //UNKNOWN> participant reg --name bob
   //bob> account reg --name /account

Now we initialize Bob's USD holding.  We create the USD holding, which will
be empty (Bob can't create USD), and then accept the once-per-particiant
offer from the mkt participant to receive 1000 USD.

.. code-block:: none

   //bob> holding reg --name /USD --account /account --asset //mkt/asset/currency/USD
   //bob> holding reg --name /holding/token --count 1 --account /account --asset //marketplace/asset/token
   //bob> waitforcommit
   //bob> exchange --src /holding/token --dst /USD --offers //mkt/offer/provision/USD --count 1

Next, let's create an empty cookie jar for Chocolate Chip cookies:

.. code-block:: none

   //bob> holding reg --name /jars/choc_chip --account /account --asset //mkt/asset/cookie/choc_chip

That is it for Bob's setup, so waitforcommit and exit:

.. code-block:: none

   //bob> waitforcommit
   //bob> exit

Now, let's register Alice in the same way.  Startup mktclient using the name of
Alice's key file (alice):

.. code-block:: console

   $ cd /project/sawtooth-mktplace
   $ ./bin/mktclient --name alice

Alice's initalization is the same as Bob's:

.. code-block:: none

   //UNKNOWN> participant reg --name alice
   //alice> account reg --name /account
   //alice> holding reg --name /USD --account /account --asset //mkt/asset/currency/USD
   //alice> holding reg --name /holding/token --count 1 --account /account --asset //marketplace/asset/token
   //alice> waitforcommit
   //alice> exchange --src /holding/token --dst /USD --offers //mkt/offer/provision/USD --count 1
   //alice> holding reg --name /jars/choc_chip --account /account --asset //mkt/asset/cookie/choc_chip
   //alice> waitforcommit
   //alice> exit

Now we have both Alice and Bob's account and holdings initialized.

Create an Exchange Offer
------------------------

Let's assume Bob has baked two dozen Chocolate Chip cookies and wants to create
an exchange offer of $2 per cookie.

Start mktclient with Bob's key:

.. code-block:: console

   $ cd /project/sawtooth-mktplace
   $ ./bin/mktclient --name bob

Let's create a new holding representing Bob's batch of cookies and initialize
it with 24 cookies.  Then create an exchange offer:

.. code-block:: none

   //bob> holding reg --name /batches/choc_chip001 --account /account --asset //mkt/asset/cookie/choc_chip --count 24
   //bob> exchangeoffer reg --output /batches/choc_chip001 --input /USD --ratio 2 1 --name /choc_chip_sale
   //bob> waitforcommit

Now Bob has two dozen cookies on the market for $2 each.  The ratio argument
says "2 USD for 1 cookie".

View the Bob's current holdings:

.. code-block:: none

   //bob> holdings --creator //bob
   1000     //bob/USD
   24       //bob/batches/choc_chip001
   1        //bob/holding/token
   0        //bob/jars/choc_chip

We can also view Bob's current offers:

.. code-block:: none

   //bob> offers --creator //bob
   Ratio    Input Asset (What You Pay)          Output Asset (What You Get)         Name
   0.5      //mkt/asset/currency/USD            //mkt/asset/cookie/choc_chip        //bob/choc_chip_sale

Great!  Now Bob waits for someone to accept his offer, so we can exit
mktclient:

.. code-block:: none

   //bob> exit

Accept the Exchange Offer
-------------------------

Alice has decided to purchase some cookies and has decided to accept Bob's
exchange offer.

.. code-block:: console

   $ cd /project/sawtooth-mktplace
   $ ./bin/mktclient --name alice

Execute an exchange (accepting Bob's offer):

.. code-block:: none

   //alice> exchange --src /USD --dst /jars/choc_chip --offers //bob/choc_chip_sale --count 24
   //alice> waitforcommit

The count above is related to the --src argument, so 24 USD for a dozen
cookies.  Let's see what the resulting holdings look like:

.. code-block:: none

   //alice> holdings --creator //bob
   1024     //bob/USD
   12       //bob/batches/choc_chip001
   1        //bob/holding/token
   0        //bob/jars/choc_chip
   //alice> holdings --creator //alice
   976      //alice/USD
   1        //alice/holding/token
   12       //alice/jars/choc_chip

Fantastic!  Bob has more USD and fewer cookies.  Alice has less USD and more
cookies.
