
----------------------------
MarketPlace Client Reference
----------------------------

The MarketPlace Client, aka mktclient, provides an interactive shell that
can be use to interact with a validator network using the MarketPlace
Transaction Family.

This section serves as a reference for mktclient.  If you would like
a tutorial to walk you through a simple example of using mktclient,
please consult :ref:`mktplace-transaction-family-tutorial-label`.

The MarketPlace Client Reference assumes familiarity with both the MarketPlace
Data Model and the MarketPlace Transaction Family.  As such, neither will be
discussed outside how they correspond to mktclient commands.  If you have not
done so already, you may wish to familiarize yourself with the following:

    * The MarketPlace Data Model.  Please consult
      :ref:`mktplace-data-model-label` for more information on the
      underlying MarketPlace Data Model.
    * The MarketPlace Transaction Family.  Please consult
      :ref:`mktplace-transactions-label` for more information on the
      underlying MarketPlace Transaction Family.

Prerequisites
=============

To use mktclient, you need the following:

    * The sawtooth distribution installed on one or more machines.
    * The URL and port for a validator in the validator network.
    * A valid key used for signing transactions (this can be generated
      using the command *sawtooth keygen*).

Launching the MarketPlace Client
================================

.. note::
    For the remainder of the MarketPlace Client Reference:

    * {mktplace} refers to the top-level directory for the MarketPlace
    * {home} refers to the top-level directory for the validator

Two pieces of information are needed for mktclient to connect to a validator network:

    #. A valid key for signing transactions.
    #. The URL of a validator in the validator network.

These are provided through a combination of a JSON configuration file and
command-line options used to override the configuration settings.

mktclient Configuration File
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An example configuration file is as follows:

.. code-block:: none

    {
        ## Validator URL/port
        "LedgerURL" : "http://localhost:8800/",

        ## Logging configuration
        "LogLevel" : "WARN",
        "LogFile"  : "__screen__",

        ## Participant information
        "ParticipantName" : "player1",

        ## File with private key used for signing transactions
        "KeyFile" : "{home}/keys/{name}.wif"
    }

Of most interest are the entries:

* ``LedgerURL``  The URL and port for the validator.
* ``ParticipantName``  The name of the participant.
* ``KeyFile``  The location of the private key used for signing transactions.
  In the above example, if the top-level directory for the Sawtooth validator
  is /project/sawtooth-validator and assuming that the participant name has
  not been explicitly supplied as a command-line option, the key file will
  be located in /project/sawtooth-validator/keys/player1.wif.

Not present in the example above, but also of interest:

