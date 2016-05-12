
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
      using txnkeygen).

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

The following steps can be used to start the mktclient, create assets,
and exchange them.

#. Register as a participant on the network

   .. code-block:: none

      participant reg

#. Register an account

   .. code-block:: none

      account reg --name /kellysaccount

#. Register an asset type

   .. code-block:: none

      assettype reg --name /kellysassets

#. Create an asset type

   .. code-block:: none

      asset reg --name /theasset --type /kellysassets

#. Create holdings of an asset

   .. code-block:: none

      holding reg --asset /theasset --count 5 --name /kellysholdingoftheasset --account /kellysaccount
      holding reg --asset /theasset --count 0  --name /kellysholdingoftheasset2 --account /kellysaccount

#. Exchange/trade asset holdings

   .. code-block:: none

      exchange --src /kellysholdingoftheasset --dst /kellysholdingoftheasset2 --count 3

#. Check the balance of  the holding

   .. code-block:: none

      dump --name /kellysholdingoftheasset
      dump --name /kellysholdingoftheasset2

This will show "/kellysholdingoftheasset" with 2 and
"/kellysholdingoftheasset2" with 3.