* ``ParticipantId``  The transaction ID used to register the participant.  To
  specify a participant ID, prepend three forward slashes (///) to the transaction
  ID as specified in :ref:`mktplace-object-names-label`.  For example, if the
  transaction ID to register the participant was 842bcb9ec98232db, the participant
  ID would be specified as follows in the configuration file:

  ``"ParticipantId" : "///842bcb9ec98232db"``

.. note::

    If ``ParticipantId`` and ``ParticipantName`` are both present in the
    configuration file, then the participant ID supersedes the participant
    name.

.. note::
    If  ``ParticipantName`` and/or ``ParticipantId`` are specified along with
    ``KeyFile`` and the participant has already been registered, the private
    key must be the same one that signed the transaction used to register the
    participant.

.. note::
    mktclient requires a signing key.  Therefore, ``KeyFile`` must appear in a
    configuration file or the ``--keyfile`` command-line option must be specified.

If a configuration file is not explicitly specified on the command line, the
mktclient searches for a configuration file named mktclient.js in the following
locations in order:

#. {home}/etc (i.e., the default validator configuration directory)
#. $HOME/.sawtooth on Linux or %USERPROFILE%\\.sawtooth on Windows
#. The current directory
#. {mktplace}/etc (i.e., the default mktclient configuration directory)

The default configuration file name and the search path can be changed via
command-line options (see below).

mktclient Command-Line Options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

mktclient has numerous command-line options that can be used to override
the default settings or the settings specified in the configuration file.  The
entire list of command-line options can be seen by executing mktclient with
the ``--help`` or ``-h`` command-line option:

.. code-block:: console

   $ cd {mktplace}
   $ ./bin/mktclient --help

The command-line options are:

* ``--config CONFIG [CONFIG ...]``  Specifies one or more configuration file
  names.  The configuration files will be applied in the order in which they
  are specified such that entries in a configuration file later in the list
  will override entries with the same name from configuration files earlier
  in the list.

  If only a file name is specified, mktclient will search the list of locations
  noted above for the configuration file.  The search path can be altered by using
  the ``--conf-dir`` command-line option.  Alternately, a configuration file can
  be specified using a relative or absolute path.
* ``--keyfile KEYFILE``  Specifies the name of the file that contains the private
  key used to sign MarketPlace transactions.

    .. note::

        If ``KeyFile`` does not appear in the configuration file(s), then the
        ``--keyfile`` command-line option is required.

    .. note::

        If mktclient is started with a participant that has already been registered,
        then the private key in KEYFILE must be the same one that was used to sign
        the transaction used to register the participant.

* ``--conf-dir CONF_DIR``  Specifies the name of the validator configuration
  directory.  This directory will replace {home}/etc in the list of directories
  searched for the configuration file(s).
* ``--name NAME``  Specifies the name of the participant to use as the creator
  of MarketPlace objects (i.e., accounts, etc.).

  If the default configuration is used, mktclient will search for the private key
  in {home}/etc/<NAME>.wif.

    .. note::

        If the participant has already been registered, then the private key in
        the key file must have been the one that was used to sign the transaction
        that registered the participant.

  If the participant ID is specified in either the configuration file or with the
  command-line option, the participant name will be superseded by the ID provided.
* ``--id ID``  Specifies the ID of the participant (i.e., the ID of the transaction
  that registered the participant) to use as the creator of MarketPlace objects.
  If this command-line option is supplied, it will supersede the participant name.
  To specify a participant ID, prepend three forward slashes (///) to the transaction
  ID as specified in :ref:`mktplace-object-names-label`.  For example, if the
  transaction ID to register the participant was 842bcb9ec98232db, the participant
  ID would be specified as follows:

  ``--id ///842bcb9ec98232db``

    .. note::

        The private key in the key file must have be the same one that was used to
        sign the transaction that registered the participant.

* ``--url URL``  Specifies the URL of the validator to use.
* ``--script SCRIPT``  Specifies the name of a file that contains mktclient
  commands to execute on startup before providing the interactive shell prompt
* ``--echo``  Specifies that commands should be echoed.  This is not necessarily
  useful when using the interactive shell, but when combined with the ``--script``
  command-line option allows you to see the commands that are executed.
* ``--log-dir LOG_DIR``  Specifies the name of the directory where the log file
  is written.
* ``--logfile LOGFILE``  Specifies the name of the log file.  A value of ``__screen__``
  (two underscores before and after) to have log messages sent to standard output.
* ``--log-level LEVEL``  Specifies the logging level.  Valid logging levels are:

    * CRITICAL
    * ERROR
    * WARNING/WARN
    * INFO
    * DEBUG.

* ``--set OPTION VALUE``  Specifies that an arbitrary configuration option, OPTION,
  be set to VALUE.
* ``--mapvar VARIABLE VALUE`` Specifies that a symbol named VARIABLE should be set
  to VALUE.  The symbol named VARIABLE is made available from the interactive shell
  prompt.  See below for the discussion about symbols.

mktclient Examples
^^^^^^^^^^^^^^^^^^

To start mktclient with a participant named mkt:

.. code-block:: console

    $ cd {mktplace}
    $ ./bin/mktclient --name mkt

To start mktclient with a participant created by the transaction with ID 842bcb9ec98232db:

.. code-block:: console

    $ cd {mktplace}
    $ ./bin/mktclient --id ///842bcb9ec98232db

If mktclient is started with a participant name that has not been previously registered,
the interactive shell provides the following prompt:

.. code-block:: none

    //UNKNOWN>

Otherwise, the interactive shell provides the following prompt (where {name} is replaced
with the name of the participant):

.. code-block:: none

    //{name}>

MarketPlace Client Commands
===========================

The mktclient interactive shell presents a prompt that accepts commands.  The list of
commands can by seen by executing the ``help`` command.

.. code-block:: none

    //UNKNOWN> help

    Documented commands (type help <topic>):
    ========================================
    EOF        dump           exit      liability    selloffer   waitforcommit
    account    echo           help      map          sleep
    asset      exchange       holding   offers       state
    assettype  exchangeoffer  holdings  participant  tokenstore

    Miscellaneous help topics:
    ==========================
    symbols  names

MarketPlace Transaction Family Commands
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The mktclient contains a set of commands that have a one-to-one correspondence
to the objects in the MarketPlace Data Model.  Specifically, these commands are:

* ``account``  Manage MarketPlace data model Account objects.
* ``asset``  Manage MarketPlace data model Asset objects.
* ``assettype``  Manage MarketPlace data model AssetType objects.
* ``exchangeoffer``  Manage MarketPlace data model ExchangeOffer objects.
* ``holding``  Manage MarketPlace data model Holding objects.
* ``liability``  Manage MarketPlace data model Liability objects.
* ``participant``  Manage MarketPlace data model Participant objects.
* ``selloffer``  Manage MarketPlace data model SellOffer objects.

Each of the data model commands has two sub-commands that correspond to the
MarketPlace Transaction Updates available for the data model objects:

* ``reg``  Registers a data model object.
* ``unr``  Unregisters a data model object.

All of the register sub-commands support the common subset of command-line options:

* ``--help`` or ``-h``  Provides additional sub-command-specific help information.
* ``--name NAME``  The name of the data model object.
* ``--description DESCRIPTION``  The description of the data model object.
* ``--waitforcommit``  Specifies that the command will not return to the interactive
  shell prompt until the transaction has been committed.
* ``--symbol SYMBOL``  A human-friendly symbol to associate with the transaction ID
  for the registration.  This symbol can be used later in other commands that use an
  identifier.

In addition to the common subset of command-line options, each of the register sub-commands
supports command-line options that have a one-to-one correspondence to properties in the
data model object.  The ``-h`` or ``--help`` command line option can be used to see them,
for example:

.. code-block:: none

    //UNKNOWN> asset reg --help
    usage: asset reg|unr [-h] [--waitforcommit] [--restricted | --no-restricted]
                         [--consumable | --no-consumable]
                         [--divisible | --no-divisible]
                         [--description DESCRIPTION] [--name NAME] --type TYPE
                         [--symbol SYMBOL]

    optional arguments:
      -h, --help            show this help message and exit
      --waitforcommit       Wait for transaction to commit before returning
      --restricted          Limit asset creation to the asset owner
      --no-restricted       Limit asset creation to the asset owner
      --consumable          Assets may not be copied
      --no-consumable       Assets may be copied infinitely
      --divisible           Fractional portions of an asset are acceptable
      --no-divisible        Assets may not be divided
      --description DESCRIPTION
                            Description of the asset
      --name NAME           Relative name, must begin with /
      --type TYPE           Fully qualified asset type name
      --symbol SYMBOL       Symbol to associate with the newly created id

To register a new participant named bob and then create an account, named
/myaccount, for bob:

.. code-block:: console

    $ cd {home}
    $ ./bin/sawtooth keygen --key-dir keys bob
    $ cd {market}
    $ ./bin/mktclient --name bob
    //UNKNWONN> participant reg --name bob --description "My Name Is Bob" --waitforcommit --symbol BOB_ID
    $BOB_ID = 163a6d90c6e1440f
    transaction 163a6d90c6e1440f submitted
    Wait for commit
    //bob> account reg --name /myaccount --description "Bob's Account" --symbol ACCOUNT_ID --waitforcommit
    $ACCOUNT_ID = 8e76be511243e9d2
    transaction 8e76be511243e9d2 submitted
    Wait for commit
    //bob>

Now that there is a participant, bob, and an associated account, /myaccount,
holdings can be added to the account.  Before registering a holding, an asset
type as well as an asset of that type need to be registered:

.. code-block:: none

    //bob> assettype reg --name /myassettype
    //bob> asset reg --name /myasset --type /myassettype
    //bob> holding reg --asset /myasset --count 5 --name /myholding1 --account /myaccount --description "My Holding 1"
    //bob> holding reg --asset /myasset --count 0 --name /myholding2 --account /myaccount --description "My Holding 2"
    //bob> dump --name /myholding1
    {
      "account": "8e76be511243e9d2",
      "asset": "2ccf837c6026571c",
      "count": 5,
      "creator": "163a6d90c6e1440f",
      "description": "My Holding 1",
      "name": "/myholding1",
      "object-type": "Holding"
    }
    //bob> dump --name /myholding2
    {
      "account": "8e76be511243e9d2",
      "asset": "2ccf837c6026571c",
      "count": 0,
      "creator": "163a6d90c6e1440f",
      "description": "My Holding 2",
      "name": "/myholding2",
      "object-type": "Holding"
    }

.. note::

    When registering the asset type, /myassettype, the ``--no-restricted``
    command-line option was not provided, meaning that only the participant
    bob can create assets of that type.  Furthermore, since the
    ``--no-restricted`` command-line option was not provided when registering
    the asset, /myasset, only the participant bob can create holdings of that asset.

In addition to the commands for MarketPlace Transaction Updates on data model objects,
there is one more MarketPlace Transaction Update command, ``exchange``.  It has the
following required command-line paramters:

* ``--src HOLDING``  The name of the holding from which assets are to be drawn.
* ``--dst HOLDING``  The name of the holding into which assets will be placed.
* ``--count COUNT``  The number of assets to transfer.

To transfer three assets from //bob/myholding1 to //bob/myholding2, execute the
following:

.. code-block:: none

    //bob> exchange --src /myholding1 --dst /myholding2 --count 3
    //bob> dump --name /myholding1
    {
      "account": "8e76be511243e9d2",
      "asset": "2ccf837c6026571c",
      "count": 2,
      "creator": "163a6d90c6e1440f",
      "description": "My Holding 1",
      "name": "/myholding1",
      "object-type": "Holding"
    }
    //bob> dump --name /myholding2
    {
      "account": "8e76be511243e9d2",
      "asset": "2ccf837c6026571c",
      "count": 3,
      "creator": "163a6d90c6e1440f",
      "description": "My Holding 2",
      "name": "/myholding2",
      "object-type": "Holding"
    }

Note that after the exchange, //bob/myholding1 has its original asset count
decremented by three and //bob/myholding2 has its original asset count
incremented by three.

Because an exchange is a transaction update, it also supports the same ``--waitforcommit``
command-line option as the commands that register/unregister data model objects.

All of the MarketPlace Data Model Transaction Update unregister sub-commands
support the same set of command-line options:

* ``--help`` or ``-h``  Provides additional sub-command-specific help information.
* ``--name NAME``  The name of the data model object to unregister.  As mentioned above,
  consult :ref:`mktplace-object-names-label` for how to specify names for data
  model objects.
* ``--waitforcommit``  Specifies that the command will not return to the interactive
  shell prompt until the transaction has been committed.

To unregister the participant named bob that was created above, all of the
following are equivalent:

* ``participant unr --name //bob``
* ``participant unr --name ///163a6d90c6e1440f``
* ``participant unr --name ///$BOB_ID``

Viewing Data Model Objects
^^^^^^^^^^^^^^^^^^^^^^^^^^

To view a previously-registered data model object, mktclient provides a
command, ``dump``, that has two command-line parameters:

* ``--name NAME``  The name, following the object naming rules, of the object
  to view.
* ``--fields FIELD [FIELD ...]``  The fields to view.  The fields are specific
  to the particular data model object type.  If the ``--fields`` option is
  omitted, all fields are shown.

For example, to view the participant bob and his account that were created
previously above:

.. code-block:: none

    //bob> dump --name //bob
    {
      "address": "1MNwVmFaZBsr4sSLxQrT575o6PDNbmq8ap",
      "description": "My Name Is Bob",
      "name": "bob",
      "object-type": "Participant"
    }
    //bob> dump --name ///$BOB_ID
    {
      "address": "1MNwVmFaZBsr4sSLxQrT575o6PDNbmq8ap",
      "description": "My Name Is Bob",
      "name": "bob",
      "object-type": "Participant"
    }
    //bob> dump --name //bob --fields name description
    bob
    My Name Is Bob
    //bob> dump --name /myaccount
    {
      "creator": "163a6d90c6e1440f",
      "description": "Bob's Account",
      "name": "/myaccount",
      "object-type": "Account"
    }
    //bob> dump --name //bob/myaccount
    {
      "creator": "163a6d90c6e1440f",
      "description": "Bob's Account",
      "name": "/myaccount",
      "object-type": "Account"
    }
    //bob> dump --name ///$ACCOUNT_ID
    {
      "creator": "163a6d90c6e1440f",
      "description": "Bob's Account",
      "name": "/myaccount",
      "object-type": "Account"
    }
    //bob>

.. note::

    In the above example, notice that because mktclient is currently running
    under the auspices of the participant named bob, the relative name /myaccount
    and the absolute name //bob/myaccount resolve to the same data model object.

    Also notice that symbols, specifically $BOB_ID and $ACCOUNT_ID, that were created
    when the data model objects were registered can also be used.

Viewing Holdings
^^^^^^^^^^^^^^^^

mktclient provides a command, ``holdings``, that can be used to view the current
holdings.  Without any command-line options, all holdings, regardless of the
creator are listed.

.. code-block:: none

    //bob> holdings
    10       //alice/aliceholding
    2        //bob/myholding1
    3        //bob/myholding2

The ``holdings`` command has several command-line options:

* ``--creator CREATOR``  Only list the holdings created by CREATOR.  If the
  special value ``@`` is used for the creator, it means the participant under
  which mktclient is currently running (i.e., the name that appears in the
  prompt).
* ``--assets ASSET [ASSET ...]``  Only list the holdings of the asset(s)
  specified.
* ``--sortby ATTRIBUTE``  Sort the output by the holding data model attribute
  specified.
* ``--verbose``  Provide verbose listing of holdings.

To list the holdings sorted by the count attribute with additional output
provided:

.. code-block:: none

    //bob> holdings --sortby count --verbose
    Balance  Holding
    2        //bob/myholding1
    3        //bob/myholding2
    10       //alice/aliceholding

If mktclient is running under the auspices of the participant bob, to
restrict the list of holdings to those that were created by bob, execute any
of the following:

.. code-block:: none

    //bob> holdings --creator //bob
    2        //bob/myholding1
    3        //bob/myholding2
    //bob> holdings --creator @
    2        //bob/myholding1
    3        //bob/myholding2
    //bob> holdings --creator ///$BOB_ID
    2        //bob/myholding1
    3        //bob/myholding2

To only see holdings of the asset //alice/aliceasset, execute the following:

.. code-block:: none

    //bob> holdings --asset //alice/aliceasset
    10       //alice/aliceholding

.. note::

    Because mktclient is running as participant bob, the asset name
    (i.e., //alice/aliceasset) has to be fully-qualified.  If instead
    mktclient was running as participant alice, the relative name, /aliceasset,
    can be used.

Viewing Exchange and Sell Offers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

mktclient provides a command, ``offers``, that can be used to view the current
offers.  Without any command-line options, all offers, regardless of the
creator are listed.

.. code-block:: none

    //bob> offers
    Ratio    Input Asset (What You Pay)          Output Asset (What You Get)         Name
    0.5      //mkt/asset/currency/USD            //mkt/asset/cookie/choc_chip        //bob/choc_chip_sale
    1000.0   //marketplace/asset/token           //mkt/asset/currency/USD            //mkt/offer/provision/USD

The ``offers`` command has several command-line options:

* ``--creator CREATOR``  Only list the offers created by CREATOR.  If the
  special value ``@`` is used for the creator, it means the participant under
  which mktclient is currently running (i.e., the name that appears in the
  prompt).
* ``--iasset ASSET``  Only list the offers where the input asset matches ASSET.
* ``--oasset ASSET``  Only list the offers where the output asset matches ASSET.
* ``--sortby FIELD``  Sort the output by FIELD.

If mktclient is running under the auspices of the participant bob, to restrict
the list of offers to those that were created by bob, execute any of the following:

.. code-block:: none

    //bob> offers --creator @
    Ratio    Input Asset (What You Pay)          Output Asset (What You Get)         Name
    0.5      //mkt/asset/currency/USD            //mkt/asset/cookie/choc_chip        //bob/choc_chip_sale
    //bob> offers --creator //bob
    Ratio    Input Asset (What You Pay)          Output Asset (What You Get)         Name
    0.5      //mkt/asset/currency/USD            //mkt/asset/cookie/choc_chip        //bob/choc_chip_sale
    //bob> offers --creator ///$BOB_ID
    Ratio    Input Asset (What You Pay)          Output Asset (What You Get)         Name
    0.5      //mkt/asset/currency/USD            //mkt/asset/cookie/choc_chip        //bob/choc_chip_sale

To only see offers in which the input asset type is //marketplace/accet/token,
execute the following:

.. code-block:: none

    //bob> offers --iasset //marketplace/asset/token
    Ratio    Input Asset (What You Pay)          Output Asset (What You Get)         Name
    1000.0   //marketplace/asset/token           //mkt/asset/currency/USD            //mkt/offer/provision/USD

Viewing MarketPlace State
^^^^^^^^^^^^^^^^^^^^^^^^^

mktclient provides a command, ``state``, that can be used to view the the transaction
updates used to register MarketPlace data model objects.  The state command supports
four sub-commands:

* ``fetch``  Fetches the current version of the ledger state.
* ``query``  Finds the object that matches the specified criteria.  By default,
  all objects are returned.  The following command-line options are supported:

    * ``--type TYPE``  The type of object to find, for example Participant.
    * ``--creator CREATOR``  Only return objects created by CREATOR. If the
      special value ``@`` is used for CREATOR, it means that participant under
      which mktclient is currently running (i.e., the name that appears in the
      prompt).
    * ``--name NAME``  Return the object with name matching NAME.
    * ``--fields FIELD [FIELD ...]``  The fields to print out for the objects
      returned.

* ``byname``  Gets the identifier of an object based upon its name.  The following
  command-line options are supported:

    * ``--name NAME``  The name of the object.
    * ``--symbol SYMBOL``  The symbol name that will be associated with the identifier.

* ``value``  Gets the value associated with a field in the state.  The following
  command-line options are supported:

    * ``--path PATH``  A period-separated path, beginning with the identifier,
      to the object field to retrieve.  If only the identifier is supplied, all
      fields are returned.

To get the list of participants registered:

.. code-block:: none

    //bob> state query --type Participant
    [
      "163a6d90c6e1440f",
      "b2232c7b18ff1c8e",
      "aac66eea84ce8444"
    ]
    //bob> state query --type Participant --fields name
    [
      [
        "bob"
      ],
      [
        "marketplace"
      ],
      [
        "alice"
      ]
    ]

To get the list of data model objects created by participant bob:

.. code-block:: none

    //bob> state query --fields name --creator //bob
    [
      [
        "/myassettype"
      ],
      [
        "/myholding1"
      ],
      [
        "/myaccount"
      ],
      [
        "/myasset"
      ],
      [
        "/myholding2"
      ]
    ]
    //bob> state query --fields name --creator @
    [
      [
        "/myassettype"
      ],
      [
        "/myholding1"
      ],
      [
        "/myaccount"
      ],
      [
        "/myasset"
      ],
      [
        "/myholding2"
      ]
    ]
    //bob> state query --fields name --creator ///$BOB_ID
    [
      [
        "/myassettype"
      ],
      [
        "/myholding1"
      ],
      [
        "/myaccount"
      ],
      [
        "/myasset"
      ],
      [
        "/myholding2"
      ]
    ]

To get the identifier for the participant bob, executing the following:

.. code-block:: none

    //bob> state byname --name //bob
    163a6d90c6e1440f
    //bob> state byname --name //bob --symbol BOB_ID
    //bob> echo $BOB_ID
    163a6d90c6e1440f

To get the name for the participant bob, using the identifier, execute the following:

.. code-block:: none

    //bob> state byname --name //bob --symbol BOB_ID
    //bob> state value --path $BOB_ID
    OrderedDict([('address', '1MNwVmFaZBsr4sSLxQrT575o6PDNbmq8ap'), ('description', ''), ('name', 'bob'), ('object-type', 'Participant')])
    //bob> state value --path $BOB_ID.name
    bob

Managing Symbols
^^^^^^^^^^^^^^^^

The mktclient interactive shell supports creating human-friendly symbols
for identifiers via the ``--symbol`` command-line option for the commands
that register data model objects.  In addition, mktclient has commands,
``map`` and ``echo``, for creating and querying, respectively, symbol values.
For example:

.. code-block:: none

    //bob> map --symbol BOB_ID --value 163a6d90c6e1440f
    $BOB_ID = 163a6d90c6e1440f
    //bob> echo $BOB_ID
    163a6d90c6e1440f

Miscellaneous Commands
^^^^^^^^^^^^^^^^^^^^^^

* ``sleep SECONDS``  This causes the mktclient interactive shell to pause for the
  number of seconds requested.
* ``waitforcommit [--txn TXN_ID]``  Like the ``--waitforcommit`` command-line option
  on the MarketPlace Transaction Update commands, if the ``--txn`` command-line option
  is provided this commands waits until the transaction with ID TXN_ID has been committed.
  If the ``--txn`` command-line option is not present, this command wants for the most-recent
  transaction to complete.

Terminating mktclient
^^^^^^^^^^^^^^^^^^^^^

The ``exit`` or ``EOF`` command may be used to terminate the mktclient interactive
shell.

Further Reading
===============

This reference has only provided a very elementary example of transactions.  Consult
the tutorial :ref:`mktplace-transaction-family-tutorial-label` for a more
complete example of registering MarketPlace data model objects as well as MarketPlace
transaction updates.